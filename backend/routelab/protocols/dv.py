"""Distance Vector (RIP-like, Bellman-Ford) routing protocol plugin.

Features:
- Bellman-Ford shortest-path computation with link-cost sensitivity.
- Configurable Split Horizon and Poison Reverse loop mitigations.
- Triggered Updates: immediately sends deltas when a cost or next-hop changes.
- Hold-down timer preventing transient loops during metric increases.
- Automatic route expiration and unreachable route metric (infinity = 16 or configurable).
- Rich state description for UI inspection (neighbor distance vectors, hold-down statuses).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol

logger = logging.getLogger("routelab.dv")


@dataclass
class DVRoute:
    """Internal distance vector routing table entry."""

    destination: str
    next_hop: str
    cost: float
    last_updated: float
    in_hold_down: bool = False
    hold_down_until: float = 0.0


class DistanceVectorProtocol(RoutingProtocol):
    """Distance Vector routing algorithm with Bellman-Ford and loop prevention."""

    name: str = "distance_vector"
    version: str = "1.0.0"
    author: str = "Team 20 (Aakarsh, Sravan, Sneha)"

    config_schema: dict[str, Any] = {
        "split_horizon": {
            "type": "boolean",
            "default": True,
            "description": "Prevent advertising a route back out the interface it was learned from",
        },
        "poison_reverse": {
            "type": "boolean",
            "default": True,
            "description": "Advertise unreachable metric (infinity) back to next-hop router",
        },
        "triggered_updates": {
            "type": "boolean",
            "default": True,
            "description": "Send immediate delta updates on metric mutation",
        },
        "infinity": {
            "type": "number",
            "default": 16.0,
            "description": "Metric value considered unreachable (infinity)",
        },
        "periodic_interval_s": {
            "type": "number",
            "default": 2.0,
            "description": "Periodic broadcast update interval in seconds",
        },
        "route_timeout_s": {
            "type": "number",
            "default": 6.0,
            "description": "Duration before a missing neighbor route is marked unreachable",
        },
        "hold_down_duration_s": {
            "type": "number",
            "default": 0.0,
            "description": "Hold-down timer duration in seconds after route failure",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.split_horizon: bool = bool(self.config.get("split_horizon", True))
        self.poison_reverse: bool = bool(self.config.get("poison_reverse", True))
        self.triggered_updates: bool = bool(self.config.get("triggered_updates", True))
        self.infinity: float = float(self.config.get("infinity", 16.0))
        self.periodic_interval_s: float = float(self.config.get("periodic_interval_s", 2.0))
        self.route_timeout_s: float = float(self.config.get("route_timeout_s", 6.0))
        self.hold_down_duration_s: float = float(self.config.get("hold_down_duration_s", 0.0))

        # Local routing table: destination -> DVRoute
        self.table: dict[str, DVRoute] = {}
        # Neighbor distance vectors: neighbor_id -> {dest: cost}
        self.neighbor_vectors: dict[str, dict[str, float]] = {}
        # Neighbor link costs: neighbor_id -> cost
        self.neighbor_costs: dict[str, float] = {}

    def on_start(self, ctx: ProtocolContext) -> None:
        """Initialize local router entry, sync neighbors, and start periodic timer."""
        # Route to self is 0 cost
        self.table[ctx.node_id] = DVRoute(
            destination=ctx.node_id,
            next_hop=ctx.node_id,
            cost=0.0,
            last_updated=ctx.now(),
        )

        for nbr in ctx.neighbors():
            if nbr.is_up:
                self.neighbor_costs[nbr.node_id] = nbr.cost
                self.table[nbr.node_id] = DVRoute(
                    destination=nbr.node_id,
                    next_hop=nbr.node_id,
                    cost=nbr.cost,
                    last_updated=ctx.now(),
                )

        # Broadcast initial distance vector
        self._send_advertisements(ctx, triggered=False)

        # Schedule periodic updates
        if self.periodic_interval_s > 0:
            ctx.set_timer("periodic_update", self.periodic_interval_s * 1000.0)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Process incoming distance vector advertisement from neighbor src."""
        vector = msg.get("vector")
        if not isinstance(vector, dict):
            return

        now = ctx.now()
        # Record latest vector from neighbor
        clean_vector: dict[str, float] = {str(k): float(v) for k, v in vector.items()}
        self.neighbor_vectors[src] = clean_vector

        link_cost = self.neighbor_costs.get(src)
        if link_cost is None:
            return

        changed = False

        # Apply Bellman-Ford equation: D(d) = min_{v} { c(s, v) + D_v(d) }
        all_destinations = set(self.table.keys()) | set(clean_vector.keys())

        for dst in all_destinations:
            if dst == ctx.node_id:
                continue

            advertised_cost = clean_vector.get(dst, self.infinity)
            new_cost = min(self.infinity, link_cost + advertised_cost)

            curr_route = self.table.get(dst)

            if curr_route is None:
                # Discovered new destination
                if new_cost < self.infinity:
                    self.table[dst] = DVRoute(
                        destination=dst,
                        next_hop=src,
                        cost=new_cost,
                        last_updated=now,
                    )
                    changed = True
            elif curr_route.next_hop == src:
                # Update from existing next-hop
                if abs(curr_route.cost - new_cost) > 1e-6:
                    if new_cost >= self.infinity:
                        # Route failed via current next-hop; search for alternative
                        curr_route.cost = self.infinity
                        curr_route.last_updated = now
                        if self.hold_down_duration_s > 0:
                            curr_route.in_hold_down = True
                            curr_route.hold_down_until = now + self.hold_down_duration_s

                        best_cost = self.infinity
                        best_nbr = src
                        for other_nbr, nbr_c in self.neighbor_costs.items():
                            alt_cost = nbr_c + self.neighbor_vectors.get(other_nbr, {}).get(
                                dst, self.infinity
                            )
                            if alt_cost < best_cost:
                                best_cost = alt_cost
                                best_nbr = other_nbr
                        if best_cost < self.infinity:
                            curr_route.cost = best_cost
                            curr_route.next_hop = best_nbr
                            curr_route.in_hold_down = False
                    elif new_cost > curr_route.cost:
                        # Metric increased: check all active neighbors for a better path
                        best_cost = new_cost
                        best_nbr = src
                        for other_nbr, nbr_c in self.neighbor_costs.items():
                            alt_cost = nbr_c + self.neighbor_vectors.get(other_nbr, {}).get(
                                dst, self.infinity
                            )
                            if alt_cost < best_cost:
                                best_cost = alt_cost
                                best_nbr = other_nbr
                        curr_route.cost = best_cost
                        curr_route.next_hop = best_nbr
                        curr_route.last_updated = now
                    else:
                        curr_route.cost = new_cost
                        curr_route.last_updated = now
                        curr_route.in_hold_down = False
                    changed = True
                else:
                    curr_route.last_updated = now
            else:
                # Route through different neighbor: adopt if strictly lower and not in hold-down
                if not curr_route.in_hold_down or now >= curr_route.hold_down_until:
                    if curr_route.in_hold_down and now >= curr_route.hold_down_until:
                        curr_route.in_hold_down = False

                    if new_cost < curr_route.cost:
                        curr_route.cost = new_cost
                        curr_route.next_hop = src
                        curr_route.last_updated = now
                        changed = True

        if changed and self.triggered_updates:
            self._send_advertisements(ctx, triggered=True)

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        """Handle link failure, recovery, or metric adjustment."""
        now = ctx.now()
        changed = False

        if up:
            self.neighbor_costs[nbr] = cost
            # Recompute or update route to neighbor directly
            curr_route = self.table.get(nbr)
            if curr_route is None or cost < curr_route.cost or curr_route.next_hop == nbr:
                self.table[nbr] = DVRoute(
                    destination=nbr,
                    next_hop=nbr,
                    cost=cost,
                    last_updated=now,
                )
                changed = True
        else:
            # Link down
            self.neighbor_costs.pop(nbr, None)
            self.neighbor_vectors.pop(nbr, None)

            # Invalidate all routes using this neighbor as next_hop
            for _dst, route in self.table.items():
                if route.next_hop == nbr:
                    route.cost = self.infinity
                    route.last_updated = now
                    if self.hold_down_duration_s > 0:
                        route.in_hold_down = True
                        route.hold_down_until = now + self.hold_down_duration_s
                    changed = True

            # Attempt alternative path search across remaining active neighbors
            for dst, route in self.table.items():
                if route.cost >= self.infinity and dst != ctx.node_id:
                    best_cost = self.infinity
                    best_nbr = ""
                    for other_nbr, nbr_c in self.neighbor_costs.items():
                        vec = self.neighbor_vectors.get(other_nbr, {})
                        alt_cost = nbr_c + vec.get(dst, self.infinity)
                        if alt_cost < best_cost:
                            best_cost = alt_cost
                            best_nbr = other_nbr
                    if best_cost < self.infinity:
                        route.cost = best_cost
                        route.next_hop = best_nbr
                        route.last_updated = now
                        route.in_hold_down = False
                        changed = True

        if changed and self.triggered_updates:
            self._send_advertisements(ctx, triggered=True)

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        """Handle periodic updates and route age expiration."""
        if timer_id == "periodic_update":
            # Check route expirations
            now = ctx.now()
            for dst, route in list(self.table.items()):
                if (
                    dst != ctx.node_id
                    and route.cost < self.infinity
                    and (now - route.last_updated) > self.route_timeout_s
                ):
                    route.cost = self.infinity

            self._send_advertisements(ctx, triggered=False)

            # Reschedule periodic update
            if self.periodic_interval_s > 0:
                ctx.set_timer("periodic_update", self.periodic_interval_s * 1000.0)

    def _send_advertisements(self, ctx: ProtocolContext, triggered: bool = False) -> None:
        """Craft and transmit distance vector advertisements per neighbor."""
        for nbr_info in ctx.neighbors():
            if not nbr_info.is_up:
                continue

            nbr = nbr_info.node_id
            vector_to_send: dict[str, float] = {}

            for dst, route in self.table.items():
                cost = route.cost

                # Apply Split Horizon / Poison Reverse
                if route.next_hop == nbr and dst != ctx.node_id:
                    if self.poison_reverse:
                        # Poison reverse: advertise infinity to next-hop
                        cost = self.infinity
                    elif self.split_horizon:
                        # Split horizon: omit route completely
                        continue

                vector_to_send[dst] = cost

            payload = {
                "type": "dv_update",
                "triggered": triggered,
                "vector": vector_to_send,
            }
            ctx.send(nbr, payload)

    def get_table(self) -> list[RouteEntry]:
        """Produce standardized RouteEntry routing table."""
        routes: list[RouteEntry] = []
        for dst, route in self.table.items():
            if route.cost < self.infinity:
                routes.append(
                    RouteEntry(
                        destination=dst,
                        next_hop=route.next_hop,
                        cost=route.cost,
                        metadata={
                            "in_hold_down": route.in_hold_down,
                            "last_updated": round(route.last_updated, 4),
                        },
                    )
                )
        return routes

    def describe_state(self) -> dict[str, Any]:
        """Describe detailed state for UI inspector."""
        return {
            "algorithm": "Distance Vector (Bellman-Ford)",
            "config": {
                "split_horizon": self.split_horizon,
                "poison_reverse": self.poison_reverse,
                "triggered_updates": self.triggered_updates,
                "infinity": self.infinity,
            },
            "distance_vectors": dict(self.neighbor_vectors.items()),
            "internal_table": {
                dst: {
                    "next_hop": r.next_hop,
                    "cost": r.cost if r.cost < self.infinity else "infinity",
                    "in_hold_down": r.in_hold_down,
                }
                for dst, r in self.table.items()
            },
        }
