"""Unit tests for logical LinkEmulator with delay, jitter, loss, and down states."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.core.link import LinkEmulator
from routelab.core.packet import Packet


@pytest.mark.asyncio
async def test_link_virtual_clock_delivery() -> None:
    vclock = VirtualClock(seed=42)
    link = LinkEmulator(
        node_a="A",
        node_b="B",
        clock=vclock,
        cost=2.0,
        latency_ms=50.0,
        jitter_ms=0.0,
        loss_rate=0.0,
    )

    delivered: list[Packet] = []
    pkt = Packet(
        src="A",
        dst="B",
        proto="dv",
        seq=1,
        ttl=16,
        timestamp=0.0,
        payload={"msg": "hello"},
    )

    success = link.transmit(pkt, delivery_callback=lambda p: delivered.append(p))
    assert success is True
    assert link.stats.packets_sent == 1
    assert len(delivered) == 0

    # Advance time to 40ms -> packet should not be delivered yet
    await vclock.run_until(0.040)
    assert len(delivered) == 0

    # Advance time to 55ms -> packet should be delivered
    await vclock.run_until(0.055)
    assert len(delivered) == 1
    assert delivered[0].seq == 1
    assert link.stats.packets_delivered == 1


@pytest.mark.asyncio
async def test_link_loss_rate() -> None:
    vclock = VirtualClock(seed=10)
    # 100% loss link
    link = LinkEmulator(
        node_a="A",
        node_b="B",
        clock=vclock,
        cost=1.0,
        latency_ms=10.0,
        loss_rate=1.0,
    )

    delivered: list[Packet] = []
    pkt = Packet(src="A", dst="B", proto="test", seq=1, ttl=16, timestamp=0.0, payload={})
    success = link.transmit(pkt, delivery_callback=lambda p: delivered.append(p))

    assert success is False
    assert link.stats.packets_dropped_loss == 1
    assert link.stats.packets_delivered == 0


@pytest.mark.asyncio
async def test_link_down_drops_packets() -> None:
    vclock = VirtualClock()
    link = LinkEmulator(node_a="A", node_b="B", clock=vclock)
    link.is_up = False

    delivered: list[Packet] = []
    pkt = Packet(src="A", dst="B", proto="test", seq=1, ttl=16, timestamp=0.0, payload={})
    success = link.transmit(pkt, delivery_callback=lambda p: delivered.append(p))

    assert success is False
    assert link.stats.packets_dropped_down == 1
    assert len(delivered) == 0
