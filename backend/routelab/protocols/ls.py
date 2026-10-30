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

        # Reliable flooding pending acknowledgements: (nbr, adv, seq) -> (sent_time, retries, msg)
        self.pending_acks: dict[tuple[str, str, int], tuple[float, int, dict[str, Any]]] = {}
        self._last_aging_time: float = 0.0
        self._has_started: bool = False

    def on_start(self, ctx: ProtocolContext) -> None:
        """Discover active neighbors, generate initial LSA, flood, and run SPF."""
        is_recovery = self._has_started
        self._has_started = True

        self._node_id = ctx.node_id
        self._last_aging_time = ctx.now()
        self.local_neighbors.clear()
        for nbr in ctx.neighbors():
            if nbr.is_up:
                self.local_neighbors[nbr.node_id] = nbr.cost

        # Generate local LSA and flood
        self._originate_and_flood_lsa(ctx)

        # On node recovery, trigger LSDB synchronization exchange before routing table recomputation
        if is_recovery:
            sync_req = {"type": "lsdb_request", "requester": ctx.node_id}
            for nbr in ctx.neighbors():
                if nbr.is_up:
                    ctx.send(nbr.node_id, sync_req)

        # Schedule periodic refresh & maintenance
        if self.refresh_interval_s > 0:
            ctx.set_timer("refresh_lsa", self.refresh_interval_s * 1000.0)
        ctx.set_timer("ls_maintenance", 1000.0)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Process incoming LSA packet with reliable LSAck, LSDB sync, and split-horizon flood."""
        msg_type = msg.get("type")

        # 1. Handle LSA Acknowledgement
        if msg_type == "lsack":
            adv_acked = str(msg.get("adv", ""))
            seq_acked = int(msg.get("seq", 0))
            self.pending_acks.pop((src, adv_acked, seq_acked), None)
            return

        # 2. Handle LSDB Synchronization Request from newly started or recovered neighbor
        if msg_type == "lsdb_request":
            for lsa in list(self.lsdb.values()):
                out_msg = {"type": "lsa", "lsa": lsa.to_dict()}
                ctx.send(src, out_msg)
                self.pending_acks[(src, lsa.adv_router, lsa.seq)] = (ctx.now(), 0, out_msg)
            return

        # 3. Handle standard LSA packet
        if msg_type != "lsa":
            return

        raw_lsa = msg.get("lsa")
        if not isinstance(raw_lsa, dict):
            return

        lsa = LSA.from_dict(raw_lsa)
        adv = lsa.adv_router

        # Always acknowledge received LSA back to ingress sender (reliable flooding)
        ack_msg = {"type": "lsack", "adv": adv, "seq": lsa.seq}
        ctx.send(src, ack_msg)

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
        now = ctx.now()
        for nbr in ctx.neighbors():
            if nbr.is_up and nbr.node_id != src:
                ctx.send(nbr.node_id, flood_msg)
                self.pending_acks[(nbr.node_id, adv, lsa.seq)] = (now, 0, flood_msg)

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        """Handle link mutations by originating a new LSA with incremented sequence."""
        if up:
            self.local_neighbors[nbr] = cost
        else:
            self.local_neighbors.pop(nbr, None)
            # Remove pending acks destined to dead neighbor
            for k in list(self.pending_acks.keys()):
                if k[0] == nbr:
                    self.pending_acks.pop(k, None)

        # Originate new LSA reflecting link change and flood immediately
        self._originate_and_flood_lsa(ctx)

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        """Handle periodic LSA refresh, database aging, and unacknowledged retransmissions."""
        now = ctx.now()
        if timer_id == "refresh_lsa":
            self._originate_and_flood_lsa(ctx)
            if self.refresh_interval_s > 0:
                ctx.set_timer("refresh_lsa", self.refresh_interval_s * 1000.0)

        elif timer_id == "ls_maintenance":
            # 1. Age and evict expired LSAs
            elapsed = max(0.0, now - self._last_aging_time)
            self._last_aging_time = now
            if elapsed > 0:
                expired_routers: list[str] = []
                for r_id, lsa in self.lsdb.items():
                    if r_id != self._node_id:
                        lsa.age += elapsed
                        if lsa.age >= self.max_lsa_age_s:
                            expired_routers.append(r_id)
                for r_id in expired_routers:
                    self.lsdb.pop(r_id, None)
                    self._spf_dirty = True

            # 2. Retransmit unacknowledged LSAs (reliable flooding)
            for key, (sent_time, retries, msg_to_send) in list(self.pending_acks.items()):
                nbr_id, _adv_r, _seq_num = key
                if now - sent_time >= 1.0:
                    if retries < 3:
                        ctx.send(nbr_id, msg_to_send)
                        self.pending_acks[key] = (now, retries + 1, msg_to_send)
                    else:
                        self.pending_acks.pop(key, None)

            ctx.set_timer("ls_maintenance", 1000.0)

    def _originate_and_flood_lsa(self, ctx: ProtocolContext) -> None:
        """Construct local LSA, store in local LSDB, and broadcast reliably."""
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
        now = ctx.now()
        for nbr in ctx.neighbors():
            if nbr.is_up:
                ctx.send(nbr.node_id, msg)
                self.pending_acks[(nbr.node_id, ctx.node_id, self._my_seq)] = (now, 0, msg)

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
