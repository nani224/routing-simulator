"""Unit and Hypothesis property tests for PHANTOMNET Event Spine schema."""

from __future__ import annotations

import msgpack
from hypothesis import given
from hypothesis import strategies as st
from phantomnet.events import EventBatch, EventKind, PhantomEvent

# Hypothesis strategy for arbitrary valid PhantomEvent instances with standard 64-bit numbers
event_strategy = st.builds(
    PhantomEvent,
    version=st.just(1),
    seq=st.integers(min_value=1, max_value=1_000_000),
    t=st.floats(min_value=0.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    kind=st.sampled_from(list(EventKind)),
    flow_id=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    src=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
    dst=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
    size=st.one_of(st.none(), st.integers(min_value=0, max_value=65535)),
    dir=st.one_of(st.none(), st.sampled_from(["TX", "RX"])),
    state=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    mask_id=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    meta=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(
            st.integers(min_value=-9_223_372_036_854_775_808, max_value=9_223_372_036_854_775_807),
            st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
            st.text(max_size=20),
            st.booleans(),
        ),
        max_size=5,
    ),
)


def test_event_basic_creation_and_dict() -> None:
    """Verify basic instantiation and dictionary mapping."""
    ev = PhantomEvent(
        version=1,
        seq=1,
        t=0.123456,
        kind=EventKind.PKT_TX,
        flow_id="flow-1",
        src="127.0.0.1:4000",
        dst="127.0.0.1:8000",
        size=1420,
        dir="TX",
        state="ESTABLISHED",
        mask_id="plain",
        meta={"proto": "ChaCha20"},
    )
    d = ev.to_dict()
    assert d["seq"] == 1
    assert d["kind"] == "PKT_TX"
    assert d["size"] == 1420

    ev2 = PhantomEvent.from_dict(d)
    assert ev2 == ev


def test_msgpack_roundtrip() -> None:
    """Verify binary MessagePack serialization and deserialization."""
    ev = PhantomEvent(
        version=1,
        seq=42,
        t=1.5,
        kind=EventKind.HANDSHAKE_MSG,
        flow_id="flow-xx",
        size=32,
        dir="TX",
        meta={"step": 1},
    )
    raw = ev.to_msgpack()
    assert isinstance(raw, bytes)

    unpacked = msgpack.unpackb(raw, raw=False)
    assert unpacked["kind"] == "HANDSHAKE_MSG"
    assert unpacked["seq"] == 42

    restored = PhantomEvent.from_msgpack(raw)
    assert restored.seq == ev.seq
    assert restored.kind == ev.kind
    assert restored.meta == ev.meta


@given(ev=event_strategy)
def test_hypothesis_schema_msgpack_roundtrip(ev: PhantomEvent) -> None:
    """Property-based verification: any valid event survives MessagePack round-trip."""
    raw = ev.to_msgpack()
    restored = PhantomEvent.from_msgpack(raw)
    assert restored.version == ev.version
    assert restored.seq == ev.seq
    assert abs(restored.t - round(ev.t, 6)) < 1e-4
    assert restored.kind == ev.kind
    assert restored.flow_id == ev.flow_id
    assert restored.src == ev.src
    assert restored.dst == ev.dst
    assert restored.size == ev.size
    assert restored.dir == ev.dir
    assert restored.state == ev.state
    assert restored.mask_id == ev.mask_id


@given(ev=event_strategy)
def test_hypothesis_schema_dict_roundtrip(ev: PhantomEvent) -> None:
    """Property-based verification: any valid event survives dict round-trip."""
    d = ev.to_dict()
    restored = PhantomEvent.from_dict(d)
    assert restored.seq == ev.seq
    assert restored.kind == ev.kind
    assert restored.size == ev.size


def test_event_batch_msgpack() -> None:
    """Verify EventBatch container packing and unpacking."""
    ev1 = PhantomEvent(version=1, seq=1, t=0.01, kind=EventKind.CONN_STATE, state="INIT")
    ev2 = PhantomEvent(version=1, seq=2, t=0.02, kind=EventKind.PKT_TX, size=64)
    batch = EventBatch(batch_seq=10, timestamp=123.456, run_id="test-run", events=[ev1, ev2])

    raw = batch.to_msgpack()
    restored = EventBatch.from_msgpack(raw)

    assert restored.batch_seq == 10
    assert restored.run_id == "test-run"
    assert len(restored.events) == 2
    assert restored.events[0].kind == EventKind.CONN_STATE
    assert restored.events[1].kind == EventKind.PKT_TX
