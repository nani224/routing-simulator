"""Verification of Distance Vector protocol against NetworkX ground-truth oracle."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.metrics.collector import MetricsCollector
from routelab.metrics.oracle import RoutingOracle
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_6_node, preset_8_node


@pytest.mark.asyncio
async def test_dv_convergence_and_oracle_on_6_node() -> None:
    topo = preset_6_node()
    vclock = VirtualClock()

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=lambda: DistanceVectorProtocol(
            config={
                "split_horizon": True,
                "poison_reverse": True,
                "triggered_updates": True,
                "infinity": 16.0,
            }
        ),
        clock=vclock,
        quiescence_window_s=0.5,
    )

    await engine.start()

    # Step virtual time until initial convergence
    step_limit = 50.0  # seconds
    converged = False
    while vclock.now() < step_limit:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            converged = True
            break

    assert converged is True
    assert engine.convergence_record.is_converged is True

    # Validate against Oracle
    active_tables = engine.get_all_routes()
    report = RoutingOracle.validate_tables(topo, active_tables)

    assert report.is_optimal is True
    assert report.is_loop_free is True
    assert len(report.loops_detected) == 0
    assert len(report.blackholes_detected) == 0
    assert report.average_path_stretch == pytest.approx(1.0)

    # Inject link failure (A <-> B)
    engine.inject_link_state("A", "B", up=False)

    # Run until reconvergence
    reconverged = False
    reconv_start = vclock.now()
    while vclock.now() < (reconv_start + step_limit):
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            reconverged = True
            break

    assert reconverged is True

    # Validate post-failure state against new oracle
    # Remove edge A-B in a test copy of topology to check new shortest paths
    topo_post_fail = preset_6_node()
    topo_post_fail.links = [
        lnk
        for lnk in topo_post_fail.links
        if not (
            (lnk.source == "A" and lnk.target == "B")
            or (lnk.source == "B" and lnk.target == "A")
        )
    ]

    post_fail_tables = engine.get_all_routes()
    post_report = RoutingOracle.validate_tables(topo_post_fail, post_fail_tables)

    assert post_report.is_optimal is True
    assert post_report.is_loop_free is True
    assert len(post_report.loops_detected) == 0

    # Collect metrics
    metrics = MetricsCollector.collect_from_engine(engine, "distance_vector", post_report)
    assert metrics.convergence_time_s > 0.0
    assert metrics.total_control_messages > 0
    assert metrics.is_optimal is True

    # Test CSV and JSON export
    csv_str = MetricsCollector.export_csv([metrics])
    assert "distance_vector" in csv_str

    json_str = MetricsCollector.export_json([metrics])
    assert "Course-6-Node-Benchmark" in json_str

    await engine.stop()


@pytest.mark.asyncio
async def test_dv_on_8_node_mesh() -> None:
    topo = preset_8_node()
    vclock = VirtualClock()

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=DistanceVectorProtocol,
        clock=vclock,
        quiescence_window_s=0.5,
    )

    await engine.start()
    while vclock.now() < 60.0:
        await vclock.run_until(vclock.now() + 0.2)
        if engine.check_convergence():
            break

    assert engine.convergence_record.is_converged is True
    tables = engine.get_all_routes()
    report = RoutingOracle.validate_tables(topo, tables)

    assert report.is_optimal is True
    assert report.is_loop_free is True

    await engine.stop()
