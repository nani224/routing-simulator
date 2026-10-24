"""Real asyncio router node with local UDP socket and link emulator bindings.

Each router instance runs as an independent network entity with its own UDP socket
bound to localhost, communicating via logical LinkEmulators.
Encapsulates plugin execution inside IsolatedProtocolRunner and provides the
strict ProtocolContext sandbox.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import random
import socket
from typing import TYPE_CHECKING, Any

from routelab.core.packet import Packet, PacketType
from routelab.plugins.interface import NeighborInfo, ProtocolContext, RouteEntry, RoutingProtocol
from routelab.plugins.loader import IsolatedProtocolRunner

if TYPE_CHECKING:
    from routelab.core.clock import Clock
    from routelab.core.events import EventStore
    from routelab.core.link import LinkEmulator

logger = logging.getLogger("routelab.node")


class NodeStatus(enum.StrEnum):
    """Operational status of a router node."""

    RUNNING = "running"
    CRASHED = "crashed"
    FAULTY = "faulty"
    STOPPED = "stopped"


class _UDPProtocol(asyncio.DatagramProtocol):
    """Asyncio UDP datagram transport handler."""

    def __init__(self, node: RouterNode) -> None:
        self.node = node

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.node.handle_incoming_raw_datagram(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Node %s UDP error: %s", self.node.node_id, exc)


class RouterNode(ProtocolContext):
    """Network router node executing an isolated routing protocol plugin."""

    def __init__(
        self,
        node_id: str,
        clock: Clock,
        event_store: EventStore | None = None,
        seed: int = 42,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0,
    ) -> None:
        self._node_id = node_id
        self.clock = clock
        self.event_store = event_store
        self.bind_host = bind_host
        self.bind_port = bind_port
        self._rng = random.Random(seed)

        self.status: NodeStatus = NodeStatus.STOPPED
        self.links: dict[str, LinkEmulator] = {}  # neighbor_id -> LinkEmulator
        self._seq: int = 0
        self._transport: asyncio.DatagramTransport | None = None
        self._assigned_port: int = bind_port

        # Active protocol runner
        self._protocol: RoutingProtocol | None = None
        self._runner: IsolatedProtocolRunner | None = None

        # Timers: timer_id -> cancellation handle or token
        self._active_timers: dict[str, Any] = {}

        # Node metrics
        self.packets_sent: int = 0
        self.packets_received: int = 0
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self.flaps_count: int = 0
        self._last_table_hash: int = 0

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def port(self) -> int:
        return self._assigned_port

    def attach_link(self, nbr: str, link: LinkEmulator) -> None:
        """Attach a link emulator connecting this node to neighbor."""
        self.links[nbr] = link

    def set_protocol(self, protocol: RoutingProtocol) -> None:
        """Bind a routing protocol instance to this router node."""
        self._protocol = protocol
        self._runner = IsolatedProtocolRunner(
            node_id=self.node_id,
            protocol=protocol,
            context=self,
        )

    async def start(self) -> None:
        """Boot router node, bind UDP socket, and launch protocol."""
        if self.status == NodeStatus.RUNNING:
            return

        # Bind UDP socket
        loop = asyncio.get_running_loop()
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: _UDPProtocol(self),
                local_addr=(self.bind_host, self.bind_port),
                reuse_port=False if socket.has_ipv6 else False,
            )
            self._transport = transport
            sockname = transport.get_extra_info("sockname")
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                self._assigned_port = sockname[1]
        except Exception as exc:
            logger.error("Failed to bind UDP socket for %s: %s", self.node_id, exc)
            self._assigned_port = 20000 + abs(hash(self.node_id)) % 20000

        self.status = NodeStatus.RUNNING

        # Start protocol
        if self._runner is not None:
            self._runner.on_start()
            self._check_table_flaps()

    async def stop(self) -> None:
        """Halt router node, cancel timers, and close socket."""
        self.status = NodeStatus.STOPPED
        self._cancel_all_timers()
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def crash(self) -> None:
        """Simulate abrupt node crash / power failure."""
        self.status = NodeStatus.CRASHED
        self._cancel_all_timers()
        logger.info("Node %s CRASHED", self.node_id)

    def recover(self) -> None:
        """Simulate router recovery from crash."""
        if self.status == NodeStatus.CRASHED:
            self.status = NodeStatus.RUNNING
            logger.info("Node %s RECOVERED", self.node_id)
            if self._runner is not None:
                self._runner.on_start()
                self._check_table_flaps()

    # ProtocolContext Implementation
    def send(self, nbr: str, payload: dict[str, Any]) -> None:
        if self.status != NodeStatus.RUNNING:
            return
        link = self.links.get(nbr)
        if link is None:
            self.log(f"Cannot send to non-neighbor {nbr}", level="WARNING")
            return

        self._seq += 1
        pkt = Packet(
            src=self.node_id,
            dst=nbr,
            proto=self._protocol.name if self._protocol else "raw",
            seq=self._seq,
            ttl=32,
            timestamp=self.clock.now(),
            payload=payload,
            packet_type=PacketType.CONTROL,
        )

        encoded = pkt.to_bytes()
        self.packets_sent += 1
        self.bytes_sent += len(encoded)

        # Transmit via LinkEmulator
        link.transmit(pkt, delivery_callback=self._deliver_to_nbr_callback(nbr))

    def broadcast(self, payload: dict[str, Any]) -> None:
        if self.status != NodeStatus.RUNNING:
            return
        for nbr in list(self.links.keys()):
            self.send(nbr, payload)

    def _deliver_to_nbr_callback(self, nbr: str) -> Any:
        # Return callback to deliver packet directly to neighbor's receiver
        return lambda pkt: self._nbr_receive_packet(nbr, pkt)

    def _nbr_receive_packet(self, nbr: str, pkt: Packet) -> None:
        # Link delivered packet to neighbor. This method is called by link emulator on arrival.
        # Neighbor node receives packet via its receive_packet handler.
        nbr_link = self.links.get(nbr)
        if nbr_link is None or not nbr_link.is_up:
            return
        # Node manager or link will route to neighbor node instance
        # Handler invoked via registered on_packet_delivered
        if hasattr(self, "_network_router_lookup"):
            target_node: RouterNode | None = self._network_router_lookup(nbr)
            if target_node is not None:
                target_node.receive_packet(pkt)

    def receive_packet(self, pkt: Packet) -> None:
        """Handle incoming packet delivered via LinkEmulator."""
        if self.status != NodeStatus.RUNNING:
            return

        self.packets_received += 1
        self.bytes_received += pkt.byte_size

        if self._runner is not None:
            self._runner.on_message(pkt.src, pkt.payload)
            if self._runner.is_faulty:
                self.status = NodeStatus.FAULTY
            self._check_table_flaps()

    def handle_incoming_raw_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming raw datagram on physical UDP socket."""
        try:
            pkt = Packet.from_bytes(data)
            self.receive_packet(pkt)
        except Exception as exc:
            logger.debug("Node %s received malformed datagram from %s: %s", self.node_id, addr, exc)

    def set_timer(self, timer_id: str, delay_ms: float) -> None:
        if self.status != NodeStatus.RUNNING:
            return
        self.cancel_timer(timer_id)
        delay_s = max(0.001, delay_ms / 1000.0)

        if self.clock.is_virtual:
            from routelab.core.clock import VirtualClock

            assert isinstance(self.clock, VirtualClock)
            seq = self.clock.schedule(delay_s, lambda: self._on_timer_fired(timer_id))
            self._active_timers[timer_id] = seq
        else:
            loop = asyncio.get_event_loop()
            real_delay = delay_s / max(0.01, self.clock.speed)
            handle = loop.call_later(real_delay, self._on_timer_fired, timer_id)
            self._active_timers[timer_id] = handle

    def cancel_timer(self, timer_id: str) -> None:
        handle = self._active_timers.pop(timer_id, None)
        if handle is None:
            return
        if hasattr(handle, "cancel"):
            handle.cancel()

    def _cancel_all_timers(self) -> None:
        for timer_id in list(self._active_timers.keys()):
            self.cancel_timer(timer_id)

    def _on_timer_fired(self, timer_id: str) -> None:
        self._active_timers.pop(timer_id, None)
        if self.status != NodeStatus.RUNNING:
            return
        if self._runner is not None:
            self._runner.on_timer(timer_id)
            self._check_table_flaps()
            if self._runner.is_faulty:
                self.status = NodeStatus.FAULTY

    def notify_link_change(self, nbr: str, cost: float, up: bool) -> None:
        """Notify active protocol of link status or cost mutation."""
        if self.status != NodeStatus.RUNNING:
            return
        if self._runner is not None:
            self._runner.on_link_change(nbr, cost, up)
            self._check_table_flaps()
            if self._runner.is_faulty:
                self.status = NodeStatus.FAULTY

    def neighbors(self) -> list[NeighborInfo]:
        infos: list[NeighborInfo] = []
        for nbr, link in self.links.items():
            infos.append(
                NeighborInfo(
                    node_id=nbr,
                    cost=link.cost,
                    is_up=link.is_up,
                    latency_ms=link.latency_ms,
                )
            )
        return infos

    def now(self) -> float:
        return self.clock.now()

    def rng(self) -> random.Random:
        return self._rng

    def log(self, message: str, level: str = "INFO") -> None:
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            "[%s] %s",
            self.node_id,
            message,
        )

    def get_table(self) -> list[RouteEntry]:
        if self._runner is None:
            return []
        return self._runner.get_table()

    def describe_state(self) -> dict[str, Any]:
        state = self._runner.describe_state() if self._runner else {}
        state["status"] = self.status.value
        state["port"] = self._assigned_port
        state["packets_sent"] = self.packets_sent
        state["packets_received"] = self.packets_received
        state["bytes_sent"] = self.bytes_sent
        state["bytes_received"] = self.bytes_received
        state["flaps_count"] = self.flaps_count
        return state

    def _check_table_flaps(self) -> None:
        """Detect route changes (flaps) by hashing destination/next-hop pairs."""
        if self._runner is None:
            return
        table = self._runner.get_table()
        table_sig = hash(tuple((r.destination, r.next_hop, r.cost) for r in table))
        if self._last_table_hash != 0 and table_sig != self._last_table_hash:
            self.flaps_count += 1
        self._last_table_hash = table_sig
