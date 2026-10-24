# RouteLab Custom Protocol Plugin Guide

Welcome to the RouteLab developer guide! This document explains how to author, test, and benchmark custom routing algorithms within RouteLab.

---

## 1. Plugin Philosophy

RouteLab contains **zero protocol hardcoding** in its simulation core, event store, REST API, or web visualizer. Built-in algorithms (Distance Vector, Link State, BGP-Lite) are only sample implementations of the `RoutingProtocol` interface.

Your custom algorithm will execute inside an **`IsolatedProtocolRunner`** sandbox, protecting the simulation from crashes while providing high-resolution event logging and comparative benchmarking.

---

## 2. The `RoutingProtocol` Interface

Every custom algorithm inherits from `routelab.plugins.interface.RoutingProtocol` and implements six required methods:

```python
from typing import Any
from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol

class MyCustomProtocol(RoutingProtocol):
    def on_start(self, ctx: ProtocolContext) -> None:
        """Invoked when the node initializes. Broadcast initial vectors or schedule timers."""
        self.ctx = ctx
        self.routes: dict[str, str] = {}
        # Schedule periodic hello beacon every 1.0 second (1000ms)
        self.ctx.set_timer("hello_timer", 1000.0)

    def on_message(self, src: str, payload: dict[str, Any]) -> None:
        """Invoked when a neighboring router delivers a packet to this node."""
        msg_type = payload.get("type")
        if msg_type == "ROUTE_ADVERTISEMENT":
            self._handle_advertisement(src, payload.get("routes", {}))

    def on_link_change(self, nbr: str, cost: float, up: bool) -> None:
        """Invoked immediately when an adjacent link fails, recovers, or mutates cost."""
        if not up:
            # Drop routes pointing through this severed neighbor
            self.routes.pop(nbr, None)
            self._trigger_update()

    def on_timer(self, timer_id: str) -> None:
        """Invoked when a scheduled timer expires."""
        if timer_id == "hello_timer":
            self.ctx.broadcast({"type": "HELLO", "node": self.ctx.node_id})
            self.ctx.set_timer("hello_timer", 1000.0)

    def get_table(self) -> list[RouteEntry]:
        """Return the current active routing table for the inspector and oracle."""
        return [
            RouteEntry(destination=dst, next_hop=nh, metric=1.0, protocol="custom")
            for dst, nh in self.routes.items()
        ]

    def describe_state(self) -> dict[str, Any]:
        """Return internal debugging state for UI drawers and event logs."""
        return {"active_routes": len(self.routes)}
```

---

## 3. Working with `ProtocolContext`

The `ctx` object passed to `on_start()` is the router's only interface to the outside world:

| Method | Description |
| :--- | :--- |
| `ctx.node_id` | Returns the string ID of the current router (e.g. `'R1'`). |
| `ctx.now()` | Returns current simulation time in seconds (respects virtual/realtime clocks). |
| `ctx.send(dst, payload)` | Transmits a message dict to an adjacent neighbor node. |
| `ctx.broadcast(payload)` | Transmits a copy of payload to all active neighbor links. |
| `ctx.set_timer(timer_id, delay_ms)` | Schedules a named timer callback in milliseconds. |
| `ctx.cancel_timer(timer_id)` | Cancels a pending scheduled timer. |
| `ctx.neighbors()` | Returns a list of `NeighborInfo(node_id, cost, is_up, latency_ms)`. |

---

## 4. Complete Example: Epidemic Gossip Routing

Here is a working implementation of a gossip-based routing protocol:

```python
"""gossip_routing.py - Custom RouteLab Plugin."""

from typing import Any
from routelab.plugins.interface import NeighborInfo, ProtocolContext, RouteEntry, RoutingProtocol

class GossipRoutingProtocol(RoutingProtocol):
    def __init__(self, fanout: int = 2) -> None:
        self.fanout = fanout
        self.ctx: ProtocolContext | None = None
        self.table: dict[str, tuple[str, float]] = {}  # dest -> (next_hop, cost)

    def on_start(self, ctx: ProtocolContext) -> None:
        self.ctx = ctx
        self.ctx.set_timer("gossip_beacon", 500.0)

    def on_message(self, src: str, payload: dict[str, Any]) -> None:
        if self.ctx is None:
            return
        
        updated = False
        advertised = payload.get("routes", {})
        for dest, metric in advertised.items():
            if dest == self.ctx.node_id:
                continue
            new_cost = metric + 1.0
            if dest not in self.table or new_cost < self.table[dest][1]:
                self.table[dest] = (src, new_cost)
                updated = True

        if updated:
            self._gossip()

    def on_link_change(self, nbr: str, cost: float, up: bool) -> None:
        if not up:
            # Purge severed routes
            self.table = {d: (nh, c) for d, (nh, c) in self.table.items() if nh != nbr}

    def on_timer(self, timer_id: str) -> None:
        if self.ctx is None:
            return
        if timer_id == "gossip_beacon":
            self._gossip()
            self.ctx.set_timer("gossip_beacon", 500.0)

    def _gossip(self) -> None:
        if self.ctx is None:
            return
        routes_summary = {d: c for d, (_, c) in self.table.items()}
        routes_summary[self.ctx.node_id] = 0.0
        self.ctx.broadcast({"type": "GOSSIP", "routes": routes_summary})

    def get_table(self) -> list[RouteEntry]:
        return [
            RouteEntry(destination=d, next_hop=nh, metric=c, protocol="gossip")
            for d, (nh, c) in self.table.items()
        ]

    def describe_state(self) -> dict[str, Any]:
        return {"known_destinations": list(self.table.keys())}
```

---

## 5. Testing & Benchmarking Your Plugin

### 5.1 Unit Testing with Hypothesis & NetworkX Oracle
```python
from routelab.core.clock import VirtualClock
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import generate_scale_free
from routelab.metrics.oracle import NetworkXOracle

async def test_my_plugin():
    topo = generate_scale_free(num_nodes=10, m=2)
    vclock = VirtualClock()
    engine = SimulationEngine(topology=topo, protocol_factory=GossipRoutingProtocol, clock=vclock)

    await engine.start()
    while vclock.now() < 3.0:
        await vclock.step()
        if engine.check_convergence():
            break

    # Verify against oracle
    oracle = NetworkXOracle(topo)
    report = oracle.evaluate_all(engine.get_all_routes())
    assert report.is_correct is True
```

### 5.2 Comparative Benchmarking
Run the built-in comparator CLI:
```bash
python -m routelab.sim.comparator --topology course-6-node --protocols distance_vector link_state gossip
```
Or open the **Comparative Algorithm Evaluation Workbench** in the web interface to view live side-by-side speedup metrics and overhead charts.
