"""High-performance binary packet protocol representation for RouteLab.

Uses msgpack binary serialization with strict byte accounting and slot-based dataclasses.
Eliminates JSON overhead on the hot path.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

import msgpack


class PacketType(enum.StrEnum):
    """Packet categories recognized by the simulation framework."""

    CONTROL = "control"
    DATA = "data"
    PROBE = "probe"
    ATTACK = "attack"


@dataclass(slots=True)
class Packet:
    """Network packet exchanged across links and router sockets.

    Attributes:
        src: Source node identifier.
        dst: Destination node identifier (or BROADCAST_ID).
        proto: Protocol name (e.g., 'dv', 'ls', 'bgp_lite').
        seq: Monotonically increasing sequence number per node.
        ttl: Time To Live hops remaining.
        timestamp: Time of packet creation/dispatch.
        payload: Protocol-specific message dictionary.
        packet_type: Packet category (CONTROL, DATA, PROBE, ATTACK).
        byte_size: Size in bytes of encoded wire payload (cached or computed).
    """

    src: str
    dst: str
    proto: str
    seq: int
    ttl: int
    timestamp: float
    payload: dict[str, Any]
    packet_type: PacketType = PacketType.CONTROL
    byte_size: int = field(default=0)

    BROADCAST_ID: str = "*"

    def is_broadcast(self) -> bool:
        return self.dst == self.BROADCAST_ID

    def to_bytes(self) -> bytes:
        """Serialize packet into compact msgpack binary format."""
        raw_dict = {
            "s": self.src,
            "d": self.dst,
            "p": self.proto,
            "n": self.seq,
            "t": self.ttl,
            "ts": self.timestamp,
            "ty": self.packet_type.value,
            "pl": self.payload,
        }
        encoded: bytes = msgpack.packb(raw_dict, use_bin_type=True)
        self.byte_size = len(encoded)
        return encoded

    @classmethod
    def from_bytes(cls, data: bytes) -> Packet:
        """Deserialize packet from msgpack binary payload."""
        unpacked = msgpack.unpackb(data, raw=False)
        return cls(
            src=unpacked["s"],
            dst=unpacked["d"],
            proto=unpacked["p"],
            seq=unpacked["n"],
            ttl=unpacked["t"],
            timestamp=unpacked["ts"],
            packet_type=PacketType(unpacked.get("ty", PacketType.CONTROL.value)),
            payload=unpacked["pl"],
            byte_size=len(data),
        )

    def decrement_ttl(self) -> bool:
        """Decrement TTL by 1. Returns True if packet is still alive (ttl > 0)."""
        self.ttl -= 1
        return self.ttl > 0
