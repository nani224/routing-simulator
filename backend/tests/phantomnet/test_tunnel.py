"""End-to-end integration tests: real socket tunnel, SOCKS5, reconnects, and blocking."""

from __future__ import annotations

import asyncio
import contextlib
import socket
import struct

import pytest
from phantomnet.bus import PhantomEventBus
from phantomnet.censor.censors import RuleBasedCensor
from phantomnet.censor.proxy import CensorProxy
from phantomnet.events import EventKind
from phantomnet.tunnel.client import TunnelClient
from phantomnet.tunnel.server import TunnelServer
from phantomnet.tunnel.socks5 import Socks5Server


def get_free_port() -> int:
    """Obtain an available ephemeral loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.asyncio
async def test_real_socket_tunnel_roundtrip() -> None:
    """Verify client and server over real sockets complete handshake and exchange encrypted data."""
    port = get_free_port()
    bus = PhantomEventBus(run_id="test-tunnel-roundtrip")

    server = TunnelServer(host="127.0.0.1", port=port, event_bus=bus)
    await server.start()

    client = TunnelClient(server_host="127.0.0.1", server_port=port, event_bus=bus)
    await client.connect()

    assert client.is_connected

    # Send data and verify echo
    payload = b"Testing real ChaCha20-Poly1305 encrypted socket tunnel"
    response = await client.send_data(payload)
    assert response == b"ECHO:" + payload

    # Explicit rekey
    await client.rekey()
    response_post_rekey = await client.send_data(b"Post-rekey payload")
    assert response_post_rekey == b"ECHO:Post-rekey payload"

    await client.close()
    await server.stop()

    # Verify event spine captured the full sequence
    kinds = [e.kind for e in bus.get_all()]
    assert EventKind.HANDSHAKE_MSG in kinds
    assert EventKind.CONN_STATE in kinds
    assert EventKind.PKT_TX in kinds
    assert EventKind.PKT_RX in kinds
    assert EventKind.REKEY in kinds


@pytest.mark.asyncio
async def test_reconnect_forced_drops_resilience() -> None:
    """Reconnect test: 20 forced connection drops in a row, tunnel client recovers every time."""
    port = get_free_port()
    bus = PhantomEventBus(run_id="test-reconnect-loop")

    server = TunnelServer(host="127.0.0.1", port=port, event_bus=bus)
    await server.start()

    client = TunnelClient(
        server_host="127.0.0.1",
        server_port=port,
        event_bus=bus,
        auto_reconnect=True,
        max_reconnect_attempts=5,
    )
    await client.connect()

    for drop_round in range(20):
        # Force terminate underlying writer/socket to simulate sudden drop
        if client._writer:
            client._writer.close()
            with contextlib.suppress(Exception):
                await client._writer.wait_closed()
            client._connected = False

        # Next send must automatically detect failure, reconnect, complete handshake, and succeed
        msg = f"Recovery round {drop_round}".encode()
        resp = await client.send_data(msg)
        assert resp == b"ECHO:" + msg
        assert client.is_connected

    await client.close()
    await server.stop()


@pytest.mark.asyncio
async def test_socks5_front_door_browser_fetch() -> None:
    """Acceptance: local test page loaded through SOCKS5 proxy via encrypted tunnel."""
    # 1. Start a local HTTP test server
    http_port = get_free_port()

    async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        _req = await reader.read(4096)
        body = b"<html><body>PHANTOMNET SECURE PAGE</body></html>"
        resp = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html\r\n"
            + f"Content-Length: {len(body)}\r\n".encode()
            + b"Connection: close\r\n\r\n"
            + body
        )
        writer.write(resp)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    http_server = await asyncio.start_server(handle_http, "127.0.0.1", http_port)

    # 2. Start Tunnel Server & Client
    tunnel_port = get_free_port()
    server = TunnelServer(host="127.0.0.1", port=tunnel_port)
    await server.start()

    client = TunnelClient(server_host="127.0.0.1", server_port=tunnel_port)
    await client.connect()

    # 3. Start SOCKS5 Front Door
    socks_port = get_free_port()
    socks5 = Socks5Server(tunnel_client=client, listen_host="127.0.0.1", listen_port=socks_port)
    await socks5.start()

    # 4. Standard SOCKS5 client interaction (simulating browser or Playwright)
    socks_reader, socks_writer = await asyncio.open_connection("127.0.0.1", socks_port)

    # Handshake: VER 5, 1 Method, No Auth
    socks_writer.write(b"\x05\x01\x00")
    await socks_writer.drain()
    handshake_resp = await socks_reader.readexactly(2)
    assert handshake_resp == b"\x05\x00"

    # Connect to local HTTP test server: VER 5, CMD 1, RSV 0, ATYP 1 (IPv4), 127.0.0.1, http_port
    req = struct.pack(">BBBB4sH", 5, 1, 0, 1, socket.inet_aton("127.0.0.1"), http_port)
    socks_writer.write(req)
    await socks_writer.drain()
    conn_resp = await socks_reader.readexactly(10)
    assert conn_resp[:2] == b"\x05\x00"  # Succeeded

    # Send HTTP GET through SOCKS5
    get_str = f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{http_port}\r\nConnection: close\r\n\r\n"
    socks_writer.write(get_str.encode("utf-8"))
    await socks_writer.drain()

    # Receive HTTP response
    http_res = await socks_reader.read(4096)
    assert b"200 OK" in http_res
    assert b"PHANTOMNET SECURE PAGE" in http_res

    socks_writer.close()
    await socks_writer.wait_closed()

    await socks5.stop()
    await client.close()
    await server.stop()
    http_server.close()
    await http_server.wait_closed()


@pytest.mark.asyncio
async def test_censor_blocks_unshaped_flow() -> None:
    """Acceptance: censor on-path proxy detects unshaped MTU burst and slams the block gate."""
    server_port = get_free_port()
    proxy_port = get_free_port()
    bus = PhantomEventBus(run_id="test-censor-blocking")

    # Start target server
    server = TunnelServer(host="127.0.0.1", port=server_port, event_bus=bus)
    await server.start()

    # Start censor on-path proxy sitting in front of server
    censor = RuleBasedCensor(mtu_cluster_threshold=3, block_threshold=0.80)
    censor_proxy = CensorProxy(
        listen_host="127.0.0.1",
        listen_port=proxy_port,
        target_host="127.0.0.1",
        target_port=server_port,
        censor=censor,
        event_bus=bus,
    )
    await censor_proxy.start()

    # Client connects to censor proxy
    client = TunnelClient(
        server_host="127.0.0.1",
        server_port=proxy_port,
        event_bus=bus,
        auto_reconnect=False,
    )
    await client.connect()

    # Stream unshaped large packets to trigger block
    blocked = False
    for _ in range(12):
        large_unshaped_chunk = b"U" * 1400
        try:
            await client.send_data(large_unshaped_chunk)
        except (ConnectionError, BrokenPipeError, ConnectionResetError):
            blocked = True
            break
        await asyncio.sleep(0.01)

    assert blocked, "Censor should have blocked the unshaped MTU flow!"

    await client.close()
    await censor_proxy.stop()
    await server.stop()

    # Verify CENSOR_ACTION BLOCK and PKT_DROP events were emitted
    events = bus.get_all()
    actions = [e for e in events if e.kind == EventKind.CENSOR_ACTION]
    drops = [e for e in events if e.kind == EventKind.PKT_DROP]
    assert any(a.meta.get("action") == "BLOCK" for a in actions)
    assert len(drops) > 0
