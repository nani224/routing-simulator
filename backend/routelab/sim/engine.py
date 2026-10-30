"""Simulation engine orchestrating nodes, link emulators, clocks, and events.

Provides:
1. Topology instantiator wiring nodes and link emulators.
2. Protocol lifecycle orchestration.
3. Live and scripted failure/mutation injection (link down/up, node crash/recover, cost change).
4. Convergence detector tracking quiescence windows and in-flight control packets.
5. High-resolution event delta streaming for WebSockets.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from routelab.core.clock import Clock, RealtimeClock
from routelab.core.events import EventStore, EventType
from routelab.core.link import LinkEmulator
from routelab.core.node import RouterNode
from routelab.plugins.interface import RouteEntry, RoutingProtocol
from routelab.topology.model import Topology

logger = logging.getLogger("routelab.sim")


@dataclass
class ConvergenceRecord:
    """Detailed record of network convergence state."""

    is_converged: bool = False
    convergence_time_s: float = 0.0
    quiescence_window_s: float = 0.5
    total_control_messages: int = 0
    total_control_bytes: int = 0
    total_flaps: int = 0


@dataclass
class ScheduledSimulationEvent:
    """A scheduled failure, recovery, or metric injection event."""

    timestamp: float
    action: str  # 'link_down', 'link_up', 'cost_change', 'node_crash', 'node_recover', 'attack'
    params: dict[str, Any]
    executed: bool = False


class SimulationEngine:
    """Central simulation controller managing topology instances and execution cycles."""

    def __init__(
        self,
        topology: Topology,
        protocol_factory: Callable[[], RoutingProtocol] | Callable[[str], RoutingProtocol],
        clock: Clock | None = None,
        event_store: EventStore | None = None,
        quiescence_window_s: float = 0.5,
        seed: int = 42,
    ) -> None:
        self.topology = topology
        self.protocol_factory = protocol_factory
        self.clock: Clock = clock or RealtimeClock(initial_speed=1.0)
        self.event_store: EventStore = event_store if event_store is not None else EventStore()
        self.quiescence_window_s = quiescence_window_s
        self.seed = seed

        self.nodes: dict[str, RouterNode] = {}
        self.links: dict[str, LinkEmulator] = {}  # "A<->B" -> LinkEmulator
        self._scheduled_events: list[ScheduledSimulationEvent] = []

        # Convergence state
        self._last_mutation_time: float = 0.0
        self._is_converged: bool = False
        self._convergence_start_time: float = 0.0
        self.convergence_record: ConvergenceRecord = ConvergenceRecord(
            quiescence_window_s=quiescence_window_s
        )

        # Delta listeners for WebSocket broadcasting
        self._delta_listeners: list[Callable[[dict[str, Any]], Any]] = []
        self._is_running: bool = False
        self._monitor_task: asyncio.Task[None] | None = None

        self._build_network()

    def _build_network(self) -> None:
        """Instantiate RouterNodes and LinkEmulators from the active Topology."""
        # Detect whether protocol_factory accepts a node_id argument
        takes_node_id = False
        try:
            sig = inspect.signature(self.protocol_factory)
            params = list(sig.parameters.values())
            if len(params) == 1 and params[0].name != "config":
                takes_node_id = True
        except Exception:
            pass

        # 1. Instantiate nodes
        for node_id, _t_node in self.topology.nodes.items():
            node = RouterNode(
                node_id=node_id,
                clock=self.clock,
                event_store=self.event_store,
                seed=abs(hash(f"{self.seed}:{node_id}")) % 100000,
            )
            # Router lookup resolver
            node._network_router_lookup = lambda target_id: self.nodes.get(target_id)  # type: ignore[attr-defined]
            # Attach protocol instance
            if takes_node_id:
                factory_with_id = cast(Callable[[str], RoutingProtocol], self.protocol_factory)
                protocol_inst = factory_with_id(node_id)
            else:
                factory_no_args = cast(Callable[[], RoutingProtocol], self.protocol_factory)
                protocol_inst = factory_no_args()
            node.set_protocol(protocol_inst)
            node.on_table_changed = self._on_node_table_changed
            node.on_packet_sent = self._on_node_packet_sent
            node.on_packet_delivered = self._on_node_packet_delivered
            self.nodes[node_id] = node

        # 2. Instantiate and wire link emulators
        for t_link in self.topology.links:
            u, v = t_link.source, t_link.target
            link = LinkEmulator(
                node_a=u,
                node_b=v,
                clock=self.clock,
                cost=t_link.cost,
                latency_ms=t_link.latency_ms,
                jitter_ms=t_link.jitter_ms,
                loss_rate=t_link.loss_rate,
                bandwidth_bps=t_link.bandwidth_bps,
            )
            key = f"{min(u, v)}<->{max(u, v)}"
            self.links[key] = link

            # Attach to both endpoints
            if u in self.nodes:
                self.nodes[u].attach_link(v, link)
            if v in self.nodes:
                self.nodes[v].attach_link(u, link)

    async def start(self) -> None:
        """Start all nodes, link emulators, and monitoring tasks."""
        if self._is_running:
            return
        self._is_running = True
        self._convergence_start_time = self.clock.now()
        self._last_mutation_time = self.clock.now()

        for link in self.links.values():
            link.start()

        for node in self.nodes.values():
            await node.start()

        if not self.clock.is_virtual:
            self._monitor_task = asyncio.create_task(self._realtime_monitor_loop())

    async def stop(self) -> None:
        """Halt all active entities."""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None

        for node in self.nodes.values():
            await node.stop()

        for link in self.links.values():
            await link.stop()

    def add_event(self, timestamp: float, action: str, params: dict[str, Any]) -> None:
        """Enqueue a scheduled event (e.g. link failure or cost change)."""
        ev = ScheduledSimulationEvent(timestamp=timestamp, action=action, params=params)
        self._scheduled_events.append(ev)
        self._scheduled_events.sort(key=lambda x: x.timestamp)
        if self.clock.is_virtual:
            delay = max(0.0, timestamp - self.clock.now())
            from routelab.core.clock import VirtualClock

            assert isinstance(self.clock, VirtualClock)
            self.clock.schedule(delay, lambda: self._trigger_event(ev))

    def _on_node_table_changed(self) -> None:
        """Invoked when any node's routing table mutates."""
        self._last_mutation_time = self.clock.now()
        self._is_converged = False

    def _on_node_packet_sent(self, src: str, dst: str, proto: str, seq: int) -> None:
        self._broadcast_delta(
            {
                "type": "packet",
                "event": "PACKET_SENT",
                "src": src,
                "dst": dst,
                "proto": proto,
                "seq": seq,
            }
        )

    def _on_node_packet_delivered(self, src: str, dst: str, proto: str, seq: int) -> None:
        self._broadcast_delta(
            {
                "type": "packet",
                "event": "PACKET_DELIVERED",
                "src": src,
                "dst": dst,
                "proto": proto,
                "seq": seq,
            }
        )

    def _trigger_event(self, ev: ScheduledSimulationEvent) -> None:
        if not ev.executed:
            ev.executed = True
            self._execute_scheduled_event(ev)

    def inject_link_state(self, u: str, v: str, up: bool) -> None:
        """Dynamically toggle link state (fail or recover)."""
        key = f"{min(u, v)}<->{max(u, v)}"
        link = self.links.get(key)
        if link is None:
            logger.warning("Link %s not found", key)
            return

        link.is_up = up
        now = self.clock.now()
        self._last_mutation_time = now
        self._convergence_start_time = now
        self._is_converged = False

        if u in self.nodes:
            self.nodes[u].notify_link_change(v, link.cost, up)
        if v in self.nodes:
            self.nodes[v].notify_link_change(u, link.cost, up)

        self.event_store.append(
            timestamp=now,
            event_type=EventType.LINK_STATE,
            source=key,
            data={"node_a": u, "node_b": v, "is_up": up, "cost": link.cost},
        )
        self._broadcast_delta({"type": "link_state", "link_id": key, "is_up": up})

    def inject_link_cost(self, u: str, v: str, cost: float) -> None:
        """Dynamically update link routing metric cost."""
        key = f"{min(u, v)}<->{max(u, v)}"
        link = self.links.get(key)
        if link is None:
            return

        link.cost = cost
        now = self.clock.now()
        self._last_mutation_time = now
        self._convergence_start_time = now
        self._is_converged = False

        if u in self.nodes:
            self.nodes[u].notify_link_change(v, cost, link.is_up)
        if v in self.nodes:
            self.nodes[v].notify_link_change(u, cost, link.is_up)

        self.event_store.append(
            timestamp=now,
            event_type=EventType.LINK_STATE,
            source=key,
            data={"node_a": u, "node_b": v, "is_up": link.is_up, "cost": cost},
        )
        self._broadcast_delta({"type": "link_cost", "link_id": key, "cost": cost})

    def inject_node_crash(self, node_id: str) -> None:
        """Simulate node crash failure."""
        node = self.nodes.get(node_id)
        if node is None:
            return
        node.crash()
        now = self.clock.now()
        self._last_mutation_time = now
        self._convergence_start_time = now
        self._is_converged = False

        # Notify neighbors of link down to this node
        for nbr in list(node.links.keys()):
            if nbr in self.nodes:
                self.nodes[nbr].notify_link_change(node_id, 999999, False)

        self.event_store.append(
            timestamp=now,
            event_type=EventType.NODE_STATE,
            source=node_id,
            data={"status": "crashed"},
        )
        self._broadcast_delta({"type": "node_state", "node_id": node_id, "status": "crashed"})

    def inject_node_recover(self, node_id: str) -> None:
        """Simulate node recovery from crash."""
        node = self.nodes.get(node_id)
        if node is None:
            return
        node.recover()
        now = self.clock.now()
        self._last_mutation_time = now
        self._convergence_start_time = now
        self._is_converged = False

        from routelab.core.node import NodeStatus

        for nbr, link in node.links.items():
            nbr_node = self.nodes.get(nbr)
            # Only restore link if the link itself is configured UP and neighbor router is alive
            if link.is_up and nbr_node is not None and nbr_node.status != NodeStatus.CRASHED:
                nbr_node.notify_link_change(node_id, link.cost, True)
                node.notify_link_change(nbr, link.cost, True)

        self.event_store.append(
            timestamp=now,
            event_type=EventType.NODE_STATE,
            source=node_id,
            data={"status": "running"},
        )
        self._broadcast_delta({"type": "node_state", "node_id": node_id, "status": "running"})

    def check_convergence(self) -> bool:
        """Assess if the network has attained convergence.

        Criteria:
        1. All link in-flight queues are completely empty.
        2. No routing table mutations have occurred during the quiescence window.
        3. No pending scheduled events remain.
        """
        # Check if there are unexecuted scheduled events pending
        if any(not ev.executed for ev in self._scheduled_events):
            return False

        now = self.clock.now()
        # Check in-flight packets
        total_in_flight = sum(link.in_flight_count() for link in self.links.values())
        if total_in_flight > 0:
            self._last_mutation_time = now
            return False

        # In virtual clock, verify no scheduled events remain in queue within quiescence window
        if self.clock.is_virtual:
            from routelab.core.clock import VirtualClock

            if isinstance(self.clock, VirtualClock) and self.clock._event_queue:
                next_event_time = self.clock._event_queue[0].timestamp
                if next_event_time <= now + (self.quiescence_window_s * 0.5):
                    return False

        # Check quiescence duration
        quiescence_duration = now - self._last_mutation_time
        if quiescence_duration >= self.quiescence_window_s:
            if not self._is_converged:
                self._is_converged = True
                conv_duration = max(0.0, now - self._convergence_start_time)
                self.convergence_record = ConvergenceRecord(
                    is_converged=True,
                    convergence_time_s=conv_duration,
                    quiescence_window_s=self.quiescence_window_s,
                    total_control_messages=sum(n.packets_sent for n in self.nodes.values()),
                    total_control_bytes=sum(n.bytes_sent for n in self.nodes.values()),
                    total_flaps=sum(n.flaps_count for n in self.nodes.values()),
                )
                self.event_store.append(
                    timestamp=now,
                    event_type=EventType.CONVERGENCE,
                    source="engine",
                    data={
                        "duration_s": conv_duration,
                        "messages": self.convergence_record.total_control_messages,
                        "bytes": self.convergence_record.total_control_bytes,
                        "flaps": self.convergence_record.total_flaps,
                    },
                )
                self._broadcast_delta(
                    {
                        "type": "convergence",
                        "duration_s": conv_duration,
                        "record": {
                            "messages": self.convergence_record.total_control_messages,
                            "bytes": self.convergence_record.total_control_bytes,
                            "flaps": self.convergence_record.total_flaps,
                        },
                    }
                )
            return True

        return False

    def baseline_routing_tables(self) -> None:
        """Baseline routing tables on all nodes to prevent initial convergence counting as flaps."""
        for node in self.nodes.values():
            node.baseline_routing_table()

    async def _realtime_monitor_loop(self) -> None:
        """Periodic loop processing scheduled events, convergence checks, and frame deltas."""
        while self._is_running:
            is_paused = getattr(self.clock, "is_paused", False)
            now = self.clock.now()

            # Process scheduled events only when not paused
            if not is_paused:
                for ev in self._scheduled_events:
                    if not ev.executed and ev.timestamp <= now:
                        ev.executed = True
                        self._execute_scheduled_event(ev)

                # Check convergence
                self.check_convergence()

            # Batch frame delta for WebSocket live telemetry
            if self._delta_listeners:
                nodes_snapshot = {
                    nid: {
                        "packets_sent": n.packets_sent,
                        "packets_received": n.packets_received,
                        "flaps_count": n.flaps_count,
                        "status": n.status.value,
                        "routes": [
                            {"destination": r.destination, "next_hop": r.next_hop, "cost": r.cost}
                            for r in n.get_table()
                        ],
                    }
                    for nid, n in self.nodes.items()
                }
                self._broadcast_delta(
                    {
                        "type": "frame",
                        "time": now,
                        "paused": is_paused,
                        "converged": self._is_converged,
                        "nodes": nodes_snapshot,
                    }
                )

            if is_paused:
                await asyncio.sleep(0.1)
            else:
                await self.clock.sleep(0.05)  # 20 FPS

    def _execute_scheduled_event(self, ev: ScheduledSimulationEvent) -> None:
        if ev.action == "link_down":
            self.inject_link_state(ev.params["u"], ev.params["v"], up=False)
        elif ev.action == "link_up":
            self.inject_link_state(ev.params["u"], ev.params["v"], up=True)
        elif ev.action in ("cost_change", "link_cost"):
            self.inject_link_cost(ev.params["u"], ev.params["v"], ev.params["cost"])
        elif ev.action == "node_crash":
            self.inject_node_crash(ev.params["node_id"])
        elif ev.action == "node_recover":
            self.inject_node_recover(ev.params["node_id"])

    def add_delta_listener(self, listener: Callable[[dict[str, Any]], Any]) -> None:
        self._delta_listeners.append(listener)

    def _broadcast_delta(self, delta: dict[str, Any]) -> None:
        for listener in self._delta_listeners:
            try:
                res = listener(delta)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as exc:
                logger.error("Error invoking delta listener: %s", exc)

    def subscribe_deltas(self, listener: Callable[[dict[str, Any]], Any]) -> None:
        """Register a callback or coroutine to receive real-time delta events."""
        self._delta_listeners.append(listener)

    def get_all_routes(self) -> dict[str, list[RouteEntry]]:
        """Return routing tables for all running nodes."""
        return {nid: node.get_table() for nid, node in self.nodes.items()}

    def get_full_state(self) -> dict[str, Any]:
        """Snapshot current state for UI inspectors or initial WebSocket connection."""
        return {
            "time": self.clock.now(),
            "is_converged": self._is_converged,
            "convergence": {
                "time_s": self.convergence_record.convergence_time_s,
                "messages": sum(n.packets_sent for n in self.nodes.values()),
                "bytes": sum(n.bytes_sent for n in self.nodes.values()),
                "flaps": sum(n.flaps_count for n in self.nodes.values()),
            },
            "nodes": {nid: n.describe_state() for nid, n in self.nodes.items()},
            "links": {
                lid: {
                    "is_up": lnk.is_up,
                    "cost": lnk.cost,
                    "in_flight": lnk.in_flight_count(),
                    "stats": {
                        "sent": lnk.stats.packets_sent,
                        "delivered": lnk.stats.packets_delivered,
                        "dropped": (
                            lnk.stats.packets_dropped_down + lnk.stats.packets_dropped_loss
                        ),
                    },
                }
                for lid, lnk in self.links.items()
            },
            "routes": {nid: [r.to_dict() for r in n.get_table()] for nid, n in self.nodes.items()},
        }
