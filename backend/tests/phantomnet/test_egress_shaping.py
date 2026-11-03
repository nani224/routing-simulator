"""Gate J Requirement 1: Verification of Live Wire-Level Egress Shaping.

Tests that shaping is applied at the tunnel EGRESS in the live code path,
and verifies that the raw bytes and packet arrival timing captured by an
intercepting TCP tap proxy on the wire strictly differ from the unshaped baseline.
"""

from __future__ import annotations

import asyncio
import time
from typing import Literal

import pytest
from phantomnet.data.traces import PacketMeta
from phantomnet.ml.morphing import MorphingParameters
from phantomnet.tunnel.framing import FrameType
from phantomnet.tunnel.shaper import TunnelEgressShaper


@pytest.mark.asyncio
async def test_gate_j_live_egress_shaping_differs_from_unshaped() -> None:
    """Prove that bytes and timings observed by an intercepting TCP tap differ when shaped."""
    unshaped_packets: list[PacketMeta] = []
    shaped_packets: list[PacketMeta] = []

    async def run_wire_exchange(shaper: TunnelEgressShaper, packet_sink: list[PacketMeta]) -> None:
        prev_t = time.perf_counter()

        # 1. Start TCP tap proxy (simulating on-path censor inspection gateway)
        async def tap_handler(
            c_reader: asyncio.StreamReader, c_writer: asyncio.StreamWriter
        ) -> None:
            s_reader, s_writer = await asyncio.open_connection("127.0.0.1", echo_port)

            async def fwd(
                src: asyncio.StreamReader, dst: asyncio.StreamWriter, dir_label: Literal["TX", "RX"]
            ) -> None:
                nonlocal prev_t
                while True:
                    data = await src.read(4096)
                    if not data:
                        break
                    now = time.perf_counter()
                    packet_sink.append(
                        PacketMeta(size=len(data), direction=dir_label, dt=round(now - prev_t, 6))
                    )
                    prev_t = now
                    dst.write(data)
                    await dst.drain()

            await asyncio.gather(
                fwd(c_reader, s_writer, "TX"),
                fwd(s_reader, c_writer, "RX"),
                return_exceptions=True,
            )

        # 2. Echo server
        async def echo_handler(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            while True:
                data = await r.read(4096)
                if not data:
                    break
                w.write(data)
                await w.drain()
            w.close()

        echo_srv = await asyncio.start_server(echo_handler, "127.0.0.1", 0)
        echo_port = int(echo_srv.sockets[0].getsockname()[1])

        tap_srv = await asyncio.start_server(tap_handler, "127.0.0.1", 0)
        tap_port = int(tap_srv.sockets[0].getsockname()[1])

        # 3. Client connects through tap and transmits payloads with shaper
        c_reader, c_writer = await asyncio.open_connection("127.0.0.1", tap_port)

        for seq in range(1, 6):
            payload = f"Payload-Chunk-{seq}-{b'A' * (seq * 30)}".encode()
            await shaper.shape_and_write(c_writer, FrameType.DATA, seq, payload)

        c_writer.close()
        await c_writer.wait_closed()
        tap_srv.close()
        echo_srv.close()

    # Run 1: Unshaped baseline
    unshaped_shaper = TunnelEgressShaper(enabled=False)
    await run_wire_exchange(unshaped_shaper, unshaped_packets)

    # Run 2: Shaped with traffic morphing parameters
    shaped_params = MorphingParameters(
        morph_strength=0.8,
        size_bucket=256,
        timing_quantization_ms=5.0,
        dummy_rate=0.4,
    )
    shaped_shaper = TunnelEgressShaper(params=shaped_params, enabled=True, seed=42)
    await run_wire_exchange(shaped_shaper, shaped_packets)

    assert len(unshaped_packets) > 0
    assert len(shaped_packets) > 0

    unshaped_sizes = [p.size for p in unshaped_packets]
    shaped_sizes = [p.size for p in shaped_packets]

    unshaped_bytes = sum(unshaped_sizes)
    shaped_bytes = sum(shaped_sizes)

    # Gate J.1: Prove wire bytes differ and overhead is positive
    assert shaped_bytes > unshaped_bytes, (
        f"Shaped wire bytes ({shaped_bytes}) must exceed unshaped ({unshaped_bytes})"
    )

    # Gate J.1: Prove packet size sequence on the wire differs
    assert shaped_sizes != unshaped_sizes, "Wire packet size sequences must differ"

    # Gate J.1: Prove timing gaps on the wire differ
    unshaped_gaps = [p.dt for p in unshaped_packets]
    shaped_gaps = [p.dt for p in shaped_packets]
    assert shaped_gaps != unshaped_gaps, "Wire timing gaps must differ"
