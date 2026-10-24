"""Unit tests for Link State (OSPF-like) protocol with LSA flooding and Oracle validation."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.metrics.oracle import RoutingOracle
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_6_node, preset_8_node


@pytest.mark.asyncio
async def test_ls_convergence_and_oracle_on_6_node() -> None:
    topo = preset_6_node()
    vclock = VirtualClock()

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=LinkStateProtocol,
        clock=vclock,
        quiescence_window_s=0.3,
    )

    await engine.start()

    # Step virtual time until initial convergence
    while vclock.now() < 30.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record.is_converged is True

    # Validate tables against NetworkX oracle
    tables = engine.get_all_routes()
    report = RoutingOracle.validate_tables(topo, tables)

    assert report.is_optimal is True
    assert report.is_loop_free is True
    assert len(report.loops_detected) == 0
    assert len(report.blackholes_detected) == 0
    assert report.average_path_stretch == pytest.approx(1.0)

    # Inject link failure (C <-> D)
    engine.inject_link_state("C", "D", up=False)

    # Reconverge
    reconv_start = vclock.now()
    while vclock.now() < (reconv_start + 30.0):
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    topo_post_fail = preset_6_node()
    topo_post_fail.links = [
        lnk
        for lnk in topo_post_fail.links
        if not (
            (lnk.source == "C" and lnk.target == "D") or (lnk.source == "D" and lnk.target == "C")
        )
    ]

    post_tables = engine.get_all_routes()
    post_report = RoutingOracle.validate_tables(topo_post_fail, post_tables)

    assert post_report.is_optimal is True
    assert post_report.is_loop_free is True

    await engine.stop()


@pytest.mark.asyncio
async def test_ls_on_8_node_mesh() -> None:
    topo = preset_8_node()
    vclock = VirtualClock()

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=LinkStateProtocol,
        clock=vclock,
        quiescence_window_s=0.3,
    )

    await engine.start()
    while vclock.now() < 30.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record.is_converged is True
    tables = engine.get_all_routes()
    report = RoutingOracle.validate_tables(topo, tables)

    assert report.is_optimal is True
    assert report.is_loop_free is True

    await engine.stop()
