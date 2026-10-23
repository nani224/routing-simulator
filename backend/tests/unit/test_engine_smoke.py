"""Unit and smoke tests for SimulationEngine lifecycle, events, and mutations."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_6_node


class SimpleEchoProtocol(RoutingProtocol):
    name = "simple_echo"

    def on_start(self, ctx: ProtocolContext) -> None:
        ctx.broadcast({"msg": "ping"})

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, object]) -> None:
        pass

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        pass

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return [RouteEntry(destination="target", next_hop="local", cost=1.0)]


@pytest.mark.asyncio
async def test_simulation_engine_lifecycle_and_mutations() -> None:
    topo = preset_6_node()
    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=SimpleEchoProtocol,
        clock=vclock,
        quiescence_window_s=0.2,
    )

    deltas: list[dict[str, object]] = []
    engine.add_delta_listener(lambda d: deltas.append(d))

    await engine.start()
    assert len(engine.nodes) == 6

    # Step through virtual time to deliver on_start broadcast messages
    await vclock.run_until(0.05)
    assert engine.event_store.count() >= 0

    # Inject link failure
    engine.inject_link_state("A", "B", up=False)
    assert engine.links["A<->B"].is_up is False

    # Inject link cost change
    engine.inject_link_cost("A", "F", cost=15.0)
    assert engine.links["A<->F"].cost == 15.0

    # Inject node crash and recovery
    engine.inject_node_crash("C")
    assert engine.nodes["C"].status.value == "crashed"

    engine.inject_node_recover("C")
    assert engine.nodes["C"].status.value == "running"

    # Advance time beyond quiescence window
    await vclock.run_until(1.0)
    is_conv = engine.check_convergence()
    assert is_conv is True
    assert engine.convergence_record.is_converged is True

    # State snapshot
    state = engine.get_full_state()
    assert "nodes" in state
    assert "links" in state
    assert "routes" in state
    assert len(state["nodes"]) == 6

    await engine.stop()
