"""Append-only compact event store for RouteLab.

Tracks every packet transmission, delivery, drop, link change, node failure,
and routing table mutation with high-resolution timestamps.
Enables full timeline scrubbing, step-by-step playback, and JSON/msgpack export.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

import msgpack


class EventType(enum.StrEnum):
    """Event classifications in the simulation timeline."""

    PACKET_SENT = "packet_sent"
    PACKET_DELIVERED = "packet_delivered"
    PACKET_DROPPED = "packet_dropped"
    LINK_STATE = "link_state"
    NODE_STATE = "node_state"
    TABLE_UPDATE = "table_update"
    CONVERGENCE = "convergence"
    ATTACK_INJECTED = "attack_injected"
    LOG_MESSAGE = "log_message"


@dataclass(slots=True)
class SimEvent:
    """Individual recorded simulation event.

    Attributes:
        seq: Monotonic event sequence number.
        timestamp: Simulation time in seconds when event occurred.
        event_type: Category of the event.
        source: Emitting node, link, or controller.
        data: Arbitrary payload details for inspectors and charts.
    """

    seq: int
    timestamp: float
    event_type: EventType
    source: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": round(self.timestamp, 6),
            "type": self.event_type.value,
            "src": self.source,
            "data": self.data,
        }


class EventStore:
    """Thread-safe and async-safe append-only event log.

    Maintains bounded memory buffers for long runs with indexed retrieval
    for timeline scrubbing, pause/step, and export.
    """

    def __init__(self, max_events: int = 100_000) -> None:
        self.max_events = max_events
        self._events: list[SimEvent] = []
        self._seq: int = 0

    def append(
        self,
        timestamp: float,
        event_type: EventType,
        source: str,
        data: dict[str, Any] | None = None,
    ) -> SimEvent:
        """Record an event in the store."""
        self._seq += 1
        event = SimEvent(
            seq=self._seq,
            timestamp=timestamp,
            event_type=event_type,
            source=source,
            data=data or {},
        )
        self._events.append(event)
        if len(self._events) > self.max_events:
            # Drop oldest 10% when capacity reached
            drop_count = self.max_events // 10
            del self._events[:drop_count]
        return event

    def count(self) -> int:
        return len(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def get_all(self) -> list[SimEvent]:
        return list(self._events)

    def get_range(
        self,
        start_time: float = 0.0,
        end_time: float | None = None,
        event_types: set[EventType] | None = None,
    ) -> list[SimEvent]:
        """Query events within a time slice, optionally filtered by event type."""
        results: list[SimEvent] = []
        for e in self._events:
            if e.timestamp < start_time:
                continue
            if end_time is not None and e.timestamp > end_time:
                break
            if event_types is not None and e.event_type not in event_types:
                continue
            results.append(e)
        return results

    def get_since_seq(self, last_seq: int, limit: int = 1000) -> list[SimEvent]:
        """Fetch newly recorded events since last_seq for incremental streaming."""
        results: list[SimEvent] = []
        for e in self._events:
            if e.seq > last_seq:
                results.append(e)
                if len(results) >= limit:
                    break
        return results

    def clear(self) -> None:
        """Clear all events and reset sequence counter."""
        self._events.clear()
        self._seq = 0

    def to_msgpack(self) -> bytes:
        """Export serialized event stream to msgpack binary."""
        raw_list = [e.to_dict() for e in self._events]
        return msgpack.packb(raw_list, use_bin_type=True)  # type: ignore[no-any-return]

    @classmethod
    def from_msgpack(cls, data: bytes) -> EventStore:
        """Import event stream from msgpack binary."""
        unpacked = msgpack.unpackb(data, raw=False)
        store = cls(max_events=max(100_000, len(unpacked) + 1000))
        for item in unpacked:
            store.append(
                timestamp=item["ts"],
                event_type=EventType(item["type"]),
                source=item["src"],
                data=item["data"],
            )
        return store
