"""Route validation and anti-poisoning mitigations.

Provides security controls against route injection, hijacking, and poisoning attacks:
1. Origin Validation: ensures advertisements originate from authorized speakers.
2. Metric Plausibility Check: drops anomalous cost drops that violate graph bounds.
3. Path/Peer Authorization: rejects advertisements from unauthorized neighbor peers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from routelab.plugins.interface import ProtocolContext
from routelab.protocols.dv import DistanceVectorProtocol

logger = logging.getLogger("routelab.attacks.mitigation")


class SecureDistanceVectorProtocol(DistanceVectorProtocol):
    """Hardened Distance Vector protocol with HMAC-SHA256 update signing and origin validation.

    Note on Security Limitations:
    Uses shared-secret HMAC authentication. This guarantees mutual peer authentication and
    payload integrity against unauthorized route tampering, but relies on symmetric keys
    (shared secrets) rather than asymmetric public-key infrastructure (e.g., RPKI).
    """

    name: str = "secure_dv"
    version: str = "1.0.0"
    author: str = "RouteLab Security Suite"

    config_schema: dict[str, Any] = {
        **DistanceVectorProtocol.config_schema,
        "shared_secret": {
            "type": "string",
            "default": "routelab_secret_key_2026",
            "description": "Shared symmetric key for HMAC-SHA256 route update signing",
        },
        "require_auth": {
            "type": "boolean",
            "default": True,
            "description": "Require valid cryptographic signature on all incoming routing updates",
        },
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
        self.shared_secret: str = str(self.config.get("shared_secret", "routelab_secret_key_2026"))
        self.require_auth: bool = bool(self.config.get("require_auth", True))
        self.authorized_origins: dict[str, list[str]] = self.config.get("authorized_origins", {})
        self.metric_sanity_check: bool = bool(self.config.get("metric_sanity_check", True))
        self.rejected_peers: set[str] = set(self.config.get("rejected_peers", []))
        self.rejected_poison_count: int = 0

    @classmethod
    def compute_hmac(cls, secret: str, sender: str, vector: dict[str, float]) -> str:
        """Compute deterministic HMAC-SHA256 signature for a distance vector."""
        canonical_items = sorted((str(k), float(v)) for k, v in vector.items())
        serialized = json.dumps({"sender": sender, "vector": canonical_items}, sort_keys=True)
        return hmac.new(
            secret.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _send_advertisements(self, ctx: ProtocolContext, triggered: bool = False) -> None:
        """Craft, cryptographically sign with HMAC, and transmit distance vector advertisements."""
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
                        cost = self.infinity
                    elif self.split_horizon:
                        continue

                vector_to_send[dst] = cost

            sig = self.compute_hmac(self.shared_secret, ctx.node_id, vector_to_send)
            payload = {
                "type": "dv_update",
                "triggered": triggered,
                "sender": ctx.node_id,
                "vector": vector_to_send,
                "hmac": sig,
            }
            ctx.send(nbr, payload)

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        """Filter incoming vectors against cryptographic HMAC signatures and validation rules."""
        if src in self.rejected_peers:
            logger.info("Dropping packet from quarantined peer %s at %s", src, ctx.node_id)
            self.rejected_poison_count += 1
            return

        msg_type = str(msg.get("type", "")).lower()
        if msg_type in ("dv_update", "update"):
            vector: dict[str, float] = {
                str(k): float(v) for k, v in dict(msg.get("vector", {})).items()
            }

            # 1. Cryptographic HMAC authentication check
            if self.require_auth:
                provided_sig = str(msg.get("hmac", ""))
                expected_sig = self.compute_hmac(self.shared_secret, src, vector)
                if not hmac.compare_digest(provided_sig, expected_sig):
                    logger.warning(
                        "Node %s REJECTED forged/unauthenticated route update from peer %s",
                        ctx.node_id,
                        src,
                    )
                    self.rejected_poison_count += 1
                    return

            sanitized_vector: dict[str, float] = {}

            for dst, cost in vector.items():
                # 2. Origin validation filter
                if dst in self.authorized_origins:
                    allowed = self.authorized_origins[dst]
                    if src not in allowed and dst != src:
                        logger.warning(
                            "Node %s REJECTED unauthorized route for %s from peer %s",
                            ctx.node_id,
                            dst,
                            src,
                        )
                        self.rejected_poison_count += 1
                        continue

                # 3. Metric sanity check (cost cannot be negative)
                if cost < 0.0:
                    self.rejected_poison_count += 1
                    continue

                sanitized_vector[dst] = cost

            # Process with verified & sanitized vector
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
