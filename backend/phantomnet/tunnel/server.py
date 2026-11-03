"""Encrypted Tunnel Server terminating Noise transport and forwarding outbound flows."""

from __future__ import annotations

import asyncio
import contextlib
import time

from phantomnet.bus import PhantomEventBus, global_event_bus
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.tunnel.crypto import NoiseSession, TamperError
from phantomnet.tunnel.framing import FrameType, encode_frame, read_frame
from phantomnet.tunnel.replay_window import ReplayWindow


class TunnelServer:
    """Server endpoint accepting client connections, completing Noise handshake,

    and decrypting/forwarding transport traffic.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8443,
        event_bus: PhantomEventBus | None = None,
        static_private_key: bytes | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.event_bus = event_bus if event_bus is not None else global_event_bus
        self.static_private_key = static_private_key

        self._server: asyncio.Server | None = None
        self._running = False
        self._seq = 0

    async def start(self) -> None:
        """Bind socket and start accepting connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._running = True

    async def stop(self) -> None:
        """Gracefully stop server."""
        self._running = False
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        client_addr = f"{peer[0]}:{peer[1]}" if peer else "unknown_client"
        server_addr = f"{self.host}:{self.port}"
        flow_id = f"{client_addr}->{server_addr}"

        noise = NoiseSession(
            is_initiator=False,
            static_private_key=self.static_private_key,
        )
        replay_win = ReplayWindow(window_size=128)

        now = time.time()
        self.event_bus.publish_sync(
            PhantomEvent(
                version=1,
                seq=self.event_bus.current_seq + 1,
                t=now,
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                src=client_addr,
                dst=server_addr,
                state="HANDSHAKE_INIT",
                meta=noise.get_telemetry(),
            )
        )

        try:
            # Step 1: Read Handshake Msg 1 (-> e, 32B)
            f1 = await read_frame(reader)
            if not f1 or f1[0] != FrameType.HANDSHAKE:
                return
            noise.read_handshake_message(f1[2])
            self.event_bus.publish_sync(
                PhantomEvent(
                    version=1,
                    seq=self.event_bus.current_seq + 1,
                    t=time.time(),
                    kind=EventKind.HANDSHAKE_MSG,
                    flow_id=flow_id,
                    src=client_addr,
                    dst=server_addr,
                    size=len(f1[2]),
                    dir="RX",
                    state="HANDSHAKE_MSG_1",
                    meta={"step": 1, "payload": "-> e"},
                )
            )

            # Step 2: Send Handshake Msg 2 (<- e, ee, s, es, 96B)
            m2 = noise.write_handshake_message()
            writer.write(encode_frame(FrameType.HANDSHAKE, 1, m2))
            await writer.drain()
            self.event_bus.publish_sync(
                PhantomEvent(
                    version=1,
                    seq=self.event_bus.current_seq + 1,
                    t=time.time(),
                    kind=EventKind.HANDSHAKE_MSG,
                    flow_id=flow_id,
                    src=server_addr,
                    dst=client_addr,
                    size=len(m2),
                    dir="TX",
                    state="HANDSHAKE_MSG_2",
                    meta={"step": 2, "payload": "<- e, ee, s, es"},
                )
            )

            # Step 3: Read Handshake Msg 3 (-> s, se, 64B)
            f3 = await read_frame(reader)
            if not f3 or f3[0] != FrameType.HANDSHAKE:
                return
            noise.read_handshake_message(f3[2])
            self.event_bus.publish_sync(
                PhantomEvent(
                    version=1,
                    seq=self.event_bus.current_seq + 1,
                    t=time.time(),
                    kind=EventKind.HANDSHAKE_MSG,
                    flow_id=flow_id,
                    src=client_addr,
                    dst=server_addr,
                    size=len(f3[2]),
                    dir="RX",
                    state="HANDSHAKE_MSG_3",
                    meta={"step": 3, "payload": "-> s, se"},
                )
            )

            if not noise.handshake_finished:
                return

            self.event_bus.publish_sync(
                PhantomEvent(
                    version=1,
                    seq=self.event_bus.current_seq + 1,
                    t=time.time(),
                    kind=EventKind.CONN_STATE,
                    flow_id=flow_id,
                    src=client_addr,
                    dst=server_addr,
                    state="ESTABLISHED",
                    meta=noise.get_telemetry(),
                )
            )

            # Transport Data Loop
            outbound_seq = 1
            while self._running:
                frame_data = await read_frame(reader)
                if frame_data is None:
                    break

                msg_type, in_seq, payload = frame_data
                now = time.time()

                # Replay protection check
                if not replay_win.check_and_update(in_seq):
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.PKT_DROP,
                            flow_id=flow_id,
                            src=client_addr,
                            dst=server_addr,
                            size=len(payload),
                            dir="RX",
                            state="REPLAY_DETECTED",
                            meta={
                                "dropped_seq": in_seq,
                                "reason": "Anti-replay window rejected duplicate",
                            },
                        )
                    )
                    continue

                if msg_type == FrameType.CLOSE:
                    break

                if msg_type == FrameType.KEEPALIVE:
                    # Echo keepalive ack
                    writer.write(encode_frame(FrameType.KEEPALIVE, outbound_seq, b"PONG"))
                    outbound_seq += 1
                    await writer.drain()
                    continue

                if msg_type == FrameType.REKEY:
                    noise.rekey_inbound()
                    noise.rekey_outbound()
                    replay_win.reset()
                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.REKEY,
                            flow_id=flow_id,
                            src=client_addr,
                            dst=server_addr,
                            state="REKEYED",
                            meta=noise.get_telemetry(),
                        )
                    )
                    continue

                if msg_type == FrameType.DATA:
                    try:
                        plaintext = noise.decrypt(payload)
                    except TamperError:
                        self.event_bus.publish_sync(
                            PhantomEvent(
                                version=1,
                                seq=self.event_bus.current_seq + 1,
                                t=now,
                                kind=EventKind.PKT_DROP,
                                flow_id=flow_id,
                                src=client_addr,
                                dst=server_addr,
                                size=len(payload),
                                dir="RX",
                                state="TAMPER_DETECTED",
                                meta={"reason": "ChaCha20-Poly1305 MAC tag failure"},
                            )
                        )
                        continue

                    self.event_bus.publish_sync(
                        PhantomEvent(
                            version=1,
                            seq=self.event_bus.current_seq + 1,
                            t=now,
                            kind=EventKind.PKT_RX,
                            flow_id=flow_id,
                            src=client_addr,
                            dst=server_addr,
                            size=len(payload) + 16,
                            dir="RX",
                            state="ESTABLISHED",
                            meta={"payload_len": len(plaintext)},
                        )
                    )

                    # Handle SOCKS5 target proxying or local echo
                    response_payload = await self._dispatch_payload(plaintext)
                    if response_payload:
                        ciphertext = noise.encrypt(response_payload)
                        writer.write(encode_frame(FrameType.DATA, outbound_seq, ciphertext))
                        outbound_seq += 1
                        await writer.drain()

                        self.event_bus.publish_sync(
                            PhantomEvent(
                                version=1,
                                seq=self.event_bus.current_seq + 1,
                                t=time.time(),
                                kind=EventKind.PKT_TX,
                                flow_id=flow_id,
                                src=server_addr,
                                dst=client_addr,
                                size=len(ciphertext) + 16,
                                dir="TX",
                                state="ESTABLISHED",
                                meta={"payload_len": len(response_payload)},
                            )
                        )

        except Exception:
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _dispatch_payload(self, payload: bytes) -> bytes | None:
        """Handle unpacked tunnel payload: target TCP forward or HTTP echo."""
        if payload.startswith(b"PING"):
            return b"PONG"

        if len(payload) > 3 and payload.startswith(b"FWD:"):
            # Format: b"FWD:" + target_host + b":" + port + b"\n" + raw_req
            try:
                header, raw_req = payload[4:].split(b"\n", 1)
                t_host, t_port_str = header.decode("utf-8").split(":")
                t_port = int(t_port_str)
                r, w = await asyncio.open_connection(t_host, t_port)
                w.write(raw_req)
                await w.drain()
                resp = await r.read(65536)
                w.close()
                await w.wait_closed()
                return resp
            except Exception as e:
                err = str(e)
                body = f"HTTP/1.1 502 Bad Gateway\r\nContent-Length: {len(err)}\r\n\r\n{err}"
                return body.encode()

        return b"ECHO:" + payload
