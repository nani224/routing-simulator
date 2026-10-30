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
- **`VirtualClock`**: A discrete-event simulation clock driven by a min-heap priority queue of scheduled callbacks. Runs deterministically across unit tests, hypothesis property suites, and automated benchmarks with bit-for-bit repeatability across platforms. The convergence engine directly inspects `VirtualClock._event_queue` to ensure all pending in-flight timers and protocol transmissions complete before declaring quiescence.

### 2.2 Localhost UDP Sockets & Link Emulator (`routelab.core.node`, `routelab.core.link`)
Each `RouterNode` instance represents an independent network device:
- Binds to an ephemeral UDP socket on `127.0.0.1` and uses real loopback UDP socket transmission (`sendto`) when running in realtime mode while maintaining deterministic discrete event simulation under `VirtualClock`.
- Communicates across logical `LinkEmulator` pipelines modeling:
  - Configurable propagation latency ($\text{latency\_ms}$)
  - Gaussian or uniform jitter ($\text{jitter\_ms}$)
  - Stochastic packet drop ($\text{loss\_rate} \in [0.0, 1.0]$)
  - Packet serialization delay queuing based on link bandwidth ($\text{bandwidth\_bps}$), tracking transmission finish timestamps (`_last_tx_finish_time`) to simulate physical queueing delays
  - Independent symmetric/asymmetric routing costs

### 2.3 Append-Only EventStore (`routelab.core.events`)
Every simulation mutation is recorded in memory using a high-resolution, indexed `EventStore`:
- Events: `PACKET_SENT`, `PACKET_FORWARDED`, `PACKET_DELIVERED`, `PACKET_DROPPED`, `LINK_STATE`, `NODE_STATE`, `TABLE_UPDATE`, `CONVERGENCE`, `ATTACK_INJECTED`.
- Storage: Slot-based compact Python dataclasses with fast messagepack serialization (`to_msgpack()`) for instant timeline scrubbing, replay, and offline forensics.
- Real-time event streams are batched and pushed over WebSocket connections (`/ws/events`), driving authentic packet courier animations on the frontend.

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
2. **Infinite Loops & Watchdog Preemption**: Dynamic untrusted plugins are guarded by thread preemption timeouts (`timeout_s`). If a plugin blocks or enters `while True`, the watchdog aborts execution and isolates the fault. Trusted built-in protocols utilize an optimized fast-path to prevent unnecessary OS thread creation during high-density simulations (up to 100 nodes).
3. **Privilege Escalation**: Plugins only communicate via the restricted `ProtocolContext` API (`ctx.send()`, `ctx.broadcast()`, `ctx.set_timer()`, `ctx.cancel_timer()`, `ctx.neighbors()`). Direct OS access and raw link manipulation are strictly prohibited.

---

## 4. Built-In Protocol Implementations

| Protocol | Algorithm / Standard | Loop Prevention / Mechanics |
| :--- | :--- | :--- |
| **Distance Vector** (`dv.py`) | Distributed Bellman-Ford (RIP-like) | Split-horizon, poison-reverse, triggered updates, genuine hold-down timer suppression (forbids premature re-adoption until expiration), immediate cost update propagation |
| **Link State** (`ls.py`) | Reliable LSA flooding + Dijkstra SPF (OSPF-like) | Sequence numbering, explicit `LSAck` acknowledgment & retransmission queue, active LSA aging (`max_lsa_age_s`) and eviction, recovery LSDB synchronization exchange (`lsdb_request`/`lsdb_response`) |
| **BGP-Lite** (`bgp_lite.py`) | Path Vector routing | `AS_PATH` cycle rejection, `LOCAL_PREF` policy routing, explicit route withdrawal tracking (`withdrawals` field populated on Loc-RIB removal) |
| **Flooding** (`flooding.py`) | Controlled hop-by-hop flooding | Hop count vs cumulative link cost delineation, monotonic sequence tracking, immediate route invalidation upon link failure |
| **Poisoning Attack** (`attacks/poisoning.py`) | Adversarial route poisoning | Advertises malicious metric 1 for arbitrary victim nodes |
| **Secure DV** (`attacks/mitigation.py`) | Authenticated Distance Vector | HMAC-SHA256 signature verification over route vectors with shared keys, cryptographic origin validation, metric sanity checks |

---

## 5. Convergence & Correctness Engine (`routelab.sim`, `routelab.metrics`)

### 5.1 Dual-Criterion Convergence Detector
RouteLab defines convergence deterministically:
$$\text{Converged} \iff (\text{In-Flight Packets} == 0) \land (\text{Pending Event Queue} == 0) \land (\text{Time Since Last Flap} \ge \text{quiescence\_window\_s})$$
- Routing table changes detected in `RouterNode._check_table_flaps()` feed directly into `engine._last_mutation_time` to prevent false early convergence.
- Initial boot-up routing table installations are baselined (`baseline_routing_tables()`), ensuring bootstrap route installations are not falsely classified as route flaps.
- When nodes crash or recover, neighbor states are strictly verified so crashed nodes are never revived erroneously.

### 5.2 NetworkX Correctness Oracle (`routelab.metrics.oracle`) & Protocol Comparator
- Continuous verification against theoretical all-pairs shortest paths ($D_{u}(v) == \text{dijkstra\_path\_length}(G, u, v)$).
- Detects transient and persistent routing loops ($u \to v \to u$) and blackholes.
- Computes Path Stretch factor:
$$\text{Stretch} = \frac{\text{Actual Hops / Latency}}{\text{Oracle Shortest Path}}$$
- `ProtocolComparator` ensures fair benchmarking: if one or both competing protocols fail to converge, `winners["convergence_time"]` reports `"None (Neither Converged)"` rather than declaring a false winner.

---

## 6. Frontend Visualization & Architecture (`frontend/`)

- **Rendering Engine**: Custom HTML5 Canvas 2D with `requestAnimationFrame` yielding 60 FPS on 100+ node scale-free networks.
- **Event-Driven Packet Visualization**: Replaces synthetic random particles with real simulation telemetry (`PACKET_SENT`, `PACKET_FORWARDED`, `PACKET_DELIVERED`) streamed via WebSockets.
- **Timeline Scrubber & State Replay**: Supports scrubbing backwards through time snapshots to review past routing tables and link events.
- **Delineated Metric Terminology**:
  - Distance Vector: Bellman-Ford Shortest Path (Cumulative Metric Cost)
  - Link State: Dijkstra SPF Shortest Path (Cumulative Link Cost)
  - BGP-Lite: Policy AS-Path (AS Hop Count / Preference)
  - Flooding: Hop-Count Discovery Path
- **Design Theme**: *Cartographer's Atlas / Drafting Table* adhering to OKLCH perceptual color tokens:
  - Light mode: Warm antique parchment (`oklch(96.8% 0.014 85)`), hand-drawn ink edges, compass rose watermark.
  - Dark mode: Nautical blueprint (`oklch(16.5% 0.035 240)`), chalk-white lines, amber sextant accents.
- **13 Interactive Workbenches**: Topology canvas, live packet couriers, node inspector, timeline scrubber, attack lab, side-by-side comparative evaluation, Golden Quill path tracer, scenario runner, virtualized event log, artifact export, explain walkthrough, and settings station.
