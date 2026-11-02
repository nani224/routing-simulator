"""Unit tests for PhantomEventBus pub/sub, append-only log, and export/import."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from phantomnet.bus import PhantomEventBus
from phantomnet.events import EventKind, PhantomEvent


@pytest.mark.asyncio
async def test_bus_pubsub() -> None:
    """Verify in-process pub/sub broadcasting to async subscribers."""
    bus = PhantomEventBus(run_id="test-pubsub")
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    ev = PhantomEvent(
        version=1,
        seq=1,
        t=1.0,
        kind=EventKind.PKT_TX,
        size=1420,
    )
    await bus.publish(ev)

    received1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    received2 = await asyncio.wait_for(q2.get(), timeout=1.0)

    assert received1.seq == 1
    assert received1.size == 1420
    assert received2.seq == 1

    bus.unsubscribe(q1)
    bus.unsubscribe(q2)


def test_bus_append_and_query() -> None:
    """Verify temporal range filtering and sequence retrieval."""
    bus = PhantomEventBus(run_id="test-query")
    for i in range(1, 11):
        bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=i,
                t=float(i) * 0.5,
                kind=EventKind.PKT_TX if i % 2 == 0 else EventKind.PKT_RX,
                size=100 * i,
            )
        )

    assert bus.count() == 10
    assert bus.current_seq == 10

    # Range test
    slice_events = bus.get_range(start_t=1.5, end_t=3.5)
    assert len(slice_events) == 5  # t=1.5, 2.0, 2.5, 3.0, 3.5

    # Kind filter test
    tx_events = bus.get_range(start_t=0.0, kinds={EventKind.PKT_TX})
    assert len(tx_events) == 5
    assert all(e.kind == EventKind.PKT_TX for e in tx_events)

    # Since seq test
    recent = bus.get_since_seq(last_seq=7)
    assert len(recent) == 3
    assert [e.seq for e in recent] == [8, 9, 10]


def test_bus_jsonl_export_import(tmp_path: Path) -> None:
    """Verify JSONL export and roundtrip reconstruction."""
    bus = PhantomEventBus(run_id="test-jsonl")
    for i in range(1, 6):
        bus.publish_sync(PhantomEvent(version=1, seq=i, t=float(i), kind=EventKind.PKT_TX, size=64))

    jsonl_path = tmp_path / "events.jsonl"
    bus.export_jsonl(jsonl_path)
    assert jsonl_path.exists()

    restored = PhantomEventBus.from_jsonl(jsonl_path, run_id="restored-jsonl")
    assert restored.count() == 5
    assert restored.get_run_hash() == bus.get_run_hash()


def test_bus_msgpack_export_import(tmp_path: Path) -> None:
    """Verify MessagePack binary export and roundtrip reconstruction."""
    bus = PhantomEventBus(run_id="test-msgpack")
    for i in range(1, 6):
        bus.publish_sync(
            PhantomEvent(version=1, seq=i, t=float(i), kind=EventKind.PKT_RX, size=128)
        )

    msgpack_path = tmp_path / "events.msgpack"
    bus.export_msgpack(msgpack_path)
    assert msgpack_path.exists()

    restored = PhantomEventBus.from_msgpack(msgpack_path, run_id="restored-msgpack")
    assert restored.count() == 5
    assert restored.get_run_hash() == bus.get_run_hash()


def test_bus_sliding_window_pruning() -> None:
    """Verify bounded memory pruning under high event counts."""
    cap = 50
    bus = PhantomEventBus(run_id="test-pruning", max_events=cap)
    for i in range(1, 65):
        bus.publish_sync(PhantomEvent(version=1, seq=i, t=float(i), kind=EventKind.PKT_TX))

    # Total stored should be capped around max_events
    assert bus.count() <= cap
