"""Advanced unit tests for SimulationEngine and LinkEmulator realtime behaviors."""

import pytest
from routelab.core.clock import RealtimeClock, VirtualClock
from routelab.core.link import LinkEmulator
from routelab.core.node import RouterNode
from routelab.core.packet import Packet
from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_6_node


class DummyBroadcasterProtocol(RoutingProtocol):
    name = "dummy_broadcaster"

    def on_start(self, ctx: ProtocolContext) -> None:
        ctx.broadcast({"hello": "all"})

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, object]) -> None:
        pass

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        pass

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return []


@pytest.mark.asyncio
async def test_link_realtime_worker_start_stop() -> None:
    clock = RealtimeClock(initial_speed=5.0)
    link = LinkEmulator(
        node_a="A",
        node_b="B",
        clock=clock,
        latency_ms=10.0,
    )
    link.start()
    assert link._running is True
    assert link._worker_task is not None

    delivered: list[Packet] = []
    pkt = Packet(src="A", dst="B", proto="test", seq=1, ttl=16, timestamp=clock.now(), payload={})
    link.transmit(pkt, delivery_callback=lambda p: delivered.append(p))

    await clock.sleep(0.04)  # 40ms sim time
    assert len(delivered) == 1

    await link.stop()
    assert link._running is False
    assert link._worker_task is None


@pytest.mark.asyncio
async def test_engine_scheduled_events_execution() -> None:
    topo = preset_6_node()
    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=DummyBroadcasterProtocol,
        clock=vclock,
        quiescence_window_s=0.1,
    )

    # Schedule failure events in virtual time
    engine.add_event(0.05, "link_down", {"u": "A", "v": "B"})
    engine.add_event(0.10, "cost_change", {"u": "B", "v": "C", "cost": 99.0})
    engine.add_event(0.15, "node_crash", {"node_id": "D"})
    engine.add_event(0.20, "node_recover", {"node_id": "D"})
    engine.add_event(0.25, "link_up", {"u": "A", "v": "B"})

    await engine.start()
    await vclock.run_until(0.30)

    # All scheduled events should be executed
    assert all(e.executed for e in engine._scheduled_events)

    # Link A<->B should be up again
    assert engine.links["A<->B"].is_up is True
    # Link B<->C cost should be 99.0
    assert engine.links["B<->C"].cost == 99.0

    routes = engine.get_all_routes()
    assert len(routes) == 6

    await engine.stop()


def test_node_malformed_datagram_handling() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_MAL", clock=vclock)
    # Feed garbage bytes to raw datagram handler - must not throw
    node.handle_incoming_raw_datagram(b"non_msgpack_garbage_data", ("127.0.0.1", 12345))
    assert node.packets_received == 0
