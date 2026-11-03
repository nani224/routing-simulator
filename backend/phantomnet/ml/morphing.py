"""Gate J: Empirical Target Distribution Traffic Morphing.

Replaces target-less padding with empirical distribution matching:
1. EmpiricalTLSDistribution: Learns empirical size and timing gap distributions
   exclusively from direct TLS 1.3 flows on TRAIN sites (never touches test sites).
2. TrafficMorpher: Samples packet sizes and gaps from target distributions,
   morphs outgoing packet lengths, quantizes timings, and injects dummy frames.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from phantomnet.data.traces import FlowTrace, PacketMeta


@dataclass
class MorphingParameters:
    """Tunable parameters for traffic morphing defense."""

    morph_strength: float = 0.5  # 0.0 = raw, 1.0 = full target distribution
    size_bucket: int = 64  # Quantization bucket size
    timing_quantization_ms: float = 2.0  # Timing jitter / gap quantization
    dummy_rate: float = 0.05  # Rate of dummy wire frame injection
    hs_pad_m1: int = 144  # Pad Noise msg 1 (96B -> ~240B ClientHello)
    hs_pad_m2: int = 500  # Pad Noise msg 2 (144B -> ~644B ServerHello)
    hs_pad_m3: int = 100  # Pad Noise msg 3 (128B -> ~228B Finished)
    hs_jitter_ms: float = 2.0  # Handshake timing jitter in ms

    def to_vector(self) -> list[float]:
        return [
            self.morph_strength,
            float(self.size_bucket),
            self.timing_quantization_ms,
            self.dummy_rate,
            float(self.hs_pad_m1),
            float(self.hs_pad_m2),
            float(self.hs_pad_m3),
            self.hs_jitter_ms,
        ]

    @classmethod
    def from_vector(cls, v: list[float]) -> MorphingParameters:
        return cls(
            morph_strength=max(0.0, min(1.0, float(v[0]))),
            size_bucket=max(16, int(round(v[1]))),
            timing_quantization_ms=max(0.0, min(20.0, float(v[2]))),
            dummy_rate=max(0.0, min(0.3, float(v[3]))),
            hs_pad_m1=max(0, min(500, int(round(v[4])))),
            hs_pad_m2=max(0, min(1000, int(round(v[5])))),
            hs_pad_m3=max(0, min(500, int(round(v[6])))),
            hs_jitter_ms=max(0.0, min(15.0, float(v[7]))),
        )


class EmpiricalTLSDistribution:
    """Empirical distribution estimator fit ONLY on Train Site TLS 1.3 flows."""

    def __init__(self) -> None:
        self.tx_sizes: list[int] = []
        self.rx_sizes: list[int] = []
        self.tx_gaps: list[float] = []
        self.rx_gaps: list[float] = []
        self.is_fit = False

    def fit_from_flows(self, tls_flows: list[FlowTrace]) -> None:
        """Estimate empirical distribution strictly from train direct TLS flows."""
        self.tx_sizes.clear()
        self.rx_sizes.clear()
        self.tx_gaps.clear()
        self.rx_gaps.clear()

        for f in tls_flows:
            if f.is_tunnel:
                continue  # Never learn from tunnel flows
            for p in f.packets:
                if p.direction == "TX":
                    self.tx_sizes.append(p.size)
                    if p.dt > 0:
                        self.tx_gaps.append(p.dt)
                else:
                    self.rx_sizes.append(p.size)
                    if p.dt > 0:
                        self.rx_gaps.append(p.dt)

        if not self.tx_sizes:
            self.tx_sizes = [240, 137, 500]
        if not self.rx_sizes:
            self.rx_sizes = [703, 1420, 1420]
        if not self.tx_gaps:
            self.tx_gaps = [0.005, 0.010]
        if not self.rx_gaps:
            self.rx_gaps = [0.001, 0.002]

        self.is_fit = True

    def sample_size(self, direction: str, rng: random.Random) -> int:
        pool = self.tx_sizes if direction == "TX" else self.rx_sizes
        return rng.choice(pool)

    def sample_gap(self, direction: str, rng: random.Random) -> float:
        pool = self.tx_gaps if direction == "TX" else self.rx_gaps
        return rng.choice(pool)


@dataclass
class MorphEvaluation:
    bandwidth_overhead: float
    latency_cost_ms: float
    packets_in: int
    packets_out: int


class TrafficMorpher:
    """Transforms raw flows towards the empirical TLS distribution."""

    def __init__(
        self,
        distribution: EmpiricalTLSDistribution,
        params: MorphingParameters | None = None,
        seed: int = 42,
    ) -> None:
        self.distribution = distribution
        self.params = params or MorphingParameters()
        self.rng = random.Random(seed)

    def morph_packet_size(self, raw_size: int, direction: str) -> int:
        """Morph packet size towards empirical TLS target size."""
        target_size = self.distribution.sample_size(direction, self.rng)
        # Interpolate between raw and target
        alpha = self.params.morph_strength
        interpolated = int(round((1.0 - alpha) * raw_size + alpha * target_size))

        # Size must be at least raw_size to avoid truncation
        morphed = max(raw_size, interpolated)

        # Bucket quantization
        if self.params.size_bucket > 0:
            morphed = (
                (morphed + self.params.size_bucket - 1)
                // self.params.size_bucket
                * self.params.size_bucket
            )

        return min(16384, morphed)

    def morph_packet_gap(self, raw_gap: float, direction: str) -> float:
        """Morph inter-packet timing gap."""
        target_gap = self.distribution.sample_gap(direction, self.rng)
        alpha = self.params.morph_strength
        interpolated = (1.0 - alpha) * raw_gap + alpha * target_gap

        if self.params.timing_quantization_ms > 0:
            step_s = self.params.timing_quantization_ms / 1000.0
            interpolated = round(interpolated / step_s) * step_s

        return max(0.0001, round(interpolated, 6))

    def morph_flow(self, flow: FlowTrace) -> tuple[FlowTrace, MorphEvaluation]:
        """Apply traffic morphing to a flow trace."""
        if not flow.is_tunnel:
            return flow, MorphEvaluation(0.0, 0.0, len(flow.packets), len(flow.packets))

        morphed_packets: list[PacketMeta] = []
        raw_bytes = sum(p.size for p in flow.packets)
        total_latency_ms = 0.0

        for idx, p in enumerate(flow.packets):
            # Handshake packet morphing (first 4 packets)
            if idx == 0:  # Noise Msg 1 (TX)
                m_size = p.size + self.params.hs_pad_m1
                m_dt = p.dt + (self.rng.uniform(0, self.params.hs_jitter_ms) / 1000.0)
            elif idx == 1:  # Noise Msg 2 (RX)
                m_size = p.size + self.params.hs_pad_m2
                m_dt = p.dt + (self.rng.uniform(0, self.params.hs_jitter_ms) / 1000.0)
            elif idx == 2:  # Noise Msg 3 (TX)
                m_size = p.size + self.params.hs_pad_m3
                m_dt = p.dt + (self.rng.uniform(0, self.params.hs_jitter_ms) / 1000.0)
            else:
                m_size = self.morph_packet_size(p.size, p.direction)
                m_dt = self.morph_packet_gap(p.dt, p.direction)
                total_latency_ms += max(0.0, (m_dt - p.dt) * 1000.0)

            morphed_packets.append(PacketMeta(size=m_size, direction=p.direction, dt=m_dt))

            # Dummy wire packet injection
            if idx > 3 and self.rng.random() < self.params.dummy_rate:
                dummy_dir: Literal["TX", "RX"] = "RX" if self.rng.random() < 0.7 else "TX"
                d_size = self.distribution.sample_size(dummy_dir, self.rng)
                d_dt = self.distribution.sample_gap(dummy_dir, self.rng)
                morphed_packets.append(PacketMeta(size=d_size, direction=dummy_dir, dt=d_dt))

        morphed_bytes = sum(p.size for p in morphed_packets)
        bw_overhead = (morphed_bytes - raw_bytes) / max(1, raw_bytes)

        return (
            FlowTrace(
                site_id=flow.site_id,
                category=flow.category,
                is_tunnel=True,
                packets=morphed_packets,
            ),
            MorphEvaluation(
                bandwidth_overhead=bw_overhead,
                latency_cost_ms=total_latency_ms,
                packets_in=len(flow.packets),
                packets_out=len(morphed_packets),
            ),
        )
