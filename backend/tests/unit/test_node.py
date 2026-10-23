"""Unit tests for RouterNode lifecycle, real UDP sockets, and protocol context."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.core.events import EventStore
from routelab.core.link import LinkEmulator
from routelab.core.node import NodeStatus, RouterNode
from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol


class MockFlappingProtocol(RoutingProtocol):
    name = "mock_flapping"

    def __init__(self, config: dict[str, object] | None = None) -> None:
        super().__init__(config)
        self.routes: list[RouteEntry] = []

    def on_start(self, _ctx: ProtocolContext) -> None:
        self.routes = [RouteEntry(destination="X", next_hop="A", cost=1.0)]

    def on_message(self, _ctx: ProtocolContext, _src: str, _msg: dict[str, object]) -> None:
        # Flap route cost
        curr_cost = self.routes[0].cost if self.routes else 1.0
        self.routes = [RouteEntry(destination="X", next_hop="B", cost=curr_cost + 1.0)]

    def on_link_change(self, _ctx: ProtocolContext, _nbr: str, _cost: float, _up: bool) -> None:
        pass

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return list(self.routes)


@pytest.mark.asyncio
async def test_node_udp_socket_binding_and_lifecycle() -> None:
    vclock = VirtualClock()
    store = EventStore()
    node = RouterNode("R1", clock=vclock, event_store=store, bind_port=0)

    assert node.status == NodeStatus.STOPPED

    await node.start()
    assert node.status == NodeStatus.RUNNING
    assert node.port > 0

    desc = node.describe_state()
    assert desc["status"] == "running"
    assert desc["port"] == node.port

    await node.stop()
    assert node.status == NodeStatus.STOPPED


@pytest.mark.asyncio
async def test_node_link_attachment_and_send() -> None:
    vclock = VirtualClock()
    node_a = RouterNode("A", clock=vclock)
    node_b = RouterNode("B", clock=vclock)

    node_a._network_router_lookup = lambda target: node_b if target == "B" else None  # type: ignore[attr-defined]
    node_b._network_router_lookup = lambda target: node_a if target == "A" else None  # type: ignore[attr-defined]

    proto_a = MockFlappingProtocol()
    proto_b = MockFlappingProtocol()
    node_a.set_protocol(proto_a)
    node_b.set_protocol(proto_b)

    link_ab = LinkEmulator(node_a="A", node_b="B", clock=vclock, latency_ms=10.0)
    node_a.attach_link("B", link_ab)
    node_b.attach_link("A", link_ab)

    await node_a.start()
    await node_b.start()

    # Node A sends to Node B
    node_a.send("B", {"greeting": "hello_from_a"})
    assert node_a.packets_sent == 1

    # Advance time to deliver packet
    await vclock.run_until(0.015)

    assert node_b.packets_received == 1
    # Check that proto_b received message and triggered a flap
    assert node_b.flaps_count >= 1

    await node_a.stop()
    await node_b.stop()


@pytest.mark.asyncio
async def test_node_crash_and_recover() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_CRASH", clock=vclock)
    proto = MockFlappingProtocol()
    node.set_protocol(proto)

    await node.start()
    assert node.status == NodeStatus.RUNNING

    node.crash()
    assert node.status == NodeStatus.CRASHED

    # Sending while crashed is silently ignored
    node.send("NON_EXISTENT", {"test": 1})
    assert node.packets_sent == 0

    node.recover()
    assert node.status == NodeStatus.RUNNING

    await node.stop()


@pytest.mark.asyncio
async def test_node_timer_scheduling() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_TIMER", clock=vclock)

    fired_timers: list[str] = []

    class TimerProtocol(MockFlappingProtocol):
        def on_timer(self, _ctx: ProtocolContext, timer_id: str) -> None:
            fired_timers.append(timer_id)

    node.set_protocol(TimerProtocol())
    await node.start()

    node.set_timer("heartbeat", 50.0)  # 50 ms
    node.set_timer("to_cancel", 100.0)
    node.cancel_timer("to_cancel")

    await vclock.run_until(0.060)
    assert fired_timers == ["heartbeat"]

    await node.stop()
