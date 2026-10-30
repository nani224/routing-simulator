"""Global simulation session state and WebSocket broadcasting manager.

Maintains the active simulation instance, bridges delta events to WebSocket clients,
and provides unified state snapshots for the UI.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import json
import logging
from collections.abc import Callable
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

from routelab.attacks.mitigation import SecureDistanceVectorProtocol
from routelab.attacks.poisoning import PoisoningAttackProtocol
from routelab.core.clock import Clock, RealtimeClock, VirtualClock
from routelab.core.events import EventStore
from routelab.metrics.collector import MetricsCollector
from routelab.plugins.interface import RoutingProtocol
from routelab.protocols.bgp_lite import BGPLiteProtocol
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.protocols.flooding import FloodingProtocol
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import (
    preset_6_node,
    preset_8_node,
    preset_10_node,
    preset_bgp_tier1,
    preset_count_to_infinity,
)
from routelab.topology.model import Topology, TopologyLink, TopologyNode

logger = logging.getLogger("routelab.api.state")


class SimulationSessionManager:
    """Singleton session coordinator managing active SimulationEngine and WebSocket broadcast."""

    PROTOCOL_MAP: dict[str, Callable[[dict[str, Any]], RoutingProtocol]] = {
        "distance_vector": lambda cfg: DistanceVectorProtocol(cfg),
        "link_state": lambda cfg: LinkStateProtocol(cfg),
        "bgp_lite": lambda cfg: BGPLiteProtocol(cfg),
        "flooding": lambda cfg: FloodingProtocol(cfg),
        "poisoning_attack": lambda cfg: PoisoningAttackProtocol(cfg),
        "secure_dv": lambda cfg: SecureDistanceVectorProtocol(cfg),
    }

    PRESET_MAP: dict[str, Callable[[], Topology]] = {
        "Course-6-Node-Benchmark": preset_6_node,
        "Course-8-Node-Benchmark": preset_8_node,
        "Course-10-Node-Benchmark": preset_10_node,
        "Count-to-Infinity-Linear": preset_count_to_infinity,
        "BGP-Multi-AS-Interdomain": preset_bgp_tier1,
    }

    def __init__(self) -> None:
        self.engine: SimulationEngine | None = None
        self.clock: Clock | None = None
        self.topology: Topology | None = None
        self.event_store: EventStore | None = None
        self.active_protocol_name: str = "distance_vector"

        # WebSocket active connections
        self.connected_clients: set[WebSocket] = set()
        self._delta_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=10_000)
        self._broadcast_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Start the background WebSocket delta broadcaster loop."""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def shutdown(self) -> None:
        """Terminate active simulation session and close WebSocket broadcast."""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            self._broadcast_task = None
        if self.engine:
            await self.engine.stop()
            self.engine = None

    async def register_client(self, websocket: WebSocket) -> None:
        """Register newly connected WebSocket client and transmit initial state snapshot."""
        await websocket.accept()
        self.connected_clients.add(websocket)
        logger.info(
            "WebSocket client connected. Total clients: %s",
            len(self.connected_clients),
        )

        # Transmit initial current state
        state = self.get_state()
        await websocket.send_json({"type": "init", "state": state})

    def unregister_client(self, websocket: WebSocket) -> None:
        """Remove disconnected WebSocket client."""
        self.connected_clients.discard(websocket)
        logger.info(
            "WebSocket client disconnected. Total clients: %s",
            len(self.connected_clients),
        )

    def _enqueue_delta(self, delta: dict[str, Any]) -> None:
        """Queue engine delta callback into async broadcast queue."""
        with contextlib.suppress(asyncio.QueueFull):
            self._delta_queue.put_nowait(delta)

    async def _broadcast_loop(self) -> None:
        """Batches deltas at up to 60 FPS (~16ms) and sends them to all connected clients."""
        while True:
            try:
                # Wait for at least one delta
                first_delta = await self._delta_queue.get()
                batch: list[dict[str, Any]] = [first_delta]

                # Drain queued deltas within a 16ms window (60 FPS throttle)
                await asyncio.sleep(0.016)
                while not self._delta_queue.empty() and len(batch) < 200:
                    try:
                        batch.append(self._delta_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                if not self.connected_clients:
                    continue

                payload = json.dumps({"type": "delta_batch", "deltas": batch})
                dead_clients: list[WebSocket] = []

                for ws in list(self.connected_clients):
                    if ws.client_state == WebSocketState.CONNECTED:
                        try:
                            await ws.send_text(payload)
                        except Exception:
                            dead_clients.append(ws)
                    else:
                        dead_clients.append(ws)

                for dead in dead_clients:
                    self.connected_clients.discard(dead)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Error in broadcast loop: %s", exc)
                await asyncio.sleep(0.05)

    async def start_session(
        self,
        topology_name: str = "Course-6-Node-Benchmark",
        topology_data: dict[str, Any] | None = None,
        protocol_name: str = "distance_vector",
        protocol_config: dict[str, Any] | None = None,
        node_protocols: dict[str, str] | None = None,
        quiescence_window_s: float = 0.3,
        clock_mode: str = "realtime",
        clock_speed: float = 1.0,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Initialize and start a fresh interactive simulation engine."""
        async with self._lock:
            if self.engine:
                await self.engine.stop()
                self.engine = None

            # 1. Resolve topology
            if topology_data:
                topo = Topology(name=topology_name or "Custom-Topology")
                for n_dict in topology_data.get("nodes", []):
                    topo.add_node(TopologyNode.from_dict(n_dict))
                for l_dict in topology_data.get("links", []):
                    topo.add_link(TopologyLink.from_dict(l_dict))
                self.topology = topo
            elif topology_name in self.PRESET_MAP:
                self.topology = self.PRESET_MAP[topology_name]()
            else:
                self.topology = preset_6_node()

            # 2. Clock setup
            if clock_mode == "realtime":
                self.clock = RealtimeClock(initial_speed=clock_speed)
            else:
                self.clock = VirtualClock()

            self.event_store = EventStore()
            self.active_protocol_name = protocol_name
            cfg = protocol_config or {}
            node_map = node_protocols or {}

            # 3. Protocol factory
            def make_protocol(node_id: str) -> RoutingProtocol:
                proto_key = node_map.get(node_id, protocol_name)
                factory: Callable[[dict[str, Any]], RoutingProtocol] = self.PROTOCOL_MAP.get(
                    proto_key
                ) or (lambda c: DistanceVectorProtocol(c))
                return factory(cfg)

            # 4. Engine instantiation
            self.engine = SimulationEngine(
                topology=self.topology,
                protocol_factory=make_protocol,
                clock=self.clock,
                event_store=self.event_store,
                quiescence_window_s=quiescence_window_s,
                seed=seed,
            )

            # 5. Subscribe delta broadcaster
            self.engine.subscribe_deltas(self._enqueue_delta)

            # 6. Start simulation
            await self.engine.start()

            return {
                "status": "started",
                "topology": self.topology.name,
                "protocol": self.active_protocol_name,
                "node_count": len(self.engine.nodes),
                "link_count": len(self.engine.links),
                "clock_mode": clock_mode,
            }

    async def step(self, duration_s: float = 0.1) -> dict[str, Any]:
        """Advance virtual simulation clock forward by a discrete duration step."""
        if not self.engine or not self.clock:
            raise RuntimeError("Simulation engine is not initialized")

        if not self.clock.is_virtual:
            raise ValueError("Step debugging is only permitted in virtual clock mode")

        assert isinstance(self.clock, VirtualClock)
        target_time = self.clock.now() + duration_s
        await self.clock.run_until(target_time)
        converged = self.engine.check_convergence()

        return {
            "current_time": self.clock.now(),
            "converged": converged,
            "in_flight_packets": sum(lnk.in_flight_count() for lnk in self.engine.links.values()),
        }

    async def inject_event(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Dynamically inject network event into active simulation."""
        if not self.engine:
            raise RuntimeError("Simulation engine is not initialized")

        if action == "link_down":
            self.engine.inject_link_state(str(params["u"]), str(params["v"]), up=False)
        elif action == "link_up":
            self.engine.inject_link_state(str(params["u"]), str(params["v"]), up=True)
        elif action == "link_cost":
            self.engine.inject_link_cost(str(params["u"]), str(params["v"]), float(params["cost"]))
        elif action == "node_crash":
            self.engine.inject_node_crash(str(params["node_id"]))
        elif action == "node_recover":
            self.engine.inject_node_recover(str(params["node_id"]))
        else:
            raise ValueError(f"Unsupported event action: {action}")

        return {"status": "event_injected", "action": action, "params": params}

    async def stop_session(self) -> dict[str, Any]:
        """Halt active simulation run."""
        async with self._lock:
            if self.engine:
                await self.engine.stop()
                self.engine = None
            return {"status": "stopped"}

    def get_state(self) -> dict[str, Any]:
        """Obtain complete snapshot of active simulation."""
        if not self.engine or not self.topology or not self.clock:
            return {
                "active": False,
                "topology": None,
                "current_time": 0.0,
                "is_converged": False,
                "nodes": {},
                "links": {},
            }

        nodes_state: dict[str, Any] = {}
        for nid, node in self.engine.nodes.items():
            nodes_state[nid] = {
                "status": node.status.value,
                "packets_sent": node.packets_sent,
                "packets_received": node.packets_received,
                "flaps": node.flaps_count,
                "routing_table": [
                    {"dst": r.destination, "next_hop": r.next_hop, "cost": r.cost}
                    for r in node.get_table()
                ],
                "state_desc": node.describe_state(),
            }

        links_state: dict[str, Any] = {}
        for key, link in self.engine.links.items():
            links_state[key] = {
                "node_a": link.node_a,
                "node_b": link.node_b,
                "is_up": link.is_up,
                "cost": link.cost,
                "latency_ms": link.latency_ms,
                "in_flight": link.in_flight_count(),
            }

        return {
            "active": True,
            "topology_name": self.topology.name,
            "current_time": self.clock.now(),
            "is_converged": self.engine.convergence_record.is_converged,
            "convergence_time": self.engine.convergence_record.convergence_time_s,
            "protocol": self.active_protocol_name,
            "nodes": nodes_state,
            "links": links_state,
        }

    def export_csv(self) -> str:
        """Export simulation events and metrics to CSV format."""
        if not self.event_store:
            return "seq,timestamp,type,source,data\n"

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["seq", "timestamp", "type", "source", "data"])

        for ev in self.event_store.get_all():
            writer.writerow(
                [
                    ev.seq,
                    round(ev.timestamp, 6),
                    ev.event_type.value,
                    ev.source,
                    json.dumps(ev.data),
                ]
            )

        return output.getvalue()

    def export_json(self) -> dict[str, Any]:
        """Export complete simulation telemetry and events in JSON format."""
        if not self.engine or not self.event_store:
            return {"events": [], "metrics": None}

        collector = MetricsCollector.collect_from_engine(
            self.engine, protocol_name=self.active_protocol_name
        )
        return {
            "state": self.get_state(),
            "metrics": collector.to_dict(),
            "events": [ev.to_dict() for ev in self.event_store.get_all()],
        }


# Global session instance
session_manager = SimulationSessionManager()
