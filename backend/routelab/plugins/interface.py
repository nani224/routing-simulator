"""Routing Protocol Plugin Architecture.

Defines the RoutingProtocol ABC and ProtocolContext contract.
Plugins implement only this interface and receive execution services
strictly via ProtocolContext — plugins never directly interact with sockets,
the event loop, or link layers.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class RouteEntry:
    """Standardized route entry produced by a routing protocol."""

    destination: str
    next_hop: str
    cost: float
    as_path: list[str] = field(default_factory=list)
    metric_type: str = "cost"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dst": self.destination,
            "next_hop": self.next_hop,
            "cost": self.cost if self.cost != float("inf") else 999999,
            "as_path": self.as_path,
            "metric_type": self.metric_type,
            "meta": self.metadata,
        }


@dataclass(slots=True)
class NeighborInfo:
    """Information exposed to a protocol regarding an attached neighbor."""

    node_id: str
    cost: float
    is_up: bool
    latency_ms: float = 10.0


class ProtocolContext(Protocol):
    """Execution sandbox context provided to routing protocol instances."""

    @property
    def node_id(self) -> str:
        """The identifier of the router hosting this protocol instance."""
        ...

    def send(self, nbr: str, payload: dict[str, Any]) -> None:
        """Send a unicast control message to an adjacent neighbor."""
        ...

    def broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast a control message to all active adjacent neighbors."""
        ...

    def set_timer(self, timer_id: str, delay_ms: float) -> None:
        """Schedule a timer callback identified by timer_id after delay_ms."""
        ...

    def cancel_timer(self, timer_id: str) -> None:
        """Cancel any pending timer with the specified timer_id."""
        ...

    def neighbors(self) -> Sequence[NeighborInfo]:
        """Return the current set of adjacent neighbors and their link costs."""
        ...

    def now(self) -> float:
        """Current simulation time in seconds."""
        ...

    def rng(self) -> random.Random:
        """Deterministic pseudorandom generator assigned to this router."""
        ...

    def log(self, message: str, level: str = "INFO") -> None:
        """Log a diagnostic message tagged with the node and protocol context."""
        ...


class RoutingProtocol(ABC):
    """Abstract Base Class for all RouteLab routing protocol plugins.

    Built-in protocols (DV, LS, BGP-lite) and user-provided custom algorithms
    must inherit from this class and implement its lifecycle hooks.
    """

    name: str = "base_protocol"
    version: str = "1.0.0"
    author: str = "Anonymous"
    config_schema: dict[str, Any] = {}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}

    @abstractmethod
    def on_start(self, ctx: ProtocolContext) -> None:
        """Invoked when the router boots or the protocol is initialized."""

    @abstractmethod
    def on_message(
        self,
        ctx: ProtocolContext,
        src: str,
        msg: dict[str, Any],
    ) -> None:
        """Invoked when a control packet from neighbor `src` arrives."""

    @abstractmethod
    def on_link_change(
        self,
        ctx: ProtocolContext,
        nbr: str,
        cost: float,
        up: bool,
    ) -> None:
        """Invoked when a link to neighbor `nbr` changes cost or status."""

    @abstractmethod
    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        """Invoked when a previously scheduled timer fires."""

    @abstractmethod
    def get_table(self) -> list[RouteEntry]:
        """Return the current routing table for forwarding and metrics."""

    def describe_state(self) -> dict[str, Any]:
        """Return arbitrary protocol-specific state for the UI inspector.

        For example:
        - DV: distance vectors received from neighbors
        - LS: link state database (LSDB), sequence numbers, age
        - BGP: Adj-RIB-In, Loc-RIB, Adj-RIB-Out, local-preference table
        """
        return {}
