"""Comprehensive regression test suite for Phase 1 protocol and transport fixes."""

from __future__ import annotations

import pytest
from routelab.core.clock import VirtualClock
from routelab.protocols.bgp_lite import BGPLiteProtocol
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.protocols.flooding import FloodingProtocol
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.model import Topology, TopologyLink, TopologyNode


@pytest.mark.asyncio
async def test_dv_hold_down_suppression() -> None:
    """Verify hold-down suppresses immediate alternate path adoption during failure."""
    topo = Topology(name="Test-HoldDown")
    topo.add_node(TopologyNode(id="A", x=0, y=0))
    topo.add_node(TopologyNode(id="B", x=100, y=0))
    topo.add_node(TopologyNode(id="C", x=200, y=0))

    # A - B (cost 1), B - C (cost 1), A - C (cost 10)
    topo.add_link(TopologyLink(source="A", target="B", cost=1.0))
    topo.add_link(TopologyLink(source="B", target="C", cost=1.0))
    topo.add_link(TopologyLink(source="A", target="C", cost=10.0))

    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=lambda _nid: DistanceVectorProtocol({"hold_down_duration_s": 5.0}),
        clock=vclock,
        quiescence_window_s=0.2,
    )

    await engine.start()
    while vclock.now() < 5.0 and not engine.check_convergence():
        await vclock.run_until(vclock.now() + 0.05)

    # In A, route to C should be via B with cost 2
    table_a = {r.destination: r for r in engine.nodes["A"].get_table()}
    assert table_a["C"].next_hop == "B"
    assert table_a["C"].cost == 2.0

    # Break B-C link
    engine.inject_link_state("B", "C", up=False)
    await vclock.run_until(vclock.now() + 0.1)

    # In B, route to C must enter hold-down
    b_internal = engine.nodes["B"]._protocol.table  # type: ignore[attr-defined]
    assert b_internal["C"].in_hold_down is True
    assert b_internal["C"].cost >= 16.0

    await engine.stop()


@pytest.mark.asyncio
async def test_ls_reliable_ack_and_sync() -> None:
    """Verify LinkState generates LSAcks and synchronizes LSDB on node start."""
    topo = Topology(name="Test-LSAck")
    topo.add_node(TopologyNode(id="R1", x=0, y=0))
    topo.add_node(TopologyNode(id="R2", x=100, y=0))
    topo.add_link(TopologyLink(source="R1", target="R2", cost=2.0))

    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=LinkStateProtocol,
        clock=vclock,
        quiescence_window_s=0.2,
    )

    await engine.start()
    while vclock.now() < 3.0 and not engine.check_convergence():
        await vclock.run_until(vclock.now() + 0.05)

    p1 = engine.nodes["R1"]._protocol  # type: ignore[attr-defined]
    p2 = engine.nodes["R2"]._protocol  # type: ignore[attr-defined]
    assert "R1" in p2.lsdb
    assert "R2" in p1.lsdb
    assert len(p1.pending_acks) == 0  # All acknowledged

    await engine.stop()


@pytest.mark.asyncio
async def test_bgp_withdrawals_on_link_down() -> None:
    """Verify BGP explicitly sends withdrawals when routes become unreachable."""
    topo = Topology(name="Test-BGP-Withdrawal")
    topo.add_node(TopologyNode(id="AS1", x=0, y=0))
    topo.add_node(TopologyNode(id="AS2", x=100, y=0))
    topo.add_node(TopologyNode(id="AS3", x=200, y=0))

    topo.add_link(TopologyLink(source="AS1", target="AS2", cost=1.0))
    topo.add_link(TopologyLink(source="AS2", target="AS3", cost=1.0))

    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=lambda nid: BGPLiteProtocol({"as_number": nid}),
        clock=vclock,
        quiescence_window_s=0.2,
    )

    await engine.start()
    while vclock.now() < 5.0 and not engine.check_convergence():
        await vclock.run_until(vclock.now() + 0.05)

    # AS1 should know route to AS3 via AS2
    t1 = {r.destination: r for r in engine.nodes["AS1"].get_table()}
    assert "AS3" in t1
    assert t1["AS3"].next_hop == "AS2"

    # Break link AS2-AS3
    engine.inject_link_state("AS2", "AS3", up=False)
    while vclock.now() < 8.0 and not engine.check_convergence():
        await vclock.run_until(vclock.now() + 0.05)

    # AS1 should now have route to AS3 withdrawn
    t1_after = {r.destination: r for r in engine.nodes["AS1"].get_table()}
    assert "AS3" not in t1_after

    await engine.stop()


@pytest.mark.asyncio
async def test_flooding_link_cost_and_invalidation() -> None:
    """Verify Flooding tracks link costs and invalidates routes on link failure."""
    topo = Topology(name="Test-Flooding")
    topo.add_node(TopologyNode(id="F1", x=0, y=0))
    topo.add_node(TopologyNode(id="F2", x=100, y=0))
    topo.add_link(TopologyLink(source="F1", target="F2", cost=5.0))

    vclock = VirtualClock()
    engine = SimulationEngine(
        topology=topo,
        protocol_factory=FloodingProtocol,
        clock=vclock,
        quiescence_window_s=0.2,
    )

    await engine.start()
    await vclock.run_until(vclock.now() + 1.0)

    t1 = {r.destination: r for r in engine.nodes["F1"].get_table()}
    assert "F2" in t1
    assert t1["F2"].cost == 5.0

    # Fail link
    engine.inject_link_state("F1", "F2", up=False)
    await vclock.run_until(vclock.now() + 0.2)

    t1_after = {r.destination: r for r in engine.nodes["F1"].get_table()}
    assert "F2" not in t1_after

    await engine.stop()
