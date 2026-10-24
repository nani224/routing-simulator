"""Scenario execution engine and reproducible test case runner.

Loads scenario definitions from JSON/YAML format and executes them deterministically
against the SimulationEngine, validating post-conditions and metrics.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from routelab.attacks.mitigation import SecureDistanceVectorProtocol
from routelab.attacks.poisoning import PoisoningAttackProtocol
from routelab.core.clock import VirtualClock
from routelab.core.events import EventStore
from routelab.metrics.collector import MetricsCollector, RunMetrics
from routelab.plugins.interface import RoutingProtocol
from routelab.protocols.bgp_lite import BGPLiteProtocol
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.protocols.flooding import FloodingProtocol
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.engine import ScheduledSimulationEvent, SimulationEngine
from routelab.topology.generators import (
    preset_6_node,
    preset_8_node,
    preset_10_node,
    preset_bgp_tier1,
    preset_count_to_infinity,
)
from routelab.topology.model import Topology, TopologyLink, TopologyNode


@dataclass(slots=True)
class ScenarioDefinition:
    """Structured representation of a benchmark or educational scenario."""

    name: str
    description: str
    topology_type: str  # e.g. "preset:6_node" or "custom"
    topology_data: dict[str, Any] | None = None
    default_protocol: str = "distance_vector"
    node_protocols: dict[str, str] = field(default_factory=dict)
    protocol_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[ScheduledSimulationEvent] = field(default_factory=list)
    time_limit_s: float = 30.0
    quiescence_window_s: float = 0.3
    seed: int = 42
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioResult:
    """Execution output from running a scenario."""

    scenario_name: str
    is_converged: bool
    convergence_time_s: float
    metrics: RunMetrics
    event_count: int
    final_routes: dict[str, list[dict[str, Any]]]


class ScenarioRunner:
    """Executes scenarios with deterministic virtual clocks and metrics recording."""

    PROTOCOL_REGISTRY: dict[str, Callable[[dict[str, Any]], RoutingProtocol]] = {
        "distance_vector": lambda cfg: DistanceVectorProtocol(cfg),
        "link_state": lambda cfg: LinkStateProtocol(cfg),
        "bgp_lite": lambda cfg: BGPLiteProtocol(cfg),
        "flooding": lambda cfg: FloodingProtocol(cfg),
        "poisoning_attack": lambda cfg: PoisoningAttackProtocol(cfg),
        "secure_dv": lambda cfg: SecureDistanceVectorProtocol(cfg),
    }

    @classmethod
    def load_from_file(cls, path: str | Path) -> ScenarioDefinition:
        """Parse scenario from a JSON specification file."""
        file_path = Path(path)
        with open(file_path, encoding="utf-8") as f:
            raw = json.load(f)

        events: list[ScheduledSimulationEvent] = []
        for ev in raw.get("events", []):
            events.append(
                ScheduledSimulationEvent(
                    timestamp=float(ev["timestamp"]),
                    action=str(ev["action"]),
                    params=dict(ev.get("params", {})),
                )
            )

        return ScenarioDefinition(
            name=raw.get("name", file_path.stem),
            description=raw.get("description", ""),
            topology_type=raw.get("topology_type", "preset:6_node"),
            topology_data=raw.get("topology_data"),
            default_protocol=raw.get("default_protocol", "distance_vector"),
            node_protocols=raw.get("node_protocols", {}),
            protocol_configs=raw.get("protocol_configs", {}),
            events=events,
            time_limit_s=float(raw.get("time_limit_s", 30.0)),
            quiescence_window_s=float(raw.get("quiescence_window_s", 0.3)),
            seed=int(raw.get("seed", 42)),
            metadata=raw.get("metadata", {}),
        )

    @classmethod
    def resolve_topology(cls, scenario: ScenarioDefinition) -> Topology:
        """Materialize Topology instance based on scenario specification."""
        t_type = scenario.topology_type
        if t_type in ("preset:6_node", "6_node"):
            return preset_6_node()
        elif t_type in ("preset:8_node", "8_node"):
            return preset_8_node()
        elif t_type in ("preset:10_node", "10_node"):
            return preset_10_node()
        elif t_type in ("preset:count_to_infinity", "count_to_infinity"):
            return preset_count_to_infinity()
        elif t_type in ("preset:bgp_tier1", "bgp_tier1"):
            return preset_bgp_tier1()
        elif scenario.topology_data is not None:
            topo = Topology(name=scenario.name)
            for n_data in scenario.topology_data.get("nodes", []):
                topo.add_node(
                    TopologyNode(
                        id=str(n_data["id"]),
                        x=float(n_data.get("x", 0.0)),
                        y=float(n_data.get("y", 0.0)),
                    )
                )
            for l_data in scenario.topology_data.get("links", []):
                topo.add_link(
                    TopologyLink(
                        source=str(l_data["u"]),
                        target=str(l_data["v"]),
                        cost=float(l_data.get("cost", 1.0)),
                        latency_ms=float(l_data.get("latency_ms", 10.0)),
                    )
                )
            return topo
        else:
            return preset_6_node()

    @classmethod
    async def run(cls, scenario: ScenarioDefinition) -> ScenarioResult:
        """Run scenario through the simulation engine to completion."""
        topo = cls.resolve_topology(scenario)
        vclock = VirtualClock()
        event_store = EventStore()

        # Build protocol instance factory
        def get_protocol_for_node(node_id: str) -> RoutingProtocol:
            proto_name = scenario.node_protocols.get(node_id, scenario.default_protocol)
            cfg = scenario.protocol_configs.get(node_id, {})
            factory: Callable[[dict[str, Any]], RoutingProtocol] = cls.PROTOCOL_REGISTRY.get(
                proto_name
            ) or (lambda c: DistanceVectorProtocol(c))
            return factory(cfg)

        engine = SimulationEngine(
            topology=topo,
            protocol_factory=get_protocol_for_node,
            clock=vclock,
            event_store=event_store,
            quiescence_window_s=scenario.quiescence_window_s,
        )

        for ev in scenario.events:
            engine.add_event(ev.timestamp, ev.action, ev.params)

        await engine.start()

        # Step simulation until time limit or convergence
        while vclock.now() < scenario.time_limit_s:
            await vclock.run_until(vclock.now() + 0.1)
            if engine.check_convergence():
                break

        metrics = MetricsCollector.collect_from_engine(
            engine, protocol_name=scenario.default_protocol
        )

        final_routes: dict[str, list[dict[str, Any]]] = {}
        for nid, node in engine.nodes.items():
            tbl = node.get_table()
            final_routes[nid] = [
                {"dst": r.destination, "next_hop": r.next_hop, "cost": r.cost} for r in tbl
            ]

        is_conv = bool(
            engine.convergence_record.is_converged if engine.convergence_record else False
        )
        conv_time = float(
            engine.convergence_record.convergence_time_s if engine.convergence_record else 0.0
        )

        return ScenarioResult(
            scenario_name=scenario.name,
            is_converged=is_conv,
            convergence_time_s=conv_time,
            metrics=metrics,
            event_count=len(event_store),
            final_routes=final_routes,
        )
