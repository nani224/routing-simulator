"""Metadata-only flow capture, site generation, and disjoint site partitioning.

Constraints:
- Preserves ONLY metadata (size, direction, delta timestamp). Never payloads.
- Splits by SITE (train/val/test sites disjoint) to prevent feature leakage.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PacketMeta:
    """Metadata-only observation of a single packet frame."""

    size: int
    direction: Literal["TX", "RX"]
    dt: float  # Inter-packet arrival delta in seconds


@dataclass
class FlowTrace:
    """A captured sequence of packet metadata for a single session/site flow."""

    site_id: str
    category: str
    is_tunnel: bool
    packets: list[PacketMeta]

    @property
    def total_bytes(self) -> int:
        return sum(p.size for p in self.packets)

    @property
    def total_duration(self) -> float:
        return sum(p.dt for p in self.packets)


# 30 distinct realistic site identities across 5 categories
SITES: list[dict[str, str]] = [
    # Video Streaming (heavy RX, large 1420-1500 byte bursts, small TX ACKs)
    {"site_id": "video-stream-01", "category": "video"},
    {"site_id": "video-stream-02", "category": "video"},
    {"site_id": "video-stream-03", "category": "video"},
    {"site_id": "video-stream-04", "category": "video"},
    {"site_id": "video-stream-05", "category": "video"},
    {"site_id": "video-stream-06", "category": "video"},
    # Tech & Developer Docs (balanced interactive, 400-800B JSON/HTML chunks)
    {"site_id": "tech-dev-01", "category": "tech"},
    {"site_id": "tech-dev-02", "category": "tech"},
    {"site_id": "tech-dev-03", "category": "tech"},
    {"site_id": "tech-dev-04", "category": "tech"},
    {"site_id": "tech-dev-05", "category": "tech"},
    {"site_id": "tech-dev-06", "category": "tech"},
    # News & Editorial (bursty images/CSS, initial heavy burst, idle read gaps)
    {"site_id": "news-media-01", "category": "news"},
    {"site_id": "news-media-02", "category": "news"},
    {"site_id": "news-media-03", "category": "news"},
    {"site_id": "news-media-04", "category": "news"},
    {"site_id": "news-media-05", "category": "news"},
    {"site_id": "news-media-06", "category": "news"},
    # E-Commerce & Shopping (frequent AJAX requests, POST payloads, medium RX)
    {"site_id": "shop-retail-01", "category": "shopping"},
    {"site_id": "shop-retail-02", "category": "shopping"},
    {"site_id": "shop-retail-03", "category": "shopping"},
    {"site_id": "shop-retail-04", "category": "shopping"},
    {"site_id": "shop-retail-05", "category": "shopping"},
    {"site_id": "shop-retail-06", "category": "shopping"},
    # Cloud Collaboration & Chat (frequent tiny 64-256B keepalives/typing packets)
    {"site_id": "cloud-chat-01", "category": "collab"},
    {"site_id": "cloud-chat-02", "category": "collab"},
    {"site_id": "cloud-chat-03", "category": "collab"},
    {"site_id": "cloud-chat-04", "category": "collab"},
    {"site_id": "cloud-chat-05", "category": "collab"},
    {"site_id": "cloud-chat-06", "category": "collab"},
]


def generate_synthetic_site_flow(
    site_id: str,
    category: str,
    is_tunnel: bool,
    seed: int,
    num_packets: int = 120,
) -> FlowTrace:
    """Generate a realistic packet metadata sequence for a specific site."""
    rng = random.Random(seed)
    packets: list[PacketMeta] = []

    # Initial handshake signatures (ClientHello ~517B, ServerHello + cert ~1420B)
    packets.append(PacketMeta(size=517 if not is_tunnel else 533, direction="TX", dt=0.0))
    packets.append(PacketMeta(size=1420 if not is_tunnel else 1436, direction="RX", dt=0.015))
    packets.append(PacketMeta(size=64, direction="TX", dt=0.005))

    for _ in range(num_packets - 3):
        if category == "video":
            # Video: 85% RX MTU packets (1420-1500B), 15% TX ACKs (64-128B)
            if rng.random() < 0.85:
                direction: Literal["TX", "RX"] = "RX"
                size = rng.choice([1420, 1440, 1480, 1500])
                dt = rng.expovariate(120.0)  # Dense burst
            else:
                direction = "TX"
                size = rng.choice([64, 72, 128])
                dt = rng.expovariate(80.0)
        elif category == "tech":
            # Tech: balanced bidirectional JSON & API calls
            direction = "TX" if rng.random() < 0.4 else "RX"
            size = (
                rng.randint(128, 650) if direction == "TX" else rng.choice([256, 512, 1024, 1420])
            )
            dt = rng.expovariate(40.0)
        elif category == "collab":
            # Collab: small keepalives and bursts
            direction = "TX" if rng.random() < 0.5 else "RX"
            size = rng.choice([64, 96, 140, 220, 380])
            dt = rng.expovariate(25.0)
        else:
            # News/Shopping: bursty page load
            direction = "TX" if rng.random() < 0.3 else "RX"
            size = rng.randint(200, 1450) if direction == "RX" else rng.choice([64, 128, 320])
            dt = rng.expovariate(50.0)

        # Tunnel encapsulation adds length framing (16B header + 16B Poly1305 MAC)
        if is_tunnel:
            size += 32

        packets.append(PacketMeta(size=size, direction=direction, dt=round(dt, 5)))

    return FlowTrace(
        site_id=site_id,
        category=category,
        is_tunnel=is_tunnel,
        packets=packets,
    )


def partition_disjoint_sites(
    seed: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Partition the 30 sites into disjoint Train (18), Val (6), and Test (6) sets.

    Crucial: Site IDs never overlap across splits, strictly preventing feature leakage.
    """
    rng = random.Random(seed)
    # Group sites by category to guarantee category balance across splits
    categories = sorted({s["category"] for s in SITES})
    train_sites: list[dict[str, str]] = []
    val_sites: list[dict[str, str]] = []
    test_sites: list[dict[str, str]] = []

    for cat in categories:
        cat_sites = [s for s in SITES if s["category"] == cat]
        rng.shuffle(cat_sites)
        # 4 train, 1 val, 1 test per category
        train_sites.extend(cat_sites[:4])
        val_sites.append(cat_sites[4])
        test_sites.append(cat_sites[5])

    return train_sites, val_sites, test_sites
