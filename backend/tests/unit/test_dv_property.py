"""Hypothesis property-based tests for Distance Vector convergence and optimality."""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from routelab.core.clock import VirtualClock
from routelab.metrics.oracle import RoutingOracle
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import generate_ring


@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    num_nodes=st.integers(min_value=3, max_value=6),
    split_horizon=st.booleans(),
    poison_reverse=st.booleans(),
)
@pytest.mark.asyncio
async def test_dv_ring_property(num_nodes: int, split_horizon: bool, poison_reverse: bool) -> None:
    """Property: On any connected ring topology, DV converges to loop-free shortest paths."""
    topo = generate_ring(num_nodes=num_nodes, default_cost=1.0)
    vclock = VirtualClock(seed=42)

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=lambda: DistanceVectorProtocol(
            config={
                "split_horizon": split_horizon,
                "poison_reverse": poison_reverse,
                "triggered_updates": True,
                "infinity": 16.0,
            }
        ),
        clock=vclock,
        quiescence_window_s=0.4,
    )

    await engine.start()
    while vclock.now() < 30.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record.is_converged is True

    tables = engine.get_all_routes()
    report = RoutingOracle.validate_tables(topo, tables)

    # In a ring without link failures, DV must always find optimal and loop-free paths
    assert report.is_optimal is True
    assert report.is_loop_free is True

    await engine.stop()
