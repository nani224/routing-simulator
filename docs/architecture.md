# RouteLab Architecture Specification

## 1. Executive Summary

**RouteLab** is a modular, high-performance, pluggable routing protocol simulator built for comparative evaluation of distributed network routing algorithms (Distance Vector, Link State, BGP-Lite, Flooding, and adversarial scenarios). 

The platform is designed with a strict decoupling between:
1. **Physical Execution**: Asyncio-driven networking on real localhost UDP sockets.
2. **Logical Simulation Engine**: Dual clocks (Deterministic VirtualClock and Wall-Clock RealtimeClock), priority-queue link emulation, and an append-only binary event store.
3. **Pluggable Protocols**: Zero engine hardcoding. Any algorithm implementing `RoutingProtocol` runs in an isolated runner with CPU/memory bounds and exception sandboxing.
4. **Interactive Cartographer UI**: An HTML5 Canvas 2D visualization rendering 100+ nodes at 60 FPS under the bespoke *Cartographer's Atlas / Drafting Table* design system.

---

## 2. Core Components

### 2.1 Dual Clock Engine (`routelab.core.clock`)
RouteLab provides two interchangeable clock mechanisms deriving from `Clock`:
- **`RealtimeClock`**: Synchronizes with wall-clock time (`time.monotonic()`) with dynamic speed scaling ($0.1\times$ to $5.0\times$), pausing, and stepping. Used for live demonstrations and interactive WebSocket streaming.
- **`VirtualClock`**: A discrete-event simulation clock driven by a min-heap priority queue of scheduled callbacks. Runs deterministically across unit tests, hypothesis property suites, and automated benchmarks with bit-for-bit repeatability across platforms.

### 2.2 Localhost UDP Sockets & Link Emulator (`routelab.core.node`, `routelab.core.link`)
Each `RouterNode` instance represents an independent network device:
- Binds to an ephemeral UDP socket on `127.0.0.1`.
- Communicates across logical `LinkEmulator` pipelines modeling:
  - Configurable propagation latency ($\text{latency\_ms}$)
  - Gaussian or uniform jitter ($\text{jitter\_ms}$)
  - Stochastic packet drop ($\text{loss\_rate} \in [0.0, 1.0]$)
  - Serialization delay based on link bandwidth ($\text{bandwidth\_bps}$)
  - Independent symmetric/asymmetric routing costs

### 2.3 Append-Only EventStore (`routelab.core.events`)
Every simulation mutation is recorded in memory using a high-resolution, indexed `EventStore`:
- Events: `PACKET_SENT`, `PACKET_DELIVERED`, `PACKET_DROPPED`, `LINK_STATE`, `NODE_STATE`, `TABLE_UPDATE`, `CONVERGENCE`, `ATTACK_INJECTED`.
- Storage: Slot-based compact Python dataclasses with fast messagepack serialization (`to_msgpack()`) for instant timeline scrubbing, replay, and offline forensics.
- Bounded memory buffers prevent leaks during extended multi-hour soak tests.

---

## 3. Pluggable Routing Protocol Architecture (`routelab.plugins`)

The simulator does not contain hardcoded assumptions about packet formats, metric semantics, or convergence criteria.

### 3.1 The `RoutingProtocol` Abstract Base Class
```python
class RoutingProtocol(ABC):
    @abstractmethod
    def on_start(self, ctx: ProtocolContext) -> None: ...

    @abstractmethod
    def on_message(self, src: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def on_link_change(self, nbr: str, cost: float, up: bool) -> None: ...

    @abstractmethod
    def on_timer(self, timer_id: str) -> None: ...

    @abstractmethod
    def get_table(self) -> list[RouteEntry]: ...

    @abstractmethod
    def describe_state(self) -> dict[str, Any]: ...
```

### 3.2 Security Sandbox & Isolation (`IsolatedProtocolRunner`)
Each protocol instance runs inside an `IsolatedProtocolRunner` protecting the simulation engine from:
1. **Uncaught Exceptions**: If a custom plugin throws `ZeroDivisionError` or invalid array indexing, the runner catches the error, increments a fault counter, and flags the node as `FAULTY` without crashing the engine loop.
2. **Infinite Loops & Stalls**: Timed callbacks are constrained by execution watchdogs.
3. **Privilege Escalation**: Plugins only communicate via the restricted `ProtocolContext` API (`ctx.send()`, `ctx.broadcast()`, `ctx.set_timer()`, `ctx.cancel_timer()`, `ctx.neighbors()`). Direct OS access and raw link manipulation are strictly prohibited.

---

## 4. Built-In Protocol Implementations

| Protocol | Algorithm / Standard | Loop Prevention / Mechanics |
| :--- | :--- | :--- |
| **Distance Vector** (`dv.py`) | Distributed Bellman-Ford (RIP-like) | Split-horizon, poison-reverse, triggered updates, hold-down timers |
| **Link State** (`ls.py`) | Reliable LSA flooding + heapq Dijkstra (OSPF-like) | Sequence numbering, max-age flush, link-state database (LSDB), min Dijkstra intervals |
| **BGP-Lite** (`bgp_lite.py`) | Path Vector routing | `AS_PATH` cycle rejection, `LOCAL_PREF` policy routing, route withdrawal |
| **Flooding** (`flooding.py`) | Controlled hop-by-hop flooding | Monotonic packet sequence cache, TTL bounding |
| **Poisoning Attack** (`attacks/poisoning.py`) | Adversarial route poisoning | Advertises malicious metric 1 for arbitrary victim nodes |
| **Secure DV** (`attacks/mitigation.py`) | Authenticated Distance Vector | Cryptographic origin validation, bounded cost decrease filtering |

---

## 5. Convergence & Correctness Engine (`routelab.sim`, `routelab.metrics`)

### 5.1 Dual-Criterion Convergence Detector
RouteLab defines convergence deterministically:
$$\text{Converged} \iff (\text{In-Flight Packets} == 0) \land (\text{Time Since Last Flap} \ge \text{quiescence\_window\_s})$$

### 5.2 NetworkX Correctness Oracle (`routelab.metrics.oracle`)
A built-in oracle continuously tracks the physical graph using NetworkX:
- Verifies that routing tables match theoretical all-pairs shortest paths ($D_{u}(v) == \text{dijkstra\_path\_length}(G, u, v)$).
- Detects transient and persistent routing loops ($u \to v \to u$).
- Identifies blackholes (unreachable destinations with non-null next-hops).
- Computes Path Stretch factor:
$$\text{Stretch} = \frac{\text{Actual Hops / Latency}}{\text{Oracle Shortest Path}}$$

---

## 6. Frontend Visualization & Architecture (`frontend/`)

- **Rendering Engine**: Custom HTML5 Canvas 2D with `requestAnimationFrame` yielding 60 FPS on 100+ node scale-free networks.
- **Design Theme**: *Cartographer's Atlas / Drafting Table* adhering to OKLCH perceptual color tokens:
  - Light mode: Warm antique parchment (`oklch(96.8% 0.014 85)`), hand-drawn ink edges, compass rose watermark.
  - Dark mode: Nautical blueprint (`oklch(16.5% 0.035 240)`), chalk-white lines, amber sextant accents.
- **13 Interactive Workbenches**: Topology canvas, live packet couriers, node inspector, timeline scrubber, attack lab, side-by-side comparative evaluation, Golden Quill path tracer, scenario runner, virtualized event log, artifact export, explain walkthrough, and settings station.
