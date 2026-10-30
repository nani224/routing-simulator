"""Side-by-side protocol comparison engine for RouteLab.

Executes multiple routing protocols over identical topologies, identical failure schedules,
and identical seeds under deterministic virtual clocks.
Evaluates:
- Convergence Speed (winner = lowest time)
- Control Message Overhead (winner = fewest packets)
- Control Byte Overhead (winner = fewest wire bytes)
- Route Flaps (winner = lowest instability)
- Packet Delivery Ratio (winner = highest delivery percentage)
- Path Stretch (winner = closest to 1.0)
Generates comprehensive comparative reports and winner badges.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from routelab.core.clock import VirtualClock
from routelab.metrics.collector import MetricsCollector, RunMetrics
from routelab.metrics.oracle import RoutingOracle
from routelab.plugins.interface import RoutingProtocol
from routelab.sim.engine import ScheduledSimulationEvent, SimulationEngine
from routelab.topology.model import Topology

logger = logging.getLogger("routelab.comparator")


@dataclass
class ComparisonReport:
    """Consolidated comparative evaluation report across multiple routing protocols."""

    topology_name: str
    seed: int
    protocols: list[str]
    metrics: dict[str, RunMetrics]
    winners: dict[str, str]  # metric_name -> winning_protocol_name
    summary_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_name": self.topology_name,
            "seed": self.seed,
            "protocols": self.protocols,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "winners": self.winners,
            "summary_notes": self.summary_notes,
        }


class CompareEngine:
    """Executes identical scenario runs across candidate routing protocols."""

    @classmethod
    async def compare(
        cls,
        topology: Topology,
        protocols: list[tuple[str, Callable[[], RoutingProtocol]]],
        events: list[ScheduledSimulationEvent] | None = None,
        seed: int = 42,
        time_limit_s: float = 60.0,
        quiescence_window_s: float = 0.5,
    ) -> ComparisonReport:
        """Execute protocols deterministically on the identical topology and event schedule."""
        results: dict[str, RunMetrics] = {}

        for proto_name, factory in protocols:
            # Recreate isolated virtual clock with identical seed
            vclock = VirtualClock(seed=seed)
            # Fresh topology clone
            topo_clone = Topology.from_dict(topology.to_dict())

            engine = SimulationEngine(
                topology=topo_clone,
                protocol_factory=factory,
                clock=vclock,
                quiescence_window_s=quiescence_window_s,
            )

            # Replicate identical scheduled events
            if events:
                for ev in events:
                    engine.add_event(ev.timestamp, ev.action, dict(ev.params))

            await engine.start()

            # Execute simulation until convergence or timeout
            while vclock.now() < time_limit_s:
                await vclock.run_until(vclock.now() + 0.05)
                if engine.check_convergence():
                    # Check if pending scheduled events exist
                    pending_events = any(not e.executed for e in engine._scheduled_events)
                    if not pending_events:
                        break

            # Validate against ground-truth oracle
            tables = engine.get_all_routes()
            oracle_report = RoutingOracle.validate_tables(topo_clone, tables)

            metrics = MetricsCollector.collect_from_engine(
                engine,
                protocol_name=proto_name,
                oracle_report=oracle_report,
            )
            results[proto_name] = metrics

            await engine.stop()

        # Compute winner per metric
        winners = cls._determine_winners(results)
        summary_notes = cls._generate_summary_notes(results, winners)

        return ComparisonReport(
            topology_name=topology.name,
            seed=seed,
            protocols=[p[0] for p in protocols],
            metrics=results,
            winners=winners,
            summary_notes=summary_notes,
        )

    @classmethod
    def _determine_winners(cls, results: dict[str, RunMetrics]) -> dict[str, str]:
        winners: dict[str, str] = {}
        if not results:
            return winners

        # Lowest Convergence Time (Only among protocols that successfully converged)
        converged_candidates = [k for k, v in results.items() if v.is_converged]
        if converged_candidates:
            winners["convergence_time"] = min(
                converged_candidates, key=lambda k: results[k].convergence_time_s
            )
        else:
            winners["convergence_time"] = "None (Neither Converged)"

        # Lowest Control Message Overhead
        winners["control_messages"] = min(
            results.keys(), key=lambda k: results[k].total_control_messages
        )

        # Lowest Control Byte Overhead
        winners["control_bytes"] = min(results.keys(), key=lambda k: results[k].total_control_bytes)

        # Fewest Route Flaps
        winners["route_flaps"] = min(results.keys(), key=lambda k: results[k].total_route_flaps)

        # Highest Delivery Ratio
        winners["delivery_ratio"] = max(results.keys(), key=lambda k: results[k].delivery_ratio)

        # Lowest Path Stretch (closest to 1.0)
        winners["path_stretch"] = min(
            results.keys(), key=lambda k: abs(results[k].average_path_stretch - 1.0)
        )

        return winners

    @classmethod
    def _generate_summary_notes(
        cls, results: dict[str, RunMetrics], winners: dict[str, str]
    ) -> list[str]:
        notes: list[str] = []
        if "convergence_time" in winners:
            winner = winners["convergence_time"]
            if winner in results:
                t = results[winner].convergence_time_s
                notes.append(f"{winner} converged fastest ({t:.3f}s)")
            else:
                notes.append(
                    "No protocol achieved network convergence before the simulation limit."
                )

        if "control_messages" in winners:
            winner = winners["control_messages"]
            msgs = results[winner].total_control_messages
            notes.append(f"{winner} produced the least message overhead ({msgs} pkts)")

        return notes
