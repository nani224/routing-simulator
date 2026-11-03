"""Statistical feature extraction for traffic flow metadata.

Extracts:
1. Size histograms (TX and RX bins)
2. Inter-packet timing gap histograms
3. Direction ratios (packet counts, byte volumes)
4. Burst statistics (mean/max burst lengths, burst durations)
"""

from __future__ import annotations

import math

import numpy as np

from phantomnet.data.traces import FlowTrace

# Histogram bin boundaries
SIZE_BINS = [0, 80, 160, 320, 540, 800, 1024, 1280, 1440, 1500, 2000]
GAP_BINS = [0.0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 10.0]


def extract_flow_features(trace: FlowTrace) -> np.ndarray:
    """Extract a normalized 42-dimensional feature vector from flow metadata."""
    packets = trace.packets
    if not packets:
        return np.zeros(42, dtype=np.float64)

    tx_sizes = [p.size for p in packets if p.direction == "TX"]
    rx_sizes = [p.size for p in packets if p.direction == "RX"]
    gaps = [p.dt for p in packets]

    # 1. Size histograms (10 bins each for TX and RX)
    tx_hist, _ = np.histogram(tx_sizes, bins=SIZE_BINS)
    rx_hist, _ = np.histogram(rx_sizes, bins=SIZE_BINS)

    tx_hist_norm = (
        tx_hist / float(len(tx_sizes)) if len(tx_sizes) > 0 else np.zeros(len(SIZE_BINS) - 1)
    )
    rx_hist_norm = (
        rx_hist / float(len(rx_sizes)) if len(rx_sizes) > 0 else np.zeros(len(SIZE_BINS) - 1)
    )

    # 2. Timing gap histogram (10 bins)
    gap_hist, _ = np.histogram(gaps, bins=GAP_BINS)
    gap_hist_norm = gap_hist / float(len(gaps)) if len(gaps) > 0 else np.zeros(len(GAP_BINS) - 1)

    # 3. Direction and volume ratios
    total_pkts = len(packets)
    tx_pkt_ratio = len(tx_sizes) / float(total_pkts)
    rx_pkt_ratio = len(rx_sizes) / float(total_pkts)

    total_tx_bytes = sum(tx_sizes)
    total_rx_bytes = sum(rx_sizes)
    total_bytes = max(1, total_tx_bytes + total_rx_bytes)
    tx_byte_ratio = total_tx_bytes / float(total_bytes)
    rx_byte_ratio = total_rx_bytes / float(total_bytes)

    # 4. Burst statistics (consecutive packets in the same direction)
    burst_sizes: list[int] = []
    current_dir = packets[0].direction
    current_burst_bytes = 0

    for p in packets:
        if p.direction == current_dir:
            current_burst_bytes += p.size
        else:
            burst_sizes.append(current_burst_bytes)
            current_dir = p.direction
            current_burst_bytes = p.size
    burst_sizes.append(current_burst_bytes)

    mean_burst = float(np.mean(burst_sizes)) if burst_sizes else 0.0
    max_burst = float(np.max(burst_sizes)) if burst_sizes else 0.0

    # 5. Global moments (normalized)
    tx_mean = float(np.mean(tx_sizes)) / 1500.0 if tx_sizes else 0.0
    tx_std = float(np.std(tx_sizes)) / 1500.0 if tx_sizes else 0.0
    rx_mean = float(np.mean(rx_sizes)) / 1500.0 if rx_sizes else 0.0
    rx_std = float(np.std(rx_sizes)) / 1500.0 if rx_sizes else 0.0

    mean_burst_norm = min(1.0, mean_burst / 15000.0)
    max_burst_norm = min(1.0, max_burst / 50000.0)
    total_pkts_log = math.log1p(total_pkts) / 10.0
    total_duration_log = math.log1p(trace.total_duration) / 10.0

    # Assemble 42-dim vector
    features = np.concatenate(
        [
            tx_hist_norm,  # 10
            rx_hist_norm,  # 10
            gap_hist_norm,  # 10
            np.array(
                [  # 12
                    tx_pkt_ratio,
                    rx_pkt_ratio,
                    tx_byte_ratio,
                    rx_byte_ratio,
                    mean_burst_norm,
                    max_burst_norm,
                    tx_mean,
                    tx_std,
                    rx_mean,
                    rx_std,
                    total_pkts_log,
                    total_duration_log,
                ],
                dtype=np.float64,
            ),
        ]
    )

    return features
