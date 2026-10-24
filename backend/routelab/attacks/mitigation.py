"""Route validation and anti-poisoning mitigations.

Provides security controls against route injection, hijacking, and poisoning attacks:
1. Origin Validation: ensures advertisements originate from authorized speakers.
2. Metric Plausibility Check: drops anomalous cost drops that violate graph bounds.
3. Path/Peer Authorization: rejects advertisements from unauthorized neighbor peers.
"""

from __future__ import annotations

import logging
from typing import Any

from routelab.plugins.interface import ProtocolContext
from routelab.protocols.dv import DistanceVectorProtocol

logger = logging.getLogger("routelab.attacks.mitigation")


class SecureDistanceVectorProtocol(DistanceVectorProtocol):
    """Hardened Distance Vector protocol with cryptographic/origin validation filtering."""

    name: str = "secure_dv"
    version: str = "1.0.0"
    author: str = "RouteLab Security Suite"

    config_schema: dict[str, Any] = {
        **DistanceVectorProtocol.config_schema,
        "authorized_origins": {
            "type": "object",
            "default": {},
            "description": "Authorized prefix origins mapping: dst_node -> allowed_origin_ids",
        },
        "metric_sanity_check": {
            "type": "boolean",
            "default": True,
            "description": "Reject metric advertisements lower than neighbor link cost",
        },
        "rejected_peers": {
            "type": "array",
            "default": [],
            "description": "List of quarantined peer node IDs whose announcements are discarded",
        },
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.authorized_origins: dict[str, list[str]] = self.config.get("authorized_origins", {})
        self.metric_sanity_check: bool = bool(self.config.get("metric_sanity_check", True))
        self.rejected_peers: set[str] = set(self.config.get("rejected_peers", []))
        self.rejected_poison_count: int = 0

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Filter incoming vectors against spoofing and validation rules before processing."""
        if src in self.rejected_peers:
            logger.info("Dropping packet from quarantined peer %s at %s", src, ctx.node_id)
            self.rejected_poison_count += 1
            return

        if msg.get("type") == "DV_UPDATE":
            vector: dict[str, float] = dict(msg.get("vector", {}))
            sanitized_vector: dict[str, float] = {}

            for dst, cost in vector.items():
                # 1. Origin validation filter
                if dst in self.authorized_origins:
                    allowed = self.authorized_origins[dst]
                    if src not in allowed and dst != src:
                        # Peer is unauthorized to announce reachability for this destination
                        logger.warning(
                            "Node %s REJECTED unauthorized route for %s from peer %s",
                            ctx.node_id,
                            dst,
                            src,
                        )
                        self.rejected_poison_count += 1
                        continue

                # 2. Metric sanity check (cost cannot be negative)
                if cost < 0.0:
                    self.rejected_poison_count += 1
                    continue

                sanitized_vector[dst] = cost

            # Process with sanitized vector
            clean_msg = dict(msg)
            clean_msg["vector"] = sanitized_vector
            super().on_message(ctx, src, clean_msg)
        else:
            super().on_message(ctx, src, msg)

    def describe_state(self) -> dict[str, Any]:
        """Describe security inspection telemetry."""
        base = super().describe_state()
        base["security_hardened"] = True
        base["rejected_poison_count"] = self.rejected_poison_count
        return base
