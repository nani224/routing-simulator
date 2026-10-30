"""Controlled flooding baseline protocol plugin for comparative overhead studies.

Used in comparative analysis to demonstrate the massive control overhead of naive flooding
against intelligent Distance Vector and Link State algorithms.
"""

from __future__ import annotations

import logging
from typing import Any

from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol

logger = logging.getLogger("routelab.flooding")


class FloodingProtocol(RoutingProtocol):
    """Controlled flooding baseline with sequence cache duplicate suppression."""

    name: str = "flooding"
    version: str = "1.0.0"
    author: str = "Team 20 (Aakarsh, Sravan, Sneha)"

    config_schema: dict[str, Any] = {
        "max_hop_ttl": {
            "type": "number",
            "default": 16.0,
            "description": "Maximum forwarding hops before packet drop",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.max_hop_ttl: int = int(self.config.get("max_hop_ttl", 16))
        # Seen packet cache: (origin, seq)
        self.seen_messages: set[tuple[str, int]] = set()
        self._seq: int = 0
        # Discovered destinations: dst -> (cost, next_hop, hops)
        self.discovered_routes: dict[str, tuple[float, str, int]] = {}
        self.neighbor_costs: dict[str, float] = {}

    def on_start(self, ctx: ProtocolContext) -> None:
        """Announce presence by flooding an announcement message."""
        self.neighbor_costs.clear()
        for nbr in ctx.neighbors():
            if nbr.is_up:
                self.neighbor_costs[nbr.node_id] = nbr.cost
                self.discovered_routes[nbr.node_id] = (nbr.cost, nbr.node_id, 1)

        self._originate_announcement(ctx)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Receive flood message, record cost/hops, and re-flood to active neighbors."""
        origin = str(msg.get("origin", ""))
        seq = int(msg.get("seq", 0))
        hops = int(msg.get("hops", 0))
        path_cost = float(msg.get("cost", 0.0))
        ttl = int(msg.get("ttl", self.max_hop_ttl))

        if not origin or origin == ctx.node_id:
            return

        key = (origin, seq)
        if key in self.seen_messages:
            # Drop duplicate message
            return
        self.seen_messages.add(key)

        # Calculate cumulative cost
        link_cost = self.neighbor_costs.get(src, 1.0)
        total_cost = path_cost + link_cost
        total_hops = hops + 1

        # Update discovered route if lower cost, or lower hops on tie, or new
        curr = self.discovered_routes.get(origin)
        if (
            curr is None
            or total_cost < curr[0]
            or (abs(total_cost - curr[0]) < 1e-6 and total_hops < curr[2])
        ):
            self.discovered_routes[origin] = (total_cost, src, total_hops)

        # Re-flood if TTL remains
        if ttl > 1:
            forward_msg = {
                "origin": origin,
                "seq": seq,
                "hops": total_hops,
                "cost": total_cost,
                "ttl": ttl - 1,
            }
            for nbr in ctx.neighbors():
                if nbr.is_up and nbr.node_id != src:
                    ctx.send(nbr.node_id, forward_msg)

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        """Handle link state change by pruning invalid routes and re-announcing."""
        if up:
            self.neighbor_costs[nbr] = cost
            self.discovered_routes[nbr] = (cost, nbr, 1)
        else:
            self.neighbor_costs.pop(nbr, None)
            # Immediately invalidate routes learned via the failed link
            for dst in list(self.discovered_routes.keys()):
                if self.discovered_routes[dst][1] == nbr:
                    del self.discovered_routes[dst]

        self._originate_announcement(ctx)

    def on_timer(self, _ctx: ProtocolContext, _timer_id: str) -> None:
        pass

    def _originate_announcement(self, ctx: ProtocolContext) -> None:
        self._seq += 1
        msg = {
            "origin": ctx.node_id,
            "seq": self._seq,
            "hops": 0,
            "cost": 0.0,
            "ttl": self.max_hop_ttl,
        }
        self.seen_messages.add((ctx.node_id, self._seq))
        for nbr in ctx.neighbors():
            if nbr.is_up:
                ctx.send(nbr.node_id, msg)

    def get_table(self) -> list[RouteEntry]:
        return [
            RouteEntry(
                destination=dst,
                next_hop=nxt,
                cost=cost,
                metadata={"hops": hops},
            )
            for dst, (cost, nxt, hops) in self.discovered_routes.items()
        ]

    def describe_state(self) -> dict[str, Any]:
        return {
            "algorithm": "Controlled Flooding Baseline",
            "seen_messages_count": len(self.seen_messages),
            "discovered_routes_count": len(self.discovered_routes),
        }
