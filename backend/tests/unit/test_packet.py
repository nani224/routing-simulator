"""Unit tests for high-performance binary packet serialization."""

import pytest
from routelab.core.packet import Packet, PacketType


def test_packet_creation_and_slots() -> None:
    pkt = Packet(
        src="R1",
        dst="R2",
        proto="dv",
        seq=1,
        ttl=16,
        timestamp=10.5,
        payload={"vectors": {"R3": 5}},
        packet_type=PacketType.CONTROL,
    )
    assert pkt.src == "R1"
    assert pkt.dst == "R2"
    assert pkt.proto == "dv"
    assert not pkt.is_broadcast()


def test_packet_msgpack_roundtrip() -> None:
    pkt = Packet(
        src="A",
        dst="*",
        proto="ls",
        seq=42,
        ttl=32,
        timestamp=100.123456,
        payload={"lsa": {"adv_router": "A", "links": [["B", 1.0], ["C", 2.0]]}},
        packet_type=PacketType.CONTROL,
    )

    encoded = pkt.to_bytes()
    assert isinstance(encoded, bytes)
    assert pkt.byte_size == len(encoded)
    assert pkt.is_broadcast()

    decoded = Packet.from_bytes(encoded)
    assert decoded.src == "A"
    assert decoded.dst == "*"
    assert decoded.proto == "ls"
    assert decoded.seq == 42
    assert decoded.ttl == 32
    assert decoded.timestamp == pytest.approx(100.123456)
    assert decoded.packet_type == PacketType.CONTROL
    assert decoded.payload == pkt.payload
    assert decoded.byte_size == len(encoded)


def test_packet_ttl_decrement() -> None:
    pkt = Packet(
        src="A",
        dst="B",
        proto="test",
        seq=1,
        ttl=2,
        timestamp=0.0,
        payload={},
    )
    assert pkt.decrement_ttl() is True
    assert pkt.ttl == 1
    assert pkt.decrement_ttl() is False
    assert pkt.ttl == 0
