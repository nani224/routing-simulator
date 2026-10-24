"""Unit tests for BGP-Lite protocol: AS_PATH loop prevention, LOCAL_PREF selection, withdrawals."""

import pytest
from routelab.core.clock import VirtualClock
from routelab.core.events import EventStore
from routelab.protocols.bgp_lite import BGPLiteProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_bgp_tier1


@pytest.mark.asyncio
async def test_bgp_lite_tier1_convergence() -> None:
    topo = preset_bgp_tier1()
    vclock = VirtualClock()
    store = EventStore()

    def make_bgp(node_id: str) -> BGPLiteProtocol:
        # Extract ASN from node name e.g. AS100_R1 -> 100
        asn = node_id.split("_")[0].replace("AS", "")
        return BGPLiteProtocol(config={"as_number": asn})

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=make_bgp,
        clock=vclock,
        event_store=store,
        quiescence_window_s=0.3,
        seed=42,
    )

    await engine.start()
    while vclock.now() < 10.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record is not None
    assert engine.convergence_record.is_converged

    # Check routing table of AS100_R1
    r1 = engine.nodes["AS100_R1"]
    table = r1.get_table()
    dests = {r.destination: r for r in table}

    assert "AS100_R1" in dests
    assert "AS200_R1" in dests
    assert "AS300_R1" in dests
    assert "AS400_R1" in dests


@pytest.mark.asyncio
async def test_bgp_lite_local_pref_policy_override() -> None:
    """Verify that higher LOCAL_PREF overrides a shorter AS_PATH."""
    topo = preset_bgp_tier1()
    vclock = VirtualClock()
    store = EventStore()

    def make_bgp(node_id: str) -> BGPLiteProtocol:
        asn = node_id.split("_")[0].replace("AS", "")
        if node_id == "AS100_R1":
            # Prefer AS400_R1 (longer path) over AS200_R1 by giving AS400_R1 local_pref 300
            return BGPLiteProtocol(
                config={
                    "as_number": asn,
                    "peer_policies": {
                        "AS400_R1": {"local_pref": 300},
                        "AS200_R1": {"local_pref": 100},
                    },
                }
            )
        return BGPLiteProtocol(config={"as_number": asn})

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=make_bgp,
        clock=vclock,
        event_store=store,
        quiescence_window_s=0.3,
        seed=42,
    )

    await engine.start()
    while vclock.now() < 10.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record is not None
    assert engine.convergence_record.is_converged

    # Destination AS300_R1 should be reached via AS400_R1 due to high local_pref
    r1 = engine.nodes["AS100_R1"]
    table = r1.get_table()
    route_to_300 = next(r for r in table if r.destination == "AS300_R1")
    assert route_to_300.next_hop == "AS400_R1"


@pytest.mark.asyncio
async def test_bgp_lite_link_failure_withdrawal() -> None:
    """Verify route withdrawal and reconvergence when primary BGP link drops."""
    topo = preset_bgp_tier1()
    vclock = VirtualClock()
    store = EventStore()

    def make_bgp(node_id: str) -> BGPLiteProtocol:
        asn = node_id.split("_")[0].replace("AS", "")
        return BGPLiteProtocol(config={"as_number": asn})

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=make_bgp,
        clock=vclock,
        event_store=store,
        quiescence_window_s=0.3,
        seed=42,
    )

    # Schedule link drop
    engine.add_event(
        timestamp=0.5,
        action="link_down",
        params={"u": "AS100_R1", "v": "AS200_R1"},
    )

    await engine.start()
    while vclock.now() < 10.0:
        await vclock.run_until(vclock.now() + 0.1)
        if engine.check_convergence():
            break

    assert engine.convergence_record is not None
    assert engine.convergence_record.is_converged

    # Route to AS200_R1 should now route through AS400_R1
    r1 = engine.nodes["AS100_R1"]
    table = r1.get_table()
    route_to_200 = next(r for r in table if r.destination == "AS200_R1")
    assert route_to_200.next_hop == "AS400_R1"
