"""On-path Censor Proxy with metadata inspection, token-bucket throttling, and link impairment."""

from __future__ import annotations

import asyncio
import random
import time

from phantomnet.bus import PhantomEventBus, global_event_bus
from phantomnet.censor.interface import BaseCensor, CensorAction
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.tunnel.framing import encode_frame, read_frame


class TokenBucket:
    """Token bucket rate limiter for traffic throttling."""

    def __init__(self, rate_bps: float, capacity_bytes: float) -> None:
        self.rate = rate_bps
        self.capacity = capacity_bytes
        self.tokens = capacity_bytes
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, num_bytes: int) -> float:
        """Consume tokens or return delay time required until sufficient tokens exist."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= num_bytes:
                self.tokens -= num_bytes
                return 0.0

            deficit = num_bytes - self.tokens
            delay = deficit / max(self.rate, 1.0)
            self.tokens = 0.0
            return delay


class CensorProxy:
    """On-path TCP proxy intercepting traffic between Client and Server.

    Inspects METADATA ONLY (size, direction, timestamp).
    Emits CENSOR_SCORE and CENSOR_ACTION events to the Event Spine.
    Enforces ALLOW, THROTTLE (token-bucket delay), and BLOCK (gate-slam drops).
    Optionally applies link emulation parameters (latency, jitter, packet loss).
    """

    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        target_host: str,
        target_port: int,
        censor: BaseCensor,
        event_bus: PhantomEventBus | None = None,
        latency_ms: float = 0.0,
        jitter_ms: float = 0.0,
        loss_rate: float = 0.0,
        throttle_rate_bps: float = 64_000.0,  # 64 KB/s default throttle
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.censor = censor
        self.event_bus = event_bus if event_bus is not None else global_event_bus

        self.latency_ms = latency_ms
        self.jitter_ms = jitter_ms
        self.loss_rate = loss_rate

        self._token_bucket = TokenBucket(
            rate_bps=throttle_rate_bps,
            capacity_bytes=throttle_rate_bps * 0.5,
        )
        self._server: asyncio.Server | None = None
        self._running = False
        self._rng = random.Random(42)

    async def start(self) -> None:
        """Start listening for incoming client connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.listen_host,
            self.listen_port,
        )
        self._running = True

    async def stop(self) -> None:
        """Stop server and close connections."""
        self._running = False
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        try:
            target_reader, target_writer = await asyncio.open_connection(
                self.target_host,
                self.target_port,
            )
        except Exception:
            client_writer.close()
            await client_writer.wait_closed()
            return

        flow_id = f"censor:{self.listen_port}->{self.target_port}"

        # Bidirectional proxy tasks
        client_to_server = asyncio.create_task(
            self._forward_leg(client_reader, target_writer, "TX", flow_id)
        )
        server_to_client = asyncio.create_task(
            self._forward_leg(target_reader, client_writer, "RX", flow_id)
        )

        _done, pending = await asyncio.wait(
            [client_to_server, server_to_client],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        target_writer.close()
        client_writer.close()

    async def _forward_leg(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        direction: str,
        flow_id: str,
    ) -> None:
        try:
            while self._running:
                frame_data = await read_frame(reader)
                if frame_data is None:
                    break

                msg_type, seq, payload = frame_data
                size = 16 + len(payload)  # Exact wire length including 16B header
                now = time.time()

                # Censor metadata inspection
                decision = self.censor.inspect(size=size, direction=direction, timestamp=now)

                # 1. Emit CENSOR_SCORE event
                self.event_bus.publish_sync(
                    PhantomEvent(
                        version=1,
                        seq=self.event_bus.current_seq + 1,
                        t=now,
                        kind=EventKind.CENSOR_SCORE,
                        flow_id=flow_id,
                        src=f"censor:{self.listen_port}",
                        size=size,
                        dir=direction,
                        state="INSPECTING",
                        meta={
                            "score": decision.score,
                            "confidence": decision.confidence,
                            "censor_name": self.censor.name,
                            **decision.metadata,
                        },
                    )
                )

                # 2. Check Action: BLOCK
                if decision.action == CensorAction.BLOCK:
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.CENSOR_ACTION,
                            flow_id=flow_id,
                            src=f"censor:{self.listen_port}",
                            size=size,
                            dir=direction,
                            state="BLOCKED",
                            meta={"action": "BLOCK", "reason": decision.reason},
                        )
                    )
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.PKT_DROP,
                            flow_id=flow_id,
                            src=f"censor:{self.listen_port}",
                            size=size,
                            dir=direction,
                            state="BLOCKED",
                            meta={"reason": decision.reason},
                        )
                    )
                    # Gate slam: drop packet and terminate connection
                    break

                # 3. Check Action: THROTTLE
                if decision.action == CensorAction.THROTTLE:
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.CENSOR_ACTION,
                            flow_id=flow_id,
                            src=f"censor:{self.listen_port}",
                            size=size,
                            dir=direction,
                            state="THROTTLED",
                            meta={"action": "THROTTLE", "reason": decision.reason},
                        )
                    )
                    throttle_delay = await self._token_bucket.consume(size)
                    if throttle_delay > 0:
                        await asyncio.sleep(min(throttle_delay, 1.0))

                # 4. Link Emulation: Simulated loss
                if self.loss_rate > 0.0 and self._rng.random() < self.loss_rate:
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.PKT_DROP,
                            flow_id=flow_id,
                            src=f"link:{self.listen_port}",
                            size=size,
                            dir=direction,
                            state="LINK_LOSS",
                            meta={"loss_rate": self.loss_rate},
                        )
                    )
                    continue

                # 5. Link Emulation: Latency & Jitter
                if self.latency_ms > 0.0 or self.jitter_ms > 0.0:
                    delay_s = self.latency_ms / 1000.0
                    if self.jitter_ms > 0.0:
                        jitter_s = self._rng.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
                        delay_s = max(0.001, delay_s + jitter_s)
                    await asyncio.sleep(delay_s)

                wire_frame = encode_frame(msg_type, seq, payload)
                writer.write(wire_frame)
                await writer.drain()

        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
