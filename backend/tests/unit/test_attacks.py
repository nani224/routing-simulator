"""Unit tests for Count-to-Infinity reproduction, Poisoning Attacks, and Mitigations."""

import pytest
from routelab.attacks.mitigation import SecureDistanceVectorProtocol
from routelab.attacks.poisoning import PoisoningAttackProtocol
from routelab.core.clock import VirtualClock
from routelab.core.events import EventStore
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import preset_6_node, preset_count_to_infinity


@pytest.mark.asyncio
async def test_count_to_infinity_mitigation_comparison() -> None:
    """Compare Count-to-Infinity behavior without split-horizon vs with poison-reverse."""
    topo_without = preset_count_to_infinity()
    vclock1 = VirtualClock()
    store1 = EventStore()

    # 1. Run without split-horizon / poison-reverse
    engine_without = SimulationEngine(
        topology=topo_without,
        protocol_factory=lambda _: DistanceVectorProtocol(
            config={
                "split_horizon": False,
                "poison_reverse": False,
                "triggered_updates": True,
                "infinity_metric": 16.0,
            }
        ),
        clock=vclock1,
        event_store=store1,
        quiescence_window_s=0.2,
        seed=42,
    )
    engine_without.add_event(0.2, "link_down", {"u": "C", "v": "D"})

    await engine_without.start()
    while vclock1.now() < 5.0:
        await vclock1.run_until(vclock1.now() + 0.1)
        if engine_without.check_convergence():
            break

    # 2. Run with split-horizon and poison-reverse enabled
    topo_with = preset_count_to_infinity()
    vclock2 = VirtualClock()
    store2 = EventStore()

    engine_with = SimulationEngine(
        topology=topo_with,
        protocol_factory=lambda _: DistanceVectorProtocol(
            config={
                "split_horizon": True,
                "poison_reverse": True,
                "triggered_updates": True,
                "infinity_metric": 16.0,
            }
        ),
        clock=vclock2,
        event_store=store2,
        quiescence_window_s=0.2,
        seed=42,
    )
    engine_with.add_event(0.2, "link_down", {"u": "C", "v": "D"})

    await engine_with.start()
    while vclock2.now() < 5.0:
        await vclock2.run_until(vclock2.now() + 0.1)
        if engine_with.check_convergence():
            break

    msgs_without = sum(n.packets_sent for n in engine_without.nodes.values())
    msgs_with = sum(n.packets_sent for n in engine_with.nodes.values())

    # Count-to-infinity generates significantly more ping-pong control updates
    assert msgs_without > msgs_with


@pytest.mark.asyncio
async def test_routing_table_poisoning_and_mitigation() -> None:
    """Test poisoning attack hijacking route and secure DV preventing it."""
    # 1. Vulnerable network: Node F poisons route to victim A
    topo1 = preset_6_node()
    vclock1 = VirtualClock()
    store1 = EventStore()

    def proto_factory1(node_id: str) -> DistanceVectorProtocol:
        if node_id == "F":
            # Malicious attacker node F claims cost 0.5 to victim A
            return PoisoningAttackProtocol(
                config={
                    "victim_node": "A",
                    "poison_cost": 0.5,
                    "attack_enabled": True,
                }
            )
        return DistanceVectorProtocol()

    engine1 = SimulationEngine(
        topology=topo1,
        protocol_factory=proto_factory1,
        clock=vclock1,
        event_store=store1,
        quiescence_window_s=0.3,
        seed=42,
    )

    await engine1.start()
    while vclock1.now() < 5.0:
        await vclock1.run_until(vclock1.now() + 0.1)
        if engine1.check_convergence():
            break

    # In vulnerable network, neighbor E routes to victim A through attacker F
    node_e = engine1.nodes["E"]
    route_to_a_in_e = next(r for r in node_e.get_table() if r.destination == "A")
    assert route_to_a_in_e.next_hop == "F"

    # 2. Hardened network with SecureDistanceVectorProtocol
    topo2 = preset_6_node()
    vclock2 = VirtualClock()
    store2 = EventStore()

    def proto_factory2(node_id: str) -> DistanceVectorProtocol:
        if node_id == "F":
            return PoisoningAttackProtocol(
                config={
                    "victim_node": "A",
                    "poison_cost": 0.5,
                    "attack_enabled": True,
                }
            )
        # Protect nodes: only A can originate prefix/routes for A
        return SecureDistanceVectorProtocol(
            config={
                "authorized_origins": {"A": ["A", "B", "C"]},
            }
        )

    engine2 = SimulationEngine(
        topology=topo2,
        protocol_factory=proto_factory2,
        clock=vclock2,
        event_store=store2,
        quiescence_window_s=0.3,
        seed=42,
    )

    await engine2.start()
    while vclock2.now() < 5.0:
        await vclock2.run_until(vclock2.now() + 0.1)
        if engine2.check_convergence():
            break

    # Node E rejected F's poisoned claim for A; maintains legitimate route
    node_e_secure = engine2.nodes["E"]
    route_to_a_secure = next(r for r in node_e_secure.get_table() if r.destination == "A")
    assert route_to_a_secure.next_hop != "F"
