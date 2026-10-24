"""Routing table poisoning and blackhole attack plugin.

Simulates malicious Byzantine router behavior in distance vector or link state networks:
1. Advertises fraudulent low-cost routes (e.g. cost 1 or 0) to a target victim destination.
2. Diverts network traffic away from genuine optimal paths towards the attacker.
3. Can act as a blackhole (dropping packets) or traffic interception/man-in-the-middle node.
"""

from __future__ import annotations

import logging
from typing import Any

from routelab.plugins.interface import (
    ProtocolContext,
)
from routelab.protocols.dv import DistanceVectorProtocol

logger = logging.getLogger("routelab.attacks.poisoning")


class PoisoningAttackProtocol(DistanceVectorProtocol):
    """Malicious Distance Vector speaker that injects poisoned false-cost routes."""

    name: str = "route_poisoning_attack"
    version: str = "1.0.0"
    author: str = "RouteLab Security Suite"

    config_schema: dict[str, Any] = {
        **DistanceVectorProtocol.config_schema,
        "victim_node": {
            "type": "string",
            "default": "",
            "description": "Destination node ID whose route is being hijacked/poisoned",
        },
        "poison_cost": {
            "type": "number",
            "default": 1.0,
            "description": "Forged metric advertised for the victim node",
        },
        "attack_enabled": {
            "type": "boolean",
            "default": True,
            "description": "Whether the poisoning attack is actively transmitting false vectors",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.victim_node: str = str(self.config.get("victim_node", ""))
        self.poison_cost: float = float(self.config.get("poison_cost", 1.0))
        self.attack_enabled: bool = bool(self.config.get("attack_enabled", True))
        self.poisoned_announcements_sent: int = 0

    def on_start(self, ctx: ProtocolContext) -> None:
        """Start normal DV operations and register periodic poison injection timer."""
        super().on_start(ctx)
        if self.attack_enabled and self.victim_node:
            ctx.set_timer("poison_pulse", 50.0)

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        """Handle periodic updates and active attack injection."""
        super().on_timer(ctx, timer_id)
        if timer_id == "poison_pulse" and self.attack_enabled and self.victim_node:
            self._inject_poison(ctx)
            ctx.set_timer("poison_pulse", 50.0)

    def _inject_poison(self, ctx: ProtocolContext) -> None:
        """Broadcast fraudulent distance vector claiming direct low-cost reachability to victim."""
        # Forge table vector: claim self reaches victim with poison_cost
        vector: dict[str, float] = {dst: entry.cost for dst, entry in self.table.items()}
        vector[self.victim_node] = self.poison_cost
        vector[ctx.node_id] = 0.0

        for nbr in ctx.neighbors():
            if nbr.is_up:
                ctx.send(
                    nbr.node_id,
                    {
                        "type": "DV_UPDATE",
                        "sender": ctx.node_id,
                        "vector": vector,
                    },
                )
                self.poisoned_announcements_sent += 1

        logger.warning(
            "Node %s [ATTACKER] injected poisoned route for victim %s with cost %s",
            ctx.node_id,
            self.victim_node,
            self.poison_cost,
        )

    def describe_state(self) -> dict[str, Any]:
        """Describe attack status and counter metrics."""
        base = super().describe_state()
        base["is_attacker"] = True
        base["attack_enabled"] = self.attack_enabled
        base["victim_node"] = self.victim_node
        base["poisoned_announcements_sent"] = self.poisoned_announcements_sent
        return base
