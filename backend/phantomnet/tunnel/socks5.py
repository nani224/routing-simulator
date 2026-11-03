"""RFC 1928 SOCKS5 Front Door Proxy tunneling browser connections through PhantomNet."""

from __future__ import annotations

import asyncio
import contextlib
import socket
import struct

from phantomnet.tunnel.client import TunnelClient


class Socks5Server:
    """Local SOCKS5 proxy server allowing standard browsers and tools (curl, Playwright)

    to route HTTP/HTTPS traffic through the encrypted Noise tunnel.
    """

    def __init__(
        self,
        tunnel_client: TunnelClient,
        listen_host: str = "127.0.0.1",
        listen_port: int = 1080,
    ) -> None:
        self.tunnel_client = tunnel_client
        self.listen_host = listen_host
        self.listen_port = listen_port
        self._server: asyncio.Server | None = None
        self._running = False

    async def start(self) -> None:
        """Start listening for incoming SOCKS5 client connections."""
        self._server = await asyncio.start_server(
            self._handle_socks_connection,
            self.listen_host,
            self.listen_port,
        )
        self._running = True

    async def stop(self) -> None:
        """Stop SOCKS5 server."""
        self._running = False
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_socks_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            # 1. Negotiation: Client version & authentication methods
            ver_bytes = await reader.readexactly(2)
            ver, nmethods = ver_bytes[0], ver_bytes[1]
            if ver != 0x05:
                writer.close()
                return

            _methods = await reader.readexactly(nmethods)
            # Reply: Version 5, Method 0x00 (No Authentication Required)
            writer.write(b"\x05\x00")
            await writer.drain()

            # 2. Connection Request: VER | CMD | RSV | ATYP | DST.ADDR | DST.PORT
            req_header = await reader.readexactly(4)
            cmd = req_header[1]
            atyp = req_header[3]

            if cmd != 0x01:  # Only CONNECT supported
                writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")  # Command not supported
                await writer.drain()
                writer.close()
                return

            # Parse destination address
            if atyp == 0x01:  # IPv4
                addr_bytes = await reader.readexactly(4)
                target_host = socket.inet_ntoa(addr_bytes)
            elif atyp == 0x03:  # Domain name
                domain_len = (await reader.readexactly(1))[0]
                target_host = (await reader.readexactly(domain_len)).decode("utf-8")
            else:
                writer.write(
                    b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00"
                )  # Address type not supported
                await writer.drain()
                writer.close()
                return

            port_bytes = await reader.readexactly(2)
            target_port = struct.unpack(">H", port_bytes)[0]

            # Reply: Success (0x00), bound to 127.0.0.1:0
            writer.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
            await writer.drain()

            # 3. Tunneling Loop
            # Read first chunk of request data from browser/client
            client_data = await reader.read(65536)
            if client_data:
                # Wrap request into tunnel forward envelope: FWD:<target_host>:<target_port>\n<data>
                forward_envelope = f"FWD:{target_host}:{target_port}\n".encode() + client_data
                tunnel_response = await self.tunnel_client.send_data(forward_envelope)
                writer.write(tunnel_response)
                await writer.drain()

        except Exception:
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
