"""Routing correctness oracle and loop/blackhole verification using NetworkX.

Computes theoretical ground-truth shortest paths across the topology and verifies:
1. Optimal cost match against simulated routing tables.
2. Loop freedom: ensures no forwarding cycles (e.g., A -> B -> C -> A).
3. Reachability & blackholes: detects destinations dropped or terminated prematurely.
4. Path stretch: ratio of simulator route cost to oracle shortest path cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from routelab.plugins.interface import RouteEntry
    from routelab.topology.model import Topology


@dataclass
class OracleValidationReport:
    """Detailed verification report evaluating protocol accuracy against oracle ground truth."""

    is_optimal: bool
    is_loop_free: bool
    total_pairs_tested: int
    matched_cost_pairs: int
    mismatched_cost_pairs: list[dict[str, Any]] = field(default_factory=list)
    loops_detected: list[list[str]] = field(default_factory=list)
    blackholes_detected: list[dict[str, str]] = field(default_factory=list)
    average_path_stretch: float = 1.0


class RoutingOracle:
    """Theoretical shortest-path ground truth computer using NetworkX."""

    @classmethod
    def validate_tables(
        cls,
        topology: Topology,
        active_tables: dict[str, list[RouteEntry]],
    ) -> OracleValidationReport:
        """Validate routing tables from all nodes against theoretical shortest paths."""
        g = topology.to_networkx()

        # Compute all-pairs shortest paths on the currently active topology
        oracle_distances: dict[str, dict[str, float]] = {}
        oracle_paths: dict[str, dict[str, list[str]]] = {}

        for n in g.nodes():
            try:
                oracle_distances[n], oracle_paths[n] = nx.single_source_dijkstra(
                    g, source=n, weight="weight"
                )
            except nx.NetworkXError:
                oracle_distances[n] = {n: 0.0}
                oracle_paths[n] = {n: [n]}

        # Map active next-hops: src -> {dst: next_hop}
        # Map active route costs: src -> {dst: cost}
        next_hops: dict[str, dict[str, str]] = {}
        route_costs: dict[str, dict[str, float]] = {}

        for src, routes in active_tables.items():
            next_hops[src] = {}
            route_costs[src] = {}
            for r in routes:
                next_hops[src][r.destination] = r.next_hop
                route_costs[src][r.destination] = r.cost

        total_pairs = 0
        matched_pairs = 0
        mismatched: list[dict[str, Any]] = []
        loops: list[list[str]] = []
        blackholes: list[dict[str, str]] = []
        stretch_ratios: list[float] = []

        all_nodes = list(topology.nodes.keys())

        for src in all_nodes:
            for dst in all_nodes:
                if src == dst:
                    continue

                total_pairs += 1
                oracle_cost = oracle_distances.get(src, {}).get(dst)

                if oracle_cost is None:
                    # Target node is partitioned/unreachable in graph
                    sim_cost = route_costs.get(src, {}).get(dst)
                    if sim_cost is not None and sim_cost < 999999:
                        mismatched.append(
                            {
                                "src": src,
                                "dst": dst,
                                "oracle_cost": "unreachable",
                                "sim_cost": sim_cost,
                            }
                        )
                    else:
                        matched_pairs += 1
                    continue

                # Target is reachable in graph according to oracle
                sim_cost = route_costs.get(src, {}).get(dst)
                if sim_cost is None:
                    blackholes.append({"src": src, "dst": dst, "reason": "no_route_in_table"})
                    continue

                # Trace forwarding path to test loop-freedom
                visited: list[str] = [src]
                curr = src
                has_loop = False
                reached = False

                max_hops = len(all_nodes) + 2
                hops = 0

                while hops < max_hops:
                    hops += 1
                    nxt = next_hops.get(curr, {}).get(dst)
                    if not nxt:
                        blackholes.append(
                            {
                                "src": src,
                                "dst": dst,
                                "reason": f"path_broken_at_{curr}",
                            }
                        )
                        break
                    if nxt == dst:
                        reached = True
                        visited.append(dst)
                        break
                    if nxt in visited:
                        has_loop = True
                        loop_path = visited[visited.index(nxt) :] + [nxt]
                        if loop_path not in loops:
                            loops.append(loop_path)
                        break
                    visited.append(nxt)
                    curr = nxt

                if has_loop:
                    continue

                if reached:
                    if abs(sim_cost - oracle_cost) < 1e-4:
                        matched_pairs += 1
                        stretch_ratios.append(1.0)
                    else:
                        mismatched.append(
                            {
                                "src": src,
                                "dst": dst,
                                "oracle_cost": oracle_cost,
                                "sim_cost": sim_cost,
                            }
                        )
                        stretch = sim_cost / max(1e-4, oracle_cost)
                        stretch_ratios.append(stretch)

        avg_stretch = sum(stretch_ratios) / max(1, len(stretch_ratios))
        is_opt = len(mismatched) == 0 and len(blackholes) == 0 and len(loops) == 0
        is_loopfree = len(loops) == 0

        return OracleValidationReport(
            is_optimal=is_opt,
            is_loop_free=is_loopfree,
            total_pairs_tested=total_pairs,
            matched_cost_pairs=matched_pairs,
            mismatched_cost_pairs=mismatched,
            loops_detected=loops,
            blackholes_detected=blackholes,
            average_path_stretch=round(avg_stretch, 4),
        )
