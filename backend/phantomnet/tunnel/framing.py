"""Binary length-prefix framing protocol with validation and anti-fuzzing bounds."""

from __future__ import annotations

import asyncio
import enum
import struct

MAGIC_BYTES = b"\xfa\x01"
HEADER_FORMAT = ">2sBBQI"  # magic (2B), msg_type (1B), flags (1B), seq (8B), payload_len (4B)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 16 bytes
MAX_PAYLOAD_SIZE = 65_536  # 64 KB safety cap against memory exhaustion attacks


class FrameType(enum.IntEnum):
    """Protocol message classifications in the encrypted tunnel wire frame."""

    HANDSHAKE = 1
    DATA = 2
    KEEPALIVE = 3
    REKEY = 4
    CLOSE = 5


class FramingError(ValueError):
    """Raised when encountering malformed, corrupted, or oversized wire frames."""


def encode_frame(
    msg_type: FrameType | int,
    seq: int,
    payload: bytes,
    flags: int = 0,
) -> bytes:
    """Encode a binary frame with 16-byte length-prefixed header."""
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise FramingError(
            f"Payload length {len(payload)} exceeds maximum allowed {MAX_PAYLOAD_SIZE} bytes"
        )
    if seq < 0:
        raise FramingError(f"Sequence number {seq} must be non-negative")

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC_BYTES,
        int(msg_type),
        flags,
        seq,
        len(payload),
    )
    return header + payload


def decode_frame_header(header_bytes: bytes) -> tuple[FrameType, int, int, int]:
    """Parse and validate the 16-byte frame header.

    Returns:
        tuple of (msg_type, flags, seq, payload_len)

    Raises:
        FramingError: On invalid magic, unknown type, or oversized payload.
    """
    if len(header_bytes) != HEADER_SIZE:
        raise FramingError(f"Expected header size {HEADER_SIZE}, got {len(header_bytes)}")

    magic, raw_type, flags, seq, payload_len = struct.unpack(HEADER_FORMAT, header_bytes)
    if magic != MAGIC_BYTES:
        raise FramingError(f"Invalid frame magic: {magic!r} != {MAGIC_BYTES!r}")

    try:
        msg_type = FrameType(raw_type)
    except ValueError as e:
        raise FramingError(f"Unknown frame message type code: {raw_type}") from e

    if payload_len > MAX_PAYLOAD_SIZE:
        raise FramingError(f"Header specifies payload length {payload_len} > {MAX_PAYLOAD_SIZE}")

    return msg_type, flags, seq, payload_len


async def read_frame(
    reader: asyncio.StreamReader,
) -> tuple[FrameType, int, bytes] | None:
    """Asynchronously read an exact length-prefixed frame from a stream.

    Returns:
        tuple of (msg_type, seq, payload), or None on clean EOF.
    """
    try:
        header_bytes = await reader.readexactly(HEADER_SIZE)
    except asyncio.IncompleteReadError as e:
        if len(e.partial) == 0:
            return None
        raise FramingError(f"Incomplete frame header received: {len(e.partial)} bytes") from e

    msg_type, _flags, seq, payload_len = decode_frame_header(header_bytes)

    if payload_len == 0:
        return msg_type, seq, b""

    try:
        payload = await reader.readexactly(payload_len)
    except asyncio.IncompleteReadError as e:
        raise FramingError(
            f"Incomplete frame payload: expected {payload_len}, got {len(e.partial)}"
        ) from e

    return msg_type, seq, payload
