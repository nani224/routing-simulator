"""Mask Engine: parameter vector morphing, padding, jitter, and dummy packet insertion.

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
    """Tunable parameter vector governing traffic shaping."""

    pad_bucket: int = 128  # Quantize packet size to bucket multiples (e.g., 64, 128, 256, 512)
    jitter_ms: float = 2.0  # Timing delay variance in milliseconds
    dummy_rate: float = 0.05  # Probability of injecting dummy cover packets
    burst_chop: int = 8  # Maximum consecutive packets before inserting delay
    morph_ratio: float = 0.2  # Fraction of packets morphed to cover distribution

    def to_vector(self) -> list[float]:
        return [
            float(self.pad_bucket),
            self.jitter_ms,
            self.dummy_rate,
            float(self.burst_chop),
            self.morph_ratio,
        ]

    @classmethod
    def from_vector(cls, v: list[float]) -> MaskParameters:
        return cls(
            pad_bucket=max(32, int(round(v[0] / 32.0) * 32)),
            jitter_ms=max(0.0, min(25.0, v[1])),
            dummy_rate=max(0.0, min(0.4, v[2])),
            burst_chop=max(2, min(20, int(round(v[3])))),
            morph_ratio=max(0.0, min(1.0, v[4])),
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
        consecutive_dir = ""
        burst_len = 0

        for p in raw_packets:
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
                # Sample toward a neutral 512-byte cover distribution
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
                    burst_delay = 0.005  # 5ms chop delay
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
