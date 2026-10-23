"""Unit tests for EventStore and SimEvent serialization."""

import pytest
from routelab.core.events import EventStore, EventType


def test_event_store_append_and_query() -> None:
    store = EventStore(max_events=100)
    store.append(0.1, EventType.LINK_STATE, "A<->B", {"is_up": True})
    store.append(0.2, EventType.PACKET_SENT, "A", {"dst": "B"})
    store.append(0.3, EventType.PACKET_DELIVERED, "B", {"src": "A"})

    assert store.count() == 3

    range_events = store.get_range(start_time=0.15, end_time=0.25)
    assert len(range_events) == 1
    assert range_events[0].event_type == EventType.PACKET_SENT

    type_filtered = store.get_range(event_types={EventType.LINK_STATE})
    assert len(type_filtered) == 1
    assert type_filtered[0].source == "A<->B"


def test_event_store_msgpack_roundtrip() -> None:
    store = EventStore()
    store.append(1.5, EventType.CONVERGENCE, "engine", {"duration": 0.42})
    store.append(2.0, EventType.NODE_STATE, "R1", {"status": "crashed"})

    packed = store.to_msgpack()
    assert isinstance(packed, bytes)

    restored = EventStore.from_msgpack(packed)
    assert restored.count() == 2
    events = restored.get_all()
    assert events[0].timestamp == pytest.approx(1.5)
    assert events[0].event_type == EventType.CONVERGENCE
    assert events[1].data["status"] == "crashed"


def test_event_store_bounded_memory() -> None:
    store = EventStore(max_events=20)
    for i in range(30):
        store.append(float(i), EventType.LOG_MESSAGE, "test", {"i": i})

    assert store.count() <= 20
