"""Tunnel throughput and latency baseline benchmarks exporting to /evidence/bench/tunnel.json."""

from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
from pathlib import Path

import pytest
from phantomnet.bus import PhantomEventBus
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.tunnel.client import TunnelClient
from phantomnet.tunnel.server import TunnelServer


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get_git_commit_hash() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "development"


@pytest.mark.asyncio
async def test_tunnel_benchmark_and_evidence_export() -> None:
    """Benchmark tunnel handshake time, rekey latency, and throughput, writing evidence artifact."""
    port = get_free_port()
    bus = PhantomEventBus(run_id="bench-tunnel-run")

    server = TunnelServer(host="127.0.0.1", port=port, event_bus=bus)
    await server.start()

    client = TunnelClient(server_host="127.0.0.1", server_port=port, event_bus=bus)

    # 1. Measure Handshake Latency
    t0 = time.perf_counter()
    await client.connect()
    handshake_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    # 2. Measure Rekey Latency
    t0 = time.perf_counter()
    await client.rekey()
    rekey_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    # 3. Measure Data Transfer Throughput & RTT Latency
    payload_chunk = b"X" * 16384  # 16 KB chunks
    num_chunks = 200  # 3.2 MB total
    t0 = time.perf_counter()
    for _ in range(num_chunks):
        resp = await client.send_data(payload_chunk)
        assert len(resp) >= len(payload_chunk)
    total_time_s = time.perf_counter() - t0

    total_bytes = len(payload_chunk) * num_chunks
    throughput_mbps = round((total_bytes * 8.0) / (total_time_s * 1_000_000.0), 2)
    avg_rtt_ms = round((total_time_s / num_chunks) * 1000.0, 3)

    await client.close()
    await server.stop()

    # Machine and execution metadata
    evidence_data = {
        "benchmark": "tunnel_baseline",
        "timestamp": time.time(),
        "commit_hash": get_git_commit_hash(),
        "seed": 42,
        "machine_info": {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python_version": platform.python_version(),
        },
        "metrics": {
            "handshake_latency_ms": handshake_latency_ms,
            "rekey_latency_ms": rekey_latency_ms,
            "average_rtt_latency_ms": avg_rtt_ms,
            "throughput_mbps": throughput_mbps,
            "chunks_transferred": num_chunks,
            "total_bytes_transferred": total_bytes,
        },
    }

    # Emit BENCH_MARK event
    bus.publish_sync(
        PhantomEvent(
            version=1,
            seq=bus.current_seq + 1,
            t=time.time(),
            kind=EventKind.BENCH_MARK,
            state="MEASURED",
            meta=evidence_data["metrics"],
        )
    )

    # Write evidence artifact
    evidence_dir = Path("evidence/bench")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_file = evidence_dir / "tunnel.json"
    out_file.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    assert out_file.exists()
    assert handshake_latency_ms < 500.0  # Must be sub-second local handshake
    assert throughput_mbps > 5.0  # Must achieve reasonable loopback throughput
