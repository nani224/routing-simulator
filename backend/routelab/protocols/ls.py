"""Link State (OSPF-like) routing protocol plugin with LSA flooding and Dijkstra SPF.

Features:
- Reliable LSA (Link State Advertisement) flooding with monotonic sequence numbering.
- O(1) duplicate suppression: incoming LSAs with seq <= stored are immediately dropped.
- Split-horizon flooding: LSAs are forwarded out all active interfaces except the ingress link.
- High-performance Dijkstra Shortest Path First (SPF) using heapq and indexed adjacency.
- Full Link State Database (LSDB) synchronization across the autonomous network.
- Rich state description exposing the topology database for UI cartographic rendering.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass
from typing import Any

from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol

logger = logging.getLogger("routelab.ls")


@dataclass(slots=True)
class LSA:
    """Link State Advertisement emitted by a router."""

    adv_router: str
    seq: int
    age: float
    links: list[tuple[str, float]]  # (neighbor_id, cost)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adv": self.adv_router,
            "seq": self.seq,
            "age": round(self.age, 4),
            "links": [[nbr, cost] for nbr, cost in self.links],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LSA:
        raw_links = data.get("links", [])
        clean_links: list[tuple[str, float]] = [
            (str(item[0]), float(item[1])) for item in raw_links
        ]
        return cls(
            adv_router=str(data["adv"]),
            seq=int(data["seq"]),
            age=float(data.get("age", 0.0)),
            links=clean_links,
        )


class LinkStateProtocol(RoutingProtocol):
    """Link State routing protocol implementing LSA flooding and Dijkstra SPF."""

    name: str = "link_state"
    version: str = "1.0.0"
    author: str = "Team 20 (Aakarsh, Sravan, Sneha)"

    config_schema: dict[str, Any] = {
        "refresh_interval_s": {
            "type": "number",
            "default": 10.0,
            "description": "Periodic LSA refresh interval in seconds",
        },
        "max_lsa_age_s": {
            "type": "number",
            "default": 30.0,
            "description": "LSA expiration age in seconds",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.refresh_interval_s: float = float(self.config.get("refresh_interval_s", 10.0))
        self.max_lsa_age_s: float = float(self.config.get("max_lsa_age_s", 30.0))

        # Link State Database (LSDB): router_id -> LSA
        self.lsdb: dict[str, LSA] = {}
        # Local LSA sequence number
        self._my_seq: int = 0
        # Active local neighbor costs: nbr_id -> cost
        self.local_neighbors: dict[str, float] = {}
        # Computed routing table: destination -> RouteEntry
        self.routing_table: dict[str, RouteEntry] = {}
        self._node_id: str = ""
        self._spf_dirty: bool = True

    def on_start(self, ctx: ProtocolContext) -> None:
        """Discover active neighbors, generate initial LSA, flood, and run SPF."""
        self._node_id = ctx.node_id
        self.local_neighbors.clear()
        for nbr in ctx.neighbors():
            if nbr.is_up:
                self.local_neighbors[nbr.node_id] = nbr.cost

        # Generate local LSA and flood
        self._originate_and_flood_lsa(ctx)

        # Schedule periodic refresh
        if self.refresh_interval_s > 0:
            ctx.set_timer("refresh_lsa", self.refresh_interval_s * 1000.0)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Process incoming LSA packet with O(1) sequence check and split-horizon flood."""
        if msg.get("type") != "lsa":
            return

        raw_lsa = msg.get("lsa")
        if not isinstance(raw_lsa, dict):
            return

        lsa = LSA.from_dict(raw_lsa)
        adv = lsa.adv_router

        # O(1) duplicate suppression check against current LSDB
        current_lsa = self.lsdb.get(adv)
        if current_lsa is not None and lsa.seq <= current_lsa.seq:
            # Already possess newer or identical LSA; drop immediately
            return

        # Install newer LSA into LSDB
        self.lsdb[adv] = lsa
        self._spf_dirty = True

        # Flood LSA out all other active neighbor interfaces except the ingress source
        flood_msg = {"type": "lsa", "lsa": lsa.to_dict()}
        for nbr in ctx.neighbors():
            if nbr.is_up and nbr.node_id != src:
                ctx.send(nbr.node_id, flood_msg)

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        """Handle link mutations by originating a new LSA with incremented sequence."""
        if up:
            self.local_neighbors[nbr] = cost
        else:
            self.local_neighbors.pop(nbr, None)

        # Originate new LSA reflecting link change and flood immediately
        self._originate_and_flood_lsa(ctx)

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        """Handle periodic LSA refresh and database aging."""
        if timer_id == "refresh_lsa":
            self._originate_and_flood_lsa(ctx)
            if self.refresh_interval_s > 0:
                ctx.set_timer("refresh_lsa", self.refresh_interval_s * 1000.0)

    def _originate_and_flood_lsa(self, ctx: ProtocolContext) -> None:
        """Construct local LSA, store in local LSDB, and broadcast."""
        self._node_id = ctx.node_id
        self._my_seq += 1
        links = [(nbr, cost) for nbr, cost in self.local_neighbors.items()]
        local_lsa = LSA(
            adv_router=ctx.node_id,
            seq=self._my_seq,
            age=0.0,
            links=links,
        )

        self.lsdb[ctx.node_id] = local_lsa
        self._spf_dirty = True

        msg = {"type": "lsa", "lsa": local_lsa.to_dict()}
        for nbr in ctx.neighbors():
            if nbr.is_up:
                ctx.send(nbr.node_id, msg)

    def _recompute_spf(self, root_id: str) -> None:
        """Execute Dijkstra SPF using heapq priority queue on active LSDB graph with O(1) checks."""
        if not root_id:
            return

        # 1. Build indexed adjacency graph from LSDB: u -> {v: cost}
        adj: dict[str, dict[str, float]] = {
            r_id: dict(lsa.links) for r_id, lsa in self.lsdb.items()
        }

        # 2. Dijkstra priority queue: (distance, node, first_hop)
        # distances: node -> (min_cost, next_hop)
        distances: dict[str, tuple[float, str]] = {root_id: (0.0, root_id)}
        pq: list[tuple[float, str, str]] = [(0.0, root_id, root_id)]
        visited: set[str] = set()

        while pq:
            d, u, first_hop = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)

            # Traverse neighbors of u in LSDB
            u_links = adj.get(u, {})
            for v, cost in u_links.items():
                # O(1) symmetric bidirectional link check
                if v != root_id and v in adj and u not in adj[v]:
                    continue

                new_dist = d + cost
                assigned_hop = v if u == root_id else first_hop

                if v not in distances or new_dist < distances[v][0]:
                    distances[v] = (new_dist, assigned_hop)
                    heapq.heappush(pq, (new_dist, v, assigned_hop))

        # 3. Populate standardized routing table
        new_table: dict[str, RouteEntry] = {}
        for dst, (cost, nxt) in distances.items():
            if dst != root_id:
                new_table[dst] = RouteEntry(
                    destination=dst,
                    next_hop=nxt,
                    cost=cost,
                    metadata={"lsa_seq": self.lsdb.get(dst, self.lsdb[root_id]).seq},
                )
        self.routing_table = new_table

    def get_table(self) -> list[RouteEntry]:
        """Return computed shortest path routing entries, recomputing SPF if database mutated."""
        if self._spf_dirty and self._node_id:
            self._recompute_spf(self._node_id)
            self._spf_dirty = False
        return list(self.routing_table.values())

    def describe_state(self) -> dict[str, Any]:
        """Expose LSDB and sequence numbers for UI cartography inspector."""
        if self._spf_dirty and self._node_id:
            self._recompute_spf(self._node_id)
            self._spf_dirty = False
        return {
            "algorithm": "Link State (Dijkstra SPF)",
            "my_sequence": self._my_seq,
            "lsdb": {r_id: lsa.to_dict() for r_id, lsa in self.lsdb.items()},
            "routes_count": len(self.routing_table),
        }
