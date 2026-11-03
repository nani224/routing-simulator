"""Encrypted Tunnel Client managing Noise transport, automatic reconnects, and rekeying."""

from __future__ import annotations

import asyncio
import contextlib
import time

from phantomnet.bus import PhantomEventBus, global_event_bus
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.tunnel.crypto import NoiseSession
from phantomnet.tunnel.framing import FrameType, encode_frame, read_frame
from phantomnet.tunnel.replay_window import ReplayWindow


class TunnelClient:
    """Client endpoint connecting to TunnelServer directly or through CensorProxy."""

    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 8443,
        event_bus: PhantomEventBus | None = None,
        static_private_key: bytes | None = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 25,
    ) -> None:
        self.server_host = server_host
        self.server_port = server_port
        self.event_bus = event_bus if event_bus is not None else global_event_bus
        self.static_private_key = static_private_key
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._noise: NoiseSession | None = None
        self._replay_win: ReplayWindow = ReplayWindow(window_size=128)
        self._seq = 1
        self._connected = False
        self._lock = asyncio.Lock()
        self.local_addr = "127.0.0.1:0"

    @property
    def is_connected(self) -> bool:
        return self._connected and self._noise is not None and self._noise.handshake_finished

    async def connect(self) -> None:
        """Establish TCP connection and complete the 3-step Noise XX handshake."""
        async with self._lock:
            await self._do_connect_and_handshake()

    async def _do_connect_and_handshake(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self.server_host,
            self.server_port,
        )
        peer = self._writer.get_extra_info("sockname")
        self.local_addr = f"{peer[0]}:{peer[1]}" if peer else "client"
        server_addr = f"{self.server_host}:{self.server_port}"
        flow_id = f"{self.local_addr}->{server_addr}"

        self._noise = NoiseSession(
            is_initiator=True,
            static_private_key=self.static_private_key,
        )
        self._replay_win.reset()
        self._seq = 1

        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                src=self.local_addr,
                dst=server_addr,
                state="HANDSHAKE_INIT",
                meta=self._noise.get_telemetry(),
            )
        )

        # Step 1: Send Handshake Msg 1 (-> e, 32B)
        m1 = self._noise.write_handshake_message()
        self._writer.write(encode_frame(FrameType.HANDSHAKE, self._seq, m1))
        self._seq += 1
        await self._writer.drain()
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.HANDSHAKE_MSG,
                flow_id=flow_id,
                src=self.local_addr,
                dst=server_addr,
                size=len(m1),
                dir="TX",
                state="HANDSHAKE_MSG_1",
                meta={"step": 1, "payload": "-> e"},
            )
        )

        # Step 2: Read Handshake Msg 2 (<- e, ee, s, es, 96B)
        f2 = await read_frame(self._reader)
        if not f2 or f2[0] != FrameType.HANDSHAKE:
            raise ConnectionError("Failed to receive Noise handshake message 2")
        self._noise.read_handshake_message(f2[2])
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.HANDSHAKE_MSG,
                flow_id=flow_id,
                src=server_addr,
                dst=self.local_addr,
                size=len(f2[2]),
                dir="RX",
                state="HANDSHAKE_MSG_2",
                meta={"step": 2, "payload": "<- e, ee, s, es"},
            )
        )

        # Step 3: Send Handshake Msg 3 (-> s, se, 64B)
        m3 = self._noise.write_handshake_message()
        self._writer.write(encode_frame(FrameType.HANDSHAKE, self._seq, m3))
        self._seq += 1
        await self._writer.drain()
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.HANDSHAKE_MSG,
                flow_id=flow_id,
                src=self.local_addr,
                dst=server_addr,
                size=len(m3),
                dir="TX",
                state="HANDSHAKE_MSG_3",
                meta={"step": 3, "payload": "-> s, se"},
            )
        )

        if not self._noise.handshake_finished:
            raise ConnectionError("Noise handshake did not finish after 3 messages")

        self._connected = True
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                src=self.local_addr,
                dst=server_addr,
                state="ESTABLISHED",
                meta=self._noise.get_telemetry(),
            )
        )

    async def send_data(self, data: bytes) -> bytes:
        """Encrypt, frame, and transmit payload, then await and return decrypted response."""
        async with self._lock:
            for attempt in range(self.max_reconnect_attempts if self.auto_reconnect else 1):
                try:
                    if (
                        not self._connected
                        or self._noise is None
                        or not self._writer
                        or not self._reader
                    ):
                        await self._do_connect_and_handshake()

                    assert self._noise is not None
                    assert self._writer is not None
                    assert self._reader is not None

                    if self._noise.should_rekey():
                        await self._do_rekey()

                    ciphertext = self._noise.encrypt(data)
                    frame = encode_frame(FrameType.DATA, self._seq, ciphertext)
                    seq_used = self._seq
                    self._seq += 1

                    self._writer.write(frame)
                    await self._writer.drain()

                    now = time.time()
                    flow_id = f"{self.local_addr}->{self.server_host}:{self.server_port}"
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.PKT_TX,
                            flow_id=flow_id,
                            src=self.local_addr,
                            dst=f"{self.server_host}:{self.server_port}",
                            size=len(frame),
                            dir="TX",
                            state="ESTABLISHED",
                            meta={"payload_len": len(data), "frame_seq": seq_used},
                        )
                    )

                    resp_frame = await read_frame(self._reader)
                    if resp_frame is None:
                        raise ConnectionResetError("Server closed connection")

                    msg_type, resp_seq, resp_payload = resp_frame
                    if not self._replay_win.check_and_update(resp_seq):
                        raise ConnectionError(f"Duplicate sequence number: {resp_seq}")

                    plaintext = self._noise.decrypt(resp_payload)
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=time.time(),
                            kind=EventKind.PKT_RX,
                            flow_id=flow_id,
                            src=f"{self.server_host}:{self.server_port}",
                            dst=self.local_addr,
                            size=len(resp_payload) + 16,
                            dir="RX",
                            state="ESTABLISHED",
                            meta={"payload_len": len(plaintext), "frame_seq": resp_seq},
                        )
                    )
                    return plaintext

                except (
                    ConnectionError,
                    BrokenPipeError,
                    ConnectionResetError,
                    asyncio.IncompleteReadError,
                ):
                    self._connected = False
                    if self._writer:
                        self._writer.close()
                    if not self.auto_reconnect or attempt == self.max_reconnect_attempts - 1:
                        raise
                    await asyncio.sleep(0.05 * (attempt + 1))

            raise ConnectionError("Exceeded maximum reconnect attempts")

    async def rekey(self) -> None:
        """Trigger an explicit session rekey ritual."""
        async with self._lock:
            await self._do_rekey()

    async def _do_rekey(self) -> None:
        if not self._noise or not self._writer:
            return
        self._noise.rekey_outbound()
        self._noise.rekey_inbound()
        self._replay_win.reset()

        frame = encode_frame(FrameType.REKEY, self._seq, b"REKEY")
        self._seq += 1
        self._writer.write(frame)
        await self._writer.drain()

        flow_id = f"{self.local_addr}->{self.server_host}:{self.server_port}"
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=time.time(),
                kind=EventKind.REKEY,
                flow_id=flow_id,
                src=self.local_addr,
                dst=f"{self.server_host}:{self.server_port}",
                size=len(frame),
                dir="TX",
                state="REKEYED",
                meta=self._noise.get_telemetry(),
            )
        )

    async def close(self) -> None:
        """Close tunnel connection cleanly."""
        self._connected = False
        if self._writer is not None:
            with contextlib.suppress(Exception):
                self._writer.write(encode_frame(FrameType.CLOSE, self._seq, b""))
                await self._writer.drain()
                self._writer.close()
                await self._writer.wait_closed()
            self._writer = None
            self._reader = None
