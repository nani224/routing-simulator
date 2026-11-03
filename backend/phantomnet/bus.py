"""In-process asynchronous Pub/Sub Event Bus and append-only Event Store for PHANTOMNET."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

import msgpack

from phantomnet.events import EventKind, PhantomEvent


class PhantomEventBus:
    """Thread-safe and async-safe append-only Event Bus and Store.

    Maintains:
    - In-process pub/sub broadcasting to async subscriber queues.
    - Append-only log with sliding window pruning.
    - Incremental cryptographic SHA-256 run hash for determinism verification.
    - Temporal range slicing and replay iterators.
    - JSONL and MessagePack export/import.
    """

    def __init__(self, run_id: str = "default", max_events: int = 100_000) -> None:
        self.run_id = run_id
        self.max_events = max_events
        self._events: list[PhantomEvent] = []
        self._seq: int = 0
        self._hasher = hashlib.sha256()
        self._subscribers: set[asyncio.Queue[PhantomEvent]] = set()
        self._lock = asyncio.Lock()

    @property
    def current_seq(self) -> int:
        return self._seq

    def count(self) -> int:
        return len(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def get_run_hash(self) -> str:
        """Return the current incremental SHA-256 digest of all recorded events."""
        return self._hasher.hexdigest()

    def publish_sync(self, event: PhantomEvent) -> PhantomEvent:
        """Synchronously append an event, update run hash, and notify subscribers."""
        if event.seq <= self._seq:
            # Re-index if needed to maintain absolute sequence monotonicity
            self._seq += 1
            event = PhantomEvent(
                version=event.version,
                seq=self._seq,
                t=event.t,
                kind=event.kind,
                flow_id=event.flow_id,
                src=event.src,
                dst=event.dst,
                size=event.size,
                dir=event.dir,
                state=event.state,
                mask_id=event.mask_id,
                meta=event.meta,
            )
        else:
            self._seq = event.seq

        self._events.append(event)
        self._hasher.update(event.canonical_bytes())

        # Enforce memory safety cap
        if len(self._events) > self.max_events:
            drop_count = self.max_events // 10
            del self._events[:drop_count]

        # Dispatch to active subscribers
        dead_queues: list[asyncio.Queue[PhantomEvent]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest item to prevent memory blowout on slow consumer
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
            except Exception:
                dead_queues.append(q)

        for dead in dead_queues:
            self._subscribers.discard(dead)

        return event

    async def publish(self, event: PhantomEvent) -> PhantomEvent:
        """Asynchronously publish an event to the bus."""
        return self.publish_sync(event)

    def subscribe(self, maxsize: int = 5000) -> asyncio.Queue[PhantomEvent]:
        """Subscribe to the live event stream."""
        q: asyncio.Queue[PhantomEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[PhantomEvent]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(q)

    def get_all(self) -> list[PhantomEvent]:
        """Retrieve all recorded events in the buffer."""
        return list(self._events)

    def get_range(
        self,
        start_t: float = 0.0,
        end_t: float | None = None,
        kinds: set[EventKind] | None = None,
    ) -> list[PhantomEvent]:
        """Query events within a time slice, optionally filtered by event kind."""
        results: list[PhantomEvent] = []
        for e in self._events:
            if e.t < start_t:
                continue
            if end_t is not None and e.t > end_t:
                break
            if kinds is not None and e.kind not in kinds:
                continue
            results.append(e)
        return results

    def get_since_seq(self, last_seq: int, limit: int = 1000) -> list[PhantomEvent]:
        """Fetch newly recorded events since last_seq for incremental streaming."""
        results: list[PhantomEvent] = []
        for e in self._events:
            if e.seq > last_seq:
                results.append(e)
                if len(results) >= limit:
                    break
        return results

    def clear(self) -> None:
        """Reset the event store and sequence counter."""
        self._events.clear()
        self._seq = 0
        self._hasher = hashlib.sha256()

    def export_jsonl(self, path: Path | str) -> None:
        """Export all recorded events to a newline-delimited JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e.to_dict()) + "\n")

    def export_msgpack(self, path: Path | str) -> None:
        """Export all recorded events to a binary MessagePack file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        packed = [e.to_dict() for e in self._events]
        p.write_bytes(msgpack.packb(packed, use_bin_type=True))

    @classmethod
    def from_jsonl(cls, path: Path | str, run_id: str = "replay") -> PhantomEventBus:
        """Load an EventBus from a recorded JSONL trace."""
        p = Path(path)
        bus = cls(run_id=run_id)
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                bus.publish_sync(PhantomEvent.from_dict(d))
        return bus

    @classmethod
    def from_msgpack(cls, path: Path | str, run_id: str = "replay") -> PhantomEventBus:
        """Load an EventBus from a recorded binary MessagePack trace."""
        p = Path(path)
        raw_data = p.read_bytes()
        items = msgpack.unpackb(raw_data, raw=False)
        bus = cls(run_id=run_id)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    bus.publish_sync(PhantomEvent.from_dict(item))
        return bus

    async def replay_stream(
        self,
        start_t: float = 0.0,
        end_t: float | None = None,
        speed: float = 1.0,
    ) -> AsyncIterator[PhantomEvent]:
        """Asynchronously stream events in temporal order, paced by the speed factor."""
        events = self.get_range(start_t=start_t, end_t=end_t)
        if not events:
            return

        last_t = events[0].t
        for e in events:
            delay = (e.t - last_t) / max(speed, 0.01)
            if delay > 0:
                await asyncio.sleep(delay)
            last_t = e.t
            yield e


# Global shared instance for live tunnel and simulator aggregation
global_event_bus = PhantomEventBus(run_id="default")

