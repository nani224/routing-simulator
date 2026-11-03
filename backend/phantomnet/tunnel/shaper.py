"""Tunnel Egress Shaper: Live wire-level traffic morphing at socket egress.

Applies padding, timing quantization, and dummy frame injection directly
into the live socket stream before TCP transmission, ensuring that wire-level
captures and censor proxies observe the shaped byte stream in real time.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from phantomnet.tunnel.framing import FrameType, encode_frame

if TYPE_CHECKING:
    from phantomnet.ml.morphing import MorphingParameters


class TunnelEgressShaper:
    """Live socket egress traffic shaper attached to TunnelClient and TunnelServer."""

    def __init__(
        self,
        params: MorphingParameters | None = None,
        enabled: bool = False,
        seed: int = 42,
    ) -> None:
        self.params = params
        self.enabled = enabled
        self.rng = random.Random(seed)
        self.bytes_shaped_tx = 0
        self.dummies_injected = 0

    async def shape_and_write(
        self,
        writer: asyncio.StreamWriter,
        msg_type: FrameType | int,
        seq: int,
        payload: bytes,
    ) -> int:
        """Apply padding, delay, and write wire frame to live TCP socket."""
        if not self.enabled or self.params is None:
            frame = encode_frame(msg_type, seq, payload)
            writer.write(frame)
            await writer.drain()
            return len(frame)

        # 1. Size morphing / padding
        raw_len = len(payload)
        padded_payload = payload

        if self.params.morph_strength > 0:
            # Target size interpolation with bucket quantization
            target_size = raw_len
            if self.params.size_bucket > 0:
                target_size = (
                    (raw_len + self.params.size_bucket - 1)
                    // self.params.size_bucket
                    * self.params.size_bucket
                )
            pad_amount = max(0, target_size - raw_len)
            if pad_amount > 0:
                padded_payload = payload + (b"\x00" * pad_amount)

        # 2. Timing jitter / quantization
        if self.params.timing_quantization_ms > 0:
            delay_s = self.rng.uniform(0.0005, self.params.timing_quantization_ms / 1000.0)
            await asyncio.sleep(delay_s)

        frame = encode_frame(msg_type, seq, padded_payload)
        writer.write(frame)
        await writer.drain()
        self.bytes_shaped_tx += len(frame)

        # 3. Dummy frame injection
        if self.params.dummy_rate > 0 and self.rng.random() < self.params.dummy_rate:
            dummy_len = self.params.size_bucket if self.params.size_bucket > 0 else 64
            dummy_frame = encode_frame(FrameType.KEEPALIVE, seq + 10000, b"\x00" * dummy_len)
            writer.write(dummy_frame)
            await writer.drain()
            self.dummies_injected += 1
            self.bytes_shaped_tx += len(dummy_frame)

        return len(frame)
