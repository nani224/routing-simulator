"""High-performance logical link emulator with heap-based delayed delivery.

Provides configurable latency, jitter, loss, bandwidth limits, and routing cost.
Uses a centralized priority queue to prevent per-packet task explosions.
Supports both real-time asyncio dispatch and virtual-clock deterministic replay.
"""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from routelab.core.clock import Clock
    from routelab.core.packet import Packet


@dataclass(order=True)
class _InFlightPacket:
    delivery_time: float
    seq: int
    packet: Packet = field(compare=False)
    delivery_callback: Callable[[Packet], Any] = field(compare=False)


@dataclass
class LinkStats:
    """Cumulative metrics tracked per link."""

    packets_sent: int = 0
    packets_delivered: int = 0
    packets_dropped_loss: int = 0
    packets_dropped_down: int = 0
    bytes_sent: int = 0
    bytes_delivered: int = 0
    bytes_dropped: int = 0


class LinkEmulator:
    """Logical simplex or duplex link with emulation properties."""

    def __init__(
        self,
        node_a: str,
        node_b: str,
        clock: Clock,
        cost: float = 1.0,
        latency_ms: float = 10.0,
        jitter_ms: float = 0.0,
        loss_rate: float = 0.0,
        bandwidth_bps: float = 0.0,  # 0.0 means unconstrained
        rng: random.Random | None = None,
    ) -> None:
        self.node_a = node_a
        self.node_b = node_b
        self.clock = clock
        self.cost = cost
        self.latency_ms = latency_ms
        self.jitter_ms = jitter_ms
        self.loss_rate = loss_rate
        self.bandwidth_bps = bandwidth_bps
        self._rng = rng or random.Random(42)

        self.is_up: bool = True
        self.stats: LinkStats = LinkStats()

        # In-flight queue for this link
        self._queue: list[_InFlightPacket] = []
        self._packet_counter: int = 0
        self._last_tx_finish_time: float = 0.0
        self._worker_task: asyncio.Task[None] | None = None
        self._wake_event: asyncio.Event = asyncio.Event()
        self._running: bool = False

    @property
    def link_id(self) -> str:
        return f"{self.node_a}<->{self.node_b}"

    def start(self) -> None:
        """Start link delivery worker if in real-time mode."""
        self._running = True
        if not self.clock.is_virtual and self._worker_task is None:
            self._worker_task = asyncio.create_task(self._realtime_worker())

    async def stop(self) -> None:
        """Stop worker task and drain or drop in-flight queue."""
        self._running = False
        self._wake_event.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    def transmit(
        self,
        packet: Packet,
        delivery_callback: Callable[[Packet], Any],
    ) -> bool:
        """Enqueue packet for transmission across this link.

        Returns:
            True if queued, False if dropped immediately due to link failure or loss.
        """
        self.stats.packets_sent += 1
        pkt_bytes = packet.byte_size if packet.byte_size > 0 else len(packet.to_bytes())
        self.stats.bytes_sent += pkt_bytes

        if not self.is_up:
            self.stats.packets_dropped_down += 1
            self.stats.bytes_dropped += pkt_bytes
            return False

        if self.loss_rate > 0.0 and self._rng.random() < self.loss_rate:
            self.stats.packets_dropped_loss += 1
            self.stats.bytes_dropped += pkt_bytes
            return False

        # Calculate propagation and queued serialization delay
        now = self.clock.now()
        base_delay_s = self.latency_ms / 1000.0
        jitter_s = (
            self._rng.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
            if self.jitter_ms > 0
            else 0.0
        )
        propagation_delay = max(0.001, base_delay_s + jitter_s)

        tx_delay = (pkt_bytes * 8.0) / self.bandwidth_bps if self.bandwidth_bps > 0 else 0.0
        tx_start = max(now, self._last_tx_finish_time)
        tx_finish = tx_start + tx_delay
        self._last_tx_finish_time = tx_finish

        delivery_time = tx_finish + propagation_delay
        total_delay = max(0.001, delivery_time - now)
        self._packet_counter += 1

        in_flight = _InFlightPacket(
            delivery_time=delivery_time,
            seq=self._packet_counter,
            packet=packet,
            delivery_callback=delivery_callback,
        )

        if self.clock.is_virtual:
            from routelab.core.clock import VirtualClock

            assert isinstance(self.clock, VirtualClock)
            self.clock.schedule(
                total_delay,
                lambda: self._deliver_packet(in_flight),
            )
        else:
            heapq.heappush(self._queue, in_flight)
            self._wake_event.set()

        return True

    def _deliver_packet(self, item: _InFlightPacket) -> None:
        """Deliver packet if link is still up at delivery time."""
        if not self.is_up:
            self.stats.packets_dropped_down += 1
            self.stats.bytes_dropped += item.packet.byte_size
            return

        self.stats.packets_delivered += 1
        self.stats.bytes_delivered += item.packet.byte_size
        cb = item.delivery_callback
        res = cb(item.packet)
        if asyncio.iscoroutine(res):
            asyncio.create_task(res)

    async def _realtime_worker(self) -> None:
        """Background worker servicing in-flight packets based on scheduled delivery times."""
        while self._running:
            while self._queue:
                now = self.clock.now()
                earliest = self._queue[0]
                if earliest.delivery_time <= now:
                    item = heapq.heappop(self._queue)
                    self._deliver_packet(item)
                else:
                    delay_needed = earliest.delivery_time - now
                    try:
                        await asyncio.wait_for(
                            self._wake_event.wait(),
                            timeout=delay_needed / max(0.01, self.clock.speed),
                        )
                        self._wake_event.clear()
                    except TimeoutError:
                        pass
                    break

            if not self._queue:
                await self._wake_event.wait()
                self._wake_event.clear()

    def in_flight_count(self) -> int:
        """Return number of packets currently in transit."""
        return len(self._queue)
