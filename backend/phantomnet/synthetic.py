"""Synthetic episode generator producing realistic deterministic scripted traces for PHANTOMNET."""

from __future__ import annotations

import random
from typing import Any

from phantomnet.events import EventKind, PhantomEvent


def generate_synthetic_episode(seed: int = 42) -> list[PhantomEvent]:
    """Generate a realistic, deterministic scripted episode demonstrating all 13 event kinds.

    Timeline Narrative:
    1. [t=0.0 - 0.5] Handshake Ritual: Noise XX handshake exchange, keys spark, session locks in.
    2. [t=0.5 - 2.5] Unshaped Traffic: Normal raw flow (plain mask). Conduit flows, barcode scrolls.
    3. [t=2.5 - 3.5] Censor Inspection: Censor score spikes, throttle action, then gate block.
    4. [t=3.5 - 4.5] Defender Response: Policy decision evaluates overhead, switches mask profile.
    5. [t=4.5 - 5.5] Tunnel Re-weld & Rekey: Pipe reconnects, rekey event fires, session re-welded.
    6. [t=5.5 - 7.5] Shaped Stealth Flow: Reshaped packets pass censor smoothly (score < 0.15).
    7. [t=7.5 - 9.0] Mesh Reroute & Co-Train: Topology link perturbation, co-train, benchmarks.
    """
    rng = random.Random(seed)
    events: list[PhantomEvent] = []
    seq = 1

    def emit(
        t: float,
        kind: EventKind,
        flow_id: str | None = None,
        src: str | None = None,
        dst: str | None = None,
        size: int | None = None,
        dir: str | None = None,
        state: str | None = None,
        mask_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        nonlocal seq
        events.append(
            PhantomEvent(
                version=1,
                seq=seq,
                t=round(t, 4),
                kind=kind,
                flow_id=flow_id,
                src=src,
                dst=dst,
                size=size,
                dir=dir,
                state=state,
                mask_id=mask_id,
                meta=meta or {},
            )
        )
        seq += 1

    client = "127.0.0.1:49152"
    server = "127.0.0.1:8443"
    flow_id = "flow-alpha"

    # --- 1. Handshake Ritual (t: 0.0 - 0.4s) ---
    emit(
        0.00,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        src=client,
        dst=server,
        state="HANDSHAKE_INIT",
        mask_id="plain",
        meta={"stage": "start", "pattern": "Noise_XX_25519_ChaChaPoly_BLAKE2s"},
    )
    emit(
        0.08,
        EventKind.HANDSHAKE_MSG,
        flow_id=flow_id,
        src=client,
        dst=server,
        size=32,
        dir="TX",
        state="HANDSHAKE_MSG_1",
        mask_id="plain",
        meta={"step": 1, "payload": "-> e", "spark": "client_ephemeral"},
    )
    emit(
        0.18,
        EventKind.HANDSHAKE_MSG,
        flow_id=flow_id,
        src=server,
        dst=client,
        size=96,
        dir="RX",
        state="HANDSHAKE_MSG_2",
        mask_id="plain",
        meta={"step": 2, "payload": "<- e, ee, s, es", "spark": "server_dh_mix"},
    )
    emit(
        0.28,
        EventKind.HANDSHAKE_MSG,
        flow_id=flow_id,
        src=client,
        dst=server,
        size=64,
        dir="TX",
        state="HANDSHAKE_MSG_3",
        mask_id="plain",
        meta={"step": 3, "payload": "-> s, se", "spark": "client_auth"},
    )
    emit(
        0.35,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        src=client,
        dst=server,
        state="ESTABLISHED",
        mask_id="plain",
        meta={"session_id": "sess-4f9b8c02", "cipher": "ChaCha20-Poly1305"},
    )

    # --- 2. Unshaped Traffic (t: 0.5 - 2.2s) ---
    t = 0.5
    raw_sizes = [1420, 312, 1420, 890, 64, 1420, 1100, 1420, 540, 280]
    for i, sz in enumerate(raw_sizes):
        direction = "TX" if i % 2 == 0 else "RX"
        src_node = client if direction == "TX" else server
        dst_node = server if direction == "TX" else client
        t += rng.uniform(0.12, 0.22)
        emit(
            t,
            EventKind.PKT_TX if direction == "TX" else EventKind.PKT_RX,
            flow_id=flow_id,
            src=src_node,
            dst=dst_node,
            size=sz,
            dir=direction,
            state="ESTABLISHED",
            mask_id="plain",
            meta={"entropy": 7.96, "packet_idx": i},
        )
        censor_score = round(0.15 + (i * 0.08), 3)
        emit(
            t + 0.02,
            EventKind.CENSOR_SCORE,
            flow_id=flow_id,
            src="censor-proxy",
            dst=client,
            state="INSPECTING",
            mask_id="plain",
            meta={"score": censor_score, "confidence": round(censor_score * 0.95, 2)},
        )

    # --- 3. Censor Throttle & Gate Slam (t: 2.4 - 3.2s) ---
    t = 2.4
    emit(
        t,
        EventKind.CENSOR_ACTION,
        flow_id=flow_id,
        src="censor-proxy",
        dst=client,
        state="THROTTLED",
        mask_id="plain",
        meta={"action": "THROTTLE", "rate_limit_kbps": 64, "reason": "Fingerprint match: plain"},
    )
    emit(
        t + 0.05,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        state="THROTTLED",
        mask_id="plain",
        meta={"pipe_width_ratio": 0.35},
    )

    for _ in range(3):
        t += 0.2
        emit(
            t,
            EventKind.PKT_TX,
            flow_id=flow_id,
            src=client,
            dst=server,
            size=1420,
            dir="TX",
            state="THROTTLED",
            mask_id="plain",
        )

    t += 0.25
    emit(
        t,
        EventKind.CENSOR_SCORE,
        flow_id=flow_id,
        src="censor-proxy",
        state="BLOCK_THRESHOLD_EXCEEDED",
        mask_id="plain",
        meta={"score": 0.985, "confidence": 0.99},
    )
    emit(
        t + 0.02,
        EventKind.CENSOR_ACTION,
        flow_id=flow_id,
        src="censor-proxy",
        dst=client,
        state="BLOCKED",
        mask_id="plain",
        meta={"action": "BLOCK", "reason": "Signature confidence >= 0.98"},
    )
    emit(
        t + 0.04,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        state="BLOCKED",
        mask_id="plain",
        meta={"gate_slammed": True},
    )
    for d_idx in range(4):
        t += 0.08
        emit(
            t,
            EventKind.PKT_DROP,
            flow_id=flow_id,
            src=client,
            dst=server,
            size=1420,
            dir="TX",
            state="BLOCKED",
            mask_id="plain",
            meta={"drop_reason": "Censor gate reset RST", "drop_id": d_idx},
        )

    # --- 4. Mask Foundry & Policy Decision (t: 3.8 - 4.4s) ---
    t = 3.8
    emit(
        t,
        EventKind.POLICY_DECISION,
        flow_id=flow_id,
        src="defender-ml",
        state="DECIDING",
        mask_id="plain",
        meta={
            "action": "SELECT_MASK",
            "candidate": "mimic_https_stream",
            "reasoning": "Plain MTU fingerprint detected. Morphing packet length to HTTPS/2.",
            "bandwidth_overhead": 0.142,
            "latency_penalty_ms": 3.8,
            "reward": 0.884,
        },
    )
    emit(
        t + 0.2,
        EventKind.MASK_SWITCH,
        flow_id=flow_id,
        src="defender-ml",
        state="MASKING",
        mask_id="mimic_https_stream",
        meta={"old_mask": "plain", "new_mask": "mimic_https_stream", "quant_step": 128},
    )

    # --- 5. Tunnel Reconnect & Mini Rekey Ritual (t: 4.5 - 5.2s) ---
    t = 4.5
    emit(
        t,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        state="RECONNECTING",
        mask_id="mimic_https_stream",
        meta={"event": "pipe_reweld_start"},
    )
    emit(
        t + 0.2,
        EventKind.REKEY,
        flow_id=flow_id,
        src=client,
        dst=server,
        size=48,
        dir="TX",
        state="REKEYING",
        mask_id="mimic_https_stream",
        meta={"epoch": 2, "new_session_id": "sess-99a1f301"},
    )
    emit(
        t + 0.35,
        EventKind.CONN_STATE,
        flow_id=flow_id,
        state="ESTABLISHED",
        mask_id="mimic_https_stream",
        meta={"event": "pipe_rewelded", "active_mask": "mimic_https_stream"},
    )

    # --- 6. Shaped Traffic & Censor Neutralization (t: 5.5 - 7.2s) ---
    t = 5.5
    masked_sizes = [512, 512, 1024, 512, 256, 1024, 512, 1024, 512, 768]
    for j, sz in enumerate(masked_sizes):
        direction = "TX" if j % 2 == 0 else "RX"
        src_node = client if direction == "TX" else server
        dst_node = server if direction == "TX" else client
        t += rng.uniform(0.10, 0.18)
        emit(
            t,
            EventKind.PKT_TX if direction == "TX" else EventKind.PKT_RX,
            flow_id=flow_id,
            src=src_node,
            dst=dst_node,
            size=sz,
            dir=direction,
            state="ESTABLISHED",
            mask_id="mimic_https_stream",
            meta={"padded": True, "target_profile": "HTTPS2_MIMIC"},
        )
        suppressed_score = round(max(0.05, 0.14 - (j * 0.01)), 3)
        emit(
            t + 0.02,
            EventKind.CENSOR_SCORE,
            flow_id=flow_id,
            src="censor-proxy",
            state="INSPECTING",
            mask_id="mimic_https_stream",
            meta={"score": suppressed_score, "confidence": 0.12},
        )

    emit(
        t + 0.05,
        EventKind.CENSOR_ACTION,
        flow_id=flow_id,
        src="censor-proxy",
        state="ALLOW",
        mask_id="mimic_https_stream",
        meta={"action": "ALLOW", "reason": "Entropy matches HTTPS traffic baseline"},
    )

    # --- 7. Mesh Reroute, Training Rounds & Live Evidence (t: 7.5 - 9.0s) ---
    t = 7.5
    emit(
        t,
        EventKind.ROUTE_CHANGE,
        flow_id=flow_id,
        src="routelab-core",
        state="TOPOLOGY_REROUTE",
        mask_id="mimic_https_stream",
        meta={
            "failed_link": "relay-2->relay-3",
            "new_path": ["client", "relay-1", "relay-4", "server"],
            "oracle_optimal_cost": 24.5,
            "chosen_path_cost": 26.0,
            "stretch": 1.06,
        },
    )

    t = 8.0
    for r in range(1, 4):
        t += 0.25
        emit(
            t,
            EventKind.TRAIN_ROUND,
            flow_id=flow_id,
            src="adversarial-arena",
            state="CO_TRAIN",
            mask_id="mimic_https_stream",
            meta={
                "round": r,
                "censor_loss": round(0.65 - (r * 0.12), 3),
                "defender_stealth_auc": round(0.52 - (r * 0.03), 3),
                "pareto_overhead": round(0.12 + (r * 0.01), 3),
                "pareto_detection_rate": round(0.18 - (r * 0.04), 3),
            },
        )

    t = 8.8
    emit(
        t,
        EventKind.BENCH_MARK,
        flow_id=flow_id,
        src="evidence-engine",
        state="MEASURED",
        mask_id="mimic_https_stream",
        meta={
            "tunnel_throughput_mbps": 482.4,
            "handshake_latency_ms": 1.42,
            "rekey_latency_ms": 0.38,
            "bandwidth_overhead_pct": 14.2,
            "censor_evasion_rate_pct": 98.7,
            "frame_fps_median": 60.0,
        },
    )

    return events
