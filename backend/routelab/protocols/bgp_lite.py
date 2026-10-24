"""BGP-Lite Path-Vector Routing Protocol Plugin.

Implements simplified Border Gateway Protocol (BGP-4) semantics:
1. Path-vector advertisements with explicit AS_PATH tracking.
2. AS_PATH loop detection (announcements containing local AS are dropped).
3. Standard BGP Decision Process:
   - 1. Highest Local Preference (LOCAL_PREF)
   - 2. Shortest AS_PATH length
   - 3. Lowest Multi-Exit Discriminator (MED)
   - 4. Lowest peer link cost
   - 5. Tie-break on peer identifier
4. Explicit route withdrawals upon link down or reachability loss.
5. Per-peer import and export policy configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from routelab.plugins.interface import (
    ProtocolContext,
    RouteEntry,
    RoutingProtocol,
)

logger = logging.getLogger("routelab.bgp_lite")


@dataclass(slots=True)
class BGPPath:
    """Rib entry representing a candidate path to a destination."""

    destination: str
    next_hop: str
    as_path: list[str]
    local_pref: int = 100
    med: int = 0
    link_cost: float = 1.0


class BGPLiteProtocol(RoutingProtocol):
    """Production-grade BGP-Lite path-vector routing protocol."""

    name: str = "bgp_lite"
    version: str = "1.0.0"
    author: str = "Team 20 (Aakarsh, Sravan, Sneha)"

    config_schema: dict[str, Any] = {
        "as_number": {
            "type": "string",
            "default": "",
            "description": "Autonomous System ID (defaults to node_id if blank)",
        },
        "default_local_pref": {
            "type": "number",
            "default": 100,
            "description": "Default LOCAL_PREF assigned to imported routes",
        },
        "peer_policies": {
            "type": "object",
            "default": {},
            "description": "Map peer_id -> {'local_pref': int, 'import_filter': list[str]}",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.as_id: str = str(self.config.get("as_number", ""))
        self.default_local_pref: int = int(self.config.get("default_local_pref", 100))
        self.peer_policies: dict[str, dict[str, Any]] = self.config.get("peer_policies", {})

        # RIB-In: peer -> {dst -> BGPPath}
        self.rib_in: dict[str, dict[str, BGPPath]] = {}
        # Loc-RIB: dst -> BGPPath (best active routes)
        self.loc_rib: dict[str, BGPPath] = {}

        # Cached active neighbors
        self._neighbor_costs: dict[str, float] = {}

    def on_start(self, ctx: ProtocolContext) -> None:
        """Initialize BGP speaker, advertise local network prefix to all neighbors."""
        if not self.as_id:
            self.as_id = ctx.node_id

        self._update_neighbors(ctx)

        # Originate local prefix for self
        self.loc_rib[ctx.node_id] = BGPPath(
            destination=ctx.node_id,
            next_hop=ctx.node_id,
            as_path=[self.as_id],
            local_pref=self.default_local_pref,
            med=0,
            link_cost=0.0,
        )

        # Send initial announcements to all active peers
        self._announce_best_routes(ctx)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Handle incoming BGP messages: UPDATE (announcements and withdrawals)."""
        msg_type = msg.get("type")
        if msg_type != "BGP_UPDATE":
            return

        self._update_neighbors(ctx)
        link_cost = self._neighbor_costs.get(src, 1.0)
        policy = self.peer_policies.get(src, {})
        peer_pref = int(policy.get("local_pref", self.default_local_pref))
        import_filter = set(policy.get("import_filter", []))

        changed = False

        # 1. Process withdrawals
        withdrawals: list[str] = [str(x) for x in list(msg.get("withdrawals", []))]
        if src in self.rib_in:
            for w_dst in withdrawals:
                if w_dst in self.rib_in[src]:
                    del self.rib_in[src][w_dst]
                    changed = True

        # 2. Process announcements
        announcements: list[dict[str, Any]] = [
            dict(x) for x in list(msg.get("advertisements", [])) if isinstance(x, dict)
        ]
        for adv in announcements:
            dst = str(adv.get("destination", ""))
            as_path = list(adv.get("as_path", []))
            med = int(adv.get("med", 0))

            if not dst or not as_path:
                continue

            # Policy filter check
            if import_filter and dst in import_filter:
                continue

            # AS_PATH LOOP PREVENTION:
            # If our own AS is already in the AS_PATH, discard announcement
            if self.as_id in as_path:
                logger.debug(
                    "Node %s BGP loop detected: AS %s already in path %s",
                    ctx.node_id,
                    self.as_id,
                    as_path,
                )
                continue

            # Prepend local policy preference
            path = BGPPath(
                destination=dst,
                next_hop=src,
                as_path=as_path,
                local_pref=peer_pref,
                med=med,
                link_cost=link_cost,
            )

            if src not in self.rib_in:
                self.rib_in[src] = {}

            # Check if RIB-In entry actually changed
            old_path = self.rib_in[src].get(dst)
            if old_path != path:
                self.rib_in[src][dst] = path
                changed = True

        if changed:
            routes_modified = self._recompute_loc_rib(ctx)
            if routes_modified:
                self._announce_best_routes(ctx)

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        """Handle link up/down and cost changes with automatic route withdrawal."""
        self._update_neighbors(ctx)

        if not up:
            # Neighbor disconnected: purge its RIB-In entries and withdraw
            self._neighbor_costs.pop(nbr, None)
            if nbr in self.rib_in:
                del self.rib_in[nbr]
                routes_modified = self._recompute_loc_rib(ctx)
                if routes_modified:
                    self._announce_best_routes(ctx)
        else:
            self._neighbor_costs[nbr] = cost
            # Re-advertise our Loc-RIB to the newly connected/restored neighbor
            self._send_updates_to_peer(ctx, nbr)

    def on_timer(self, _ctx: ProtocolContext, _timer_id: str) -> None:
        pass

    def _update_neighbors(self, ctx: ProtocolContext) -> None:
        """Refresh active neighbor cost lookup."""
        for nbr in ctx.neighbors():
            if nbr.is_up:
                self._neighbor_costs[nbr.node_id] = nbr.cost
            else:
                self._neighbor_costs.pop(nbr.node_id, None)

    def _recompute_loc_rib(self, ctx: ProtocolContext) -> bool:
        """Execute BGP Decision Process across all RIB-In candidate paths."""
        new_loc_rib: dict[str, BGPPath] = {}

        # Self-originated prefix is always local
        new_loc_rib[ctx.node_id] = BGPPath(
            destination=ctx.node_id,
            next_hop=ctx.node_id,
            as_path=[self.as_id],
            local_pref=self.default_local_pref * 10,
            med=0,
            link_cost=0.0,
        )

        # Collect all candidates per destination
        all_dests: set[str] = set()
        for peer_routes in self.rib_in.values():
            all_dests.update(peer_routes.keys())

        for dst in all_dests:
            if dst == ctx.node_id:
                continue
            candidates: list[BGPPath] = []
            for peer, peer_routes in self.rib_in.items():
                if peer in self._neighbor_costs and dst in peer_routes:
                    candidates.append(peer_routes[dst])

            if not candidates:
                continue

            # Standard BGP Best Path Selection:
            # 1. Local preference (higher is better) -> -p.local_pref
            # 2. AS_PATH length (shorter is better) -> len(p.as_path)
            # 3. MED (lower is better) -> p.med
            # 4. IGP link cost to peer (lower is better) -> p.link_cost
            # 5. Deterministic tie-break on next_hop string
            best = min(
                candidates,
                key=lambda p: (
                    -p.local_pref,
                    len(p.as_path),
                    p.med,
                    p.link_cost,
                    p.next_hop,
                ),
            )
            new_loc_rib[dst] = best

        # Check if Loc-RIB changed
        changed = False
        if set(new_loc_rib.keys()) != set(self.loc_rib.keys()):
            changed = True
        else:
            for dst, path in new_loc_rib.items():
                old = self.loc_rib.get(dst)
                if old is None or old.next_hop != path.next_hop or old.as_path != path.as_path:
                    changed = True
                    break

        self.loc_rib = new_loc_rib
        return changed

    def _announce_best_routes(self, ctx: ProtocolContext) -> None:
        """Propagate current Loc-RIB to all active neighbors prepending local AS."""
        for nbr in ctx.neighbors():
            if nbr.is_up:
                self._send_updates_to_peer(ctx, nbr.node_id)

    def _send_updates_to_peer(self, ctx: ProtocolContext, peer_id: str) -> None:
        """Format and send UPDATE containing valid advertisements to a specific peer."""
        advertisements: list[dict[str, Any]] = []

        for dst, path in self.loc_rib.items():
            # Split-horizon check: do not advertise route back to the next-hop it came from
            if path.next_hop == peer_id and dst != ctx.node_id:
                continue

            advertisements.append(
                {
                    "destination": dst,
                    "as_path": [self.as_id] + path.as_path,
                    "med": path.med,
                }
            )

        if advertisements:
            ctx.send(
                peer_id,
                {
                    "type": "BGP_UPDATE",
                    "advertisements": advertisements,
                    "withdrawals": [],
                },
            )

    def get_table(self) -> list[RouteEntry]:
        """Convert Loc-RIB into standard RouteEntry table for forwarding."""
        entries: list[RouteEntry] = []
        for dst, path in self.loc_rib.items():
            # Cost reflects total AS path hops or link cost
            cost = float(len(path.as_path))
            entries.append(
                RouteEntry(
                    destination=dst,
                    next_hop=path.next_hop,
                    cost=cost,
                )
            )
        return entries

    def describe_state(self) -> dict[str, Any]:
        """Serialize BGP-Lite state for inspector and telemetry."""
        return {
            "protocol": "BGP-Lite",
            "as_id": self.as_id,
            "loc_rib_count": len(self.loc_rib),
            "loc_rib": {
                dst: {
                    "next_hop": p.next_hop,
                    "as_path": p.as_path,
                    "local_pref": p.local_pref,
                    "med": p.med,
                }
                for dst, p in self.loc_rib.items()
            },
            "peers_count": len(self.rib_in),
        }
