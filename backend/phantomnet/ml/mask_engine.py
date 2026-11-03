"""Mask Engine: parameter vector morphing, padding, jitter, dummy packets, and handshake masking.

Evaluates trade-offs:
Reward = stealth - lambda1 * bandwidth_overhead - lambda2 * latency_cost
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from phantomnet.data.traces import FlowTrace, PacketMeta


@dataclass(frozen=True)
class MaskParameters:
    """Tunable parameter vector governing transport and handshake traffic shaping."""

    pad_bucket: int = 128  # Quantize packet size to bucket multiples (e.g., 64, 128, 256, 512)
    jitter_ms: float = 2.0  # Timing delay variance in milliseconds
    dummy_rate: float = 0.05  # Probability of injecting dummy cover packets
    burst_chop: int = 8  # Maximum consecutive packets before inserting delay
    morph_ratio: float = 0.2  # Fraction of packets morphed to cover distribution

    # Gate D: Noise Handshake Masking Parameters
    hs_pad_m1: int = 0  # Payload padding for Noise XX Msg 1 (bytes)
    hs_pad_m2: int = 0  # Payload padding for Noise XX Msg 2 (bytes)
    hs_pad_m3: int = 0  # Payload padding for Noise XX Msg 3 (bytes)
    hs_preamble_count: int = 0  # Number of dummy preamble packets before handshake (0-2)
    hs_jitter_ms: float = 0.0  # Handshake round-trip timing jitter variance (ms)

    def to_vector(self) -> list[float]:
        return [
            float(self.pad_bucket),
            self.jitter_ms,
            self.dummy_rate,
            float(self.burst_chop),
            self.morph_ratio,
            float(self.hs_pad_m1),
            float(self.hs_pad_m2),
            float(self.hs_pad_m3),
            float(self.hs_preamble_count),
            self.hs_jitter_ms,
        ]

    @classmethod
    def from_vector(cls, v: list[float]) -> MaskParameters:
        if len(v) < 10:
            return cls(
                pad_bucket=max(32, int(round(v[0] / 32.0) * 32)),
                jitter_ms=max(0.0, min(25.0, v[1])),
                dummy_rate=max(0.0, min(0.4, v[2])),
                burst_chop=max(2, min(20, int(round(v[3])))),
                morph_ratio=max(0.0, min(1.0, v[4])),
            )
        return cls(
            pad_bucket=max(32, int(round(v[0] / 32.0) * 32)),
            jitter_ms=max(0.0, min(25.0, v[1])),
            dummy_rate=max(0.0, min(0.4, v[2])),
            burst_chop=max(2, min(20, int(round(v[3])))),
            morph_ratio=max(0.0, min(1.0, v[4])),
            hs_pad_m1=max(0, min(500, int(round(v[5])))),
            hs_pad_m2=max(0, min(700, int(round(v[6])))),
            hs_pad_m3=max(0, min(300, int(round(v[7])))),
            hs_preamble_count=max(0, min(2, int(round(v[8])))),
            hs_jitter_ms=max(0.0, min(20.0, v[9])),
        )


@dataclass(frozen=True)
class MaskEvaluation:
    """Telemetry describing overheads and objective reward from shaping."""

    raw_bytes: int
    masked_bytes: int
    bandwidth_overhead: float  # (masked - raw) / raw
    latency_cost_ms: float  # Mean added delay per packet in ms
    stealth_score: float  # 1.0 - censor_confidence
    reward: float  # stealth - l1 * overhead - l2 * latency


class MaskEngine:
    """Adversarial traffic morphing engine."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def shape_flow(
        self,
        raw_trace: FlowTrace,
        params: MaskParameters,
        censor_confidence: float = 0.5,
        l1: float = 0.4,
        l2: float = 0.02,
    ) -> tuple[FlowTrace, MaskEvaluation]:
        """Apply shaping parameters to raw flow metadata."""
        raw_packets = raw_trace.packets
        raw_bytes = sum(p.size for p in raw_packets)
        shaped_packets: list[PacketMeta] = []

        total_added_delay = 0.0

        # Gate D: Handshake Masking for tunnel flows
        start_idx = 0
        if raw_trace.is_tunnel and len(raw_packets) >= 3:
            # 1. Dummy preambles before handshake
            if params.hs_preamble_count > 0:
                for _ in range(params.hs_preamble_count):
                    p_size = self.rng.choice([240, 320, 512])
                    p_dt = round(self.rng.uniform(0.001, 0.004), 5)
                    shaped_packets.append(PacketMeta(size=p_size, direction="TX", dt=p_dt))
                    total_added_delay += p_dt

            # 2. Handshake messages (M1, M2, M3)
            hs_pads = [params.hs_pad_m1, params.hs_pad_m2, params.hs_pad_m3]
            for i in range(3):
                orig_p = raw_packets[i]
                padded_size = min(1500, orig_p.size + hs_pads[i])
                jit = (
                    self.rng.uniform(0.0, params.hs_jitter_ms / 1000.0)
                    if params.hs_jitter_ms > 0
                    else 0.0
                )
                dt = round(orig_p.dt + jit, 5)
                total_added_delay += jit
                shaped_packets.append(
                    PacketMeta(size=padded_size, direction=orig_p.direction, dt=dt)
                )

            start_idx = 3

        # Transport data packet shaping
        consecutive_dir = ""
        burst_len = 0

        for p in raw_packets[start_idx:]:
            size = p.size
            dt = p.dt

            # 1. Bucket padding
            if params.pad_bucket > 0:
                size = int(
                    ((size + params.pad_bucket - 1) // params.pad_bucket) * params.pad_bucket
                )
                size = min(1500, size)

            # 2. Size morphing
            if self.rng.random() < params.morph_ratio:
                size = int(size * 0.7 + self.rng.choice([384, 512, 640]) * 0.3)

            # 3. Timing jitter
            if params.jitter_ms > 0:
                added_jitter = self.rng.uniform(0.0, params.jitter_ms / 1000.0)
                dt += added_jitter
                total_added_delay += added_jitter

            # 4. Burst splitting
            if p.direction == consecutive_dir:
                burst_len += 1
                if burst_len >= params.burst_chop:
                    burst_delay = 0.005
                    dt += burst_delay
                    total_added_delay += burst_delay
                    burst_len = 0
            else:
                consecutive_dir = p.direction
                burst_len = 1

            shaped_packets.append(PacketMeta(size=size, direction=p.direction, dt=round(dt, 5)))

            # 5. Dummy packet injection
            if self.rng.random() < params.dummy_rate:
                dummy_dir: Literal["TX", "RX"] = "TX" if p.direction == "RX" else "RX"
                dummy_size = self.rng.choice([128, 256, 512])
                dummy_dt = 0.002
                shaped_packets.append(PacketMeta(size=dummy_size, direction=dummy_dir, dt=dummy_dt))

        masked_bytes = sum(p.size for p in shaped_packets)
        bw_overhead = max(0.0, (masked_bytes - raw_bytes) / float(max(1, raw_bytes)))
        mean_delay_ms = (total_added_delay / float(max(1, len(raw_packets)))) * 1000.0

        stealth = max(0.0, min(1.0, 1.0 - censor_confidence))
        reward = stealth - (l1 * bw_overhead) - (l2 * (mean_delay_ms / 10.0))

        evaluation = MaskEvaluation(
            raw_bytes=raw_bytes,
            masked_bytes=masked_bytes,
            bandwidth_overhead=round(bw_overhead, 4),
            latency_cost_ms=round(mean_delay_ms, 3),
            stealth_score=round(stealth, 4),
            reward=round(reward, 4),
        )

        shaped_trace = FlowTrace(
            site_id=raw_trace.site_id,
            category=raw_trace.category,
            is_tunnel=raw_trace.is_tunnel,
            packets=shaped_packets,
        )

        return shaped_trace, evaluation
