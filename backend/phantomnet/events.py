"""Canonical Event Spine schema, serialization, and validation models for PHANTOMNET."""

from __future__ import annotations

import enum
import json
from typing import Any

import msgpack
from pydantic import BaseModel, ConfigDict, Field


class EventKind(enum.StrEnum):
    """The 13 canonical event kinds emitted across the PHANTOMNET event spine."""

    HANDSHAKE_MSG = "HANDSHAKE_MSG"
    CONN_STATE = "CONN_STATE"
    PKT_TX = "PKT_TX"
    PKT_RX = "PKT_RX"
    PKT_DROP = "PKT_DROP"
    REKEY = "REKEY"
    CENSOR_SCORE = "CENSOR_SCORE"
    CENSOR_ACTION = "CENSOR_ACTION"
    MASK_SWITCH = "MASK_SWITCH"
    POLICY_DECISION = "POLICY_DECISION"
    ROUTE_CHANGE = "ROUTE_CHANGE"
    TRAIN_ROUND = "TRAIN_ROUND"
    BENCH_MARK = "BENCH_MARK"


class PhantomEvent(BaseModel):
    """Typed canonical event model.

    Attributes:
        version: Schema version for forward/backward compatibility.
        seq: Monotonically increasing sequence number (1-based per run).
        t: High-resolution timestamp in seconds.
        kind: Canonical event classification.
        flow_id: Identifier for the logical stream or socket pair.
        src: Origin socket or node descriptor.
        dst: Destination socket or node descriptor.
        size: Length in bytes (proportional conduit display and barcode strip).
        dir: Direction ('TX' for outbound, 'RX' for inbound).
        state: Connection or censor state machine status string.
        mask_id: Current active masking/shaping profile identifier.
        meta: Arbitrary payload telemetry for inspectors and gauges.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )

    version: int = Field(default=1, description="Schema version number")
    seq: int = Field(..., ge=1, description="1-based sequence index")
    t: float = Field(..., ge=0.0, description="Timestamp in seconds")
    kind: EventKind = Field(..., description="Canonical event classification")
    flow_id: str | None = Field(default=None, description="Flow ID")
    src: str | None = Field(default=None, description="Source address/identifier")
    dst: str | None = Field(default=None, description="Destination address/identifier")
    size: int | None = Field(default=None, ge=0, description="Packet size in bytes")
    dir: str | None = Field(default=None, description="Direction flag (TX or RX)")
    state: str | None = Field(default=None, description="State machine description")
    mask_id: str | None = Field(default=None, description="Active shaping mask ID")
    meta: dict[str, Any] = Field(default_factory=dict, description="Metadata key-value map")

    def to_dict(self) -> dict[str, Any]:
        """Convert event to primitive dict matching the canonical schema."""
        return {
            "version": self.version,
            "seq": self.seq,
            "t": round(self.t, 6),
            "kind": self.kind.value,
            "flow_id": self.flow_id,
            "src": self.src,
            "dst": self.dst,
            "size": self.size,
            "dir": self.dir,
            "state": self.state,
            "mask_id": self.mask_id,
            "meta": self.meta,
        }

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation used for SHA-256 run hash computation."""
        d = self.to_dict()
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_msgpack(self) -> bytes:
        """Serialize event into binary msgpack wire format."""
        raw = msgpack.packb(self.to_dict(), use_bin_type=True)
        return bytes(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhantomEvent:
        """Construct a PhantomEvent from a dictionary with validation."""
        kind_val = data.get("kind")
        if isinstance(kind_val, str):
            data = {**data, "kind": EventKind(kind_val)}
        return cls(**data)

    @classmethod
    def from_msgpack(cls, raw: bytes) -> PhantomEvent:
        """Deserialize a PhantomEvent from binary MessagePack payload."""
        unpacked = msgpack.unpackb(raw, raw=False)
        if not isinstance(unpacked, dict):
            raise ValueError(f"Expected dict from msgpack payload, got {type(unpacked)}")
        typed_dict: dict[str, Any] = {str(k): v for k, v in unpacked.items()}
        return cls.from_dict(typed_dict)


class EventBatch(BaseModel):
    """Batched wire transport frame for 60 Hz WebSocket delivery."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(default="event_batch")
    batch_seq: int = Field(..., ge=0)
    timestamp: float = Field(..., ge=0.0)
    run_id: str = Field(default="live")
    events: list[PhantomEvent] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "batch_seq": self.batch_seq,
            "timestamp": round(self.timestamp, 6),
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self.events],
        }

    def to_msgpack(self) -> bytes:
        raw = msgpack.packb(self.to_dict(), use_bin_type=True)
        return bytes(raw)

    @classmethod
    def from_msgpack(cls, raw: bytes) -> EventBatch:
        unpacked = msgpack.unpackb(raw, raw=False)
        if not isinstance(unpacked, dict):
            raise ValueError(f"Expected dict, got {type(unpacked)}")
        events_raw = unpacked.get("events", [])
        events: list[PhantomEvent] = [
            PhantomEvent.from_dict({str(k): v for k, v in item.items()}) for item in events_raw
        ]
        return cls(
            type=str(unpacked.get("type", "event_batch")),
            batch_seq=int(unpacked.get("batch_seq", 0)),
            timestamp=float(unpacked.get("timestamp", 0.0)),
            run_id=str(unpacked.get("run_id", "live")),
            events=events,
        )
