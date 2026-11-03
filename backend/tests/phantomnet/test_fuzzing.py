"""Fuzzing tests for wire framing protocol: 10,000 cases with zero unhandled crashes or hangs."""

from __future__ import annotations

import struct

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from phantomnet.tunnel.framing import (
    FramingError,
    decode_frame_header,
    encode_frame,
)


@settings(max_examples=10_000, deadline=None)
@given(raw_bytes=st.binary(min_size=0, max_size=128))
def test_frame_header_fuzzing_10k_cases(raw_bytes: bytes) -> None:
    """Fuzz the frame header parser across 10,000 arbitrary byte patterns.

    The parser must cleanly reject invalid input with FramingError without unhandled crashes.
    """
    try:
        msg_type, _flags, seq, payload_len = decode_frame_header(raw_bytes)
        # If it parsed without error, it must satisfy all protocol invariants:
        assert len(raw_bytes) == 16
        assert raw_bytes[:2] == b"\xfa\x01"
        assert 1 <= int(msg_type) <= 5
        assert 0 <= payload_len <= 65_536
        assert seq >= 0
    except FramingError:
        # Controlled protocol rejection is the expected outcome for malformed bytes
        pass


@settings(max_examples=500, deadline=None)
@given(
    msg_type=st.integers(min_value=1, max_value=5),
    seq=st.integers(min_value=0, max_value=2**32 - 1),
    payload=st.binary(min_size=0, max_size=2048),
)
def test_frame_encode_decode_roundtrip_fuzz(msg_type: int, seq: int, payload: bytes) -> None:
    """Verify that any validly generated frame round-trips perfectly."""
    wire = encode_frame(msg_type, seq, payload)
    header = wire[:16]
    parsed_type, _flags, parsed_seq, parsed_len = decode_frame_header(header)

    assert int(parsed_type) == msg_type
    assert parsed_seq == seq
    assert parsed_len == len(payload)
    assert wire[16:] == payload


def test_frame_oversized_payload_rejected() -> None:
    """Ensure payloads > 64KB are rejected immediately to prevent memory attacks."""
    huge_payload = b"X" * (65_536 + 1)
    try:
        encode_frame(2, 1, huge_payload)
        pytest.fail("Should have rejected oversized payload")
    except FramingError:
        pass

    # Malicious header specifying 4GB payload length
    fake_header = struct.pack(">2sBBQI", b"\xfa\x01", 2, 0, 1, 0xFFFFFFFF)
    try:
        decode_frame_header(fake_header)
        pytest.fail("Should have rejected malicious header length")
    except FramingError:
        pass
