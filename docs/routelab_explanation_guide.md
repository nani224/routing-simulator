# RouteLab Dynamic Routing Protocol Simulator: Comprehensive Technical & Architectural Guide

> **Course Project**: Team 20 — "Distance Vector, Link State & BGP: A Comparative Routing Simulator"  
> **Authors**: Aakarsh, Sravan, Sneha  
> **Repository**: [https://github.com/nani224/routing-simulator](https://github.com/nani224/routing-simulator)  
> **Document Purpose**: Complete technical breakdown of the RouteLab architecture, protocols, packet movement, node mechanics, failure modes, and simulation controls for project presentations, viva examinations, and code defense.

---

## Table of Contents
1. [Project Overview & Core Problem Solved](#1-project-overview--core-problem-solved)
2. [Routing Protocols Implemented](#2-routing-protocols-implemented)
   - Distance Vector (Bellman-Ford, RIP-like)
   - Link State (Dijkstra SPF, OSPF-like)
   - BGP-Lite (Path-Vector, AS_PATH loop detection)
   - Flooding Baseline
   - Route Poisoning Attack & Secure DV Defense
   - Summary Comparison Table
3. [Packet Movement, Latency, and Route Calculation](#3-packet-movement-latency-and-route-calculation)
4. [Routers and Nodes: Implementation & Virtualization Model](#4-routers-and-nodes-implementation--virtualization-model)
   - Real Networking vs. Simulated Mechanics
5. [Router Information Popup: Field-by-Field Breakdown](#5-router-information-popup-field-by-field-breakdown)
6. [Crash and Recovery Internals](#6-crash-and-recovery-internals)
7. [Simulation Controls & Golden Quill Path Tracer](#7-simulation-controls--golden-quill-path-tracer)
8. [End-to-End System Architecture](#8-end-to-end-system-architecture)
9. [Viva / Presentation Quick Reference Cheatsheet](#9-viva--presentation-quick-reference-cheatsheet)

---

## 1. Project Overview & Core Problem Solved

### What is RouteLab?
**RouteLab** is an interactive, real-time, pluggable routing protocol simulator designed to model, visualize, and benchmark how distributed routing algorithms make decisions across computer networks. It provides a visual "Cartographer's Drafting Table" interface paired with an event-driven networking engine.

### What Problem Does It Solve?
1. **The "Black Box" Learning Curve of Computer Networking**:
   In traditional networking education or testing, routing protocols run as background daemons (`routed`, `frr`, `quagga`, or Cisco IOS/Junos). Students and engineers only see final static tables via CLI commands like `show ip route`. They cannot observe:
   - The exchange of intermediate routing control messages traversing links in real time.
   - The transient formation and resolution of routing loops.
   - How count-to-infinity occurs during sudden fiber cuts or power outages.
   - How different algorithms scale in control packet overhead versus convergence time.
2. **Hardcoded Simulators**:
   Most educational simulators (e.g., standard Cisco Packet Tracer labs or ad-hoc Python scripts) hardcode distance vector or Dijkstra algorithms into the simulator's core loop. RouteLab provides **zero hardcoding**: the simulation engine is completely algorithm-agnostic. Any routing protocol runs as a sandboxed plug-and-play plugin implementing the `RoutingProtocol` abstract base class.
3. **Rigorous Comparative Benchmarking**:
   RouteLab allows running different algorithms over **identical network topologies** with **identical event schedules** (e.g., node failure at $t = 2.0\text{s}$, cost modification at $t = 4.0\text{s}$) to evaluate:
   - **Convergence Time**: Wall-clock / virtual seconds to establish stable, loop-free shortest paths.
   - **Control Message Overhead**: Total packets and bytes exchanged on the wire.
   - **Route Flaps**: Total table mutation events.
   - **Path Stretch Factor**: Ratio of the actual routed path cost to theoretical graph optimality.

---

## 2. Routing Protocols Implemented

RouteLab implements four core routing protocols and two security/adversarial modules located in `backend/routelab/protocols/` and `backend/routelab/attacks/`.

```
backend/routelab/
├── protocols/
│   ├── dv.py         -> DistanceVectorProtocol (Bellman-Ford / RIP)
│   ├── ls.py         -> LinkStateProtocol (Dijkstra SPF / OSPF)
│   ├── bgp_lite.py   -> BGPLiteProtocol (Path-Vector / BGP-4)
│   └── flooding.py   -> FloodingProtocol (Controlled Flooding Baseline)
└── attacks/
    ├── poisoning.py  -> PoisoningAttackProtocol (Byzantine False-Metric Injection)
    └── mitigation.py -> SecureDistanceVectorProtocol (Cryptographic Origin Validation)
```

### 2.1 Distance Vector Protocol (`backend/routelab/protocols/dv.py`)
* **Underlying Algorithm**: Distributed Bellman-Ford algorithm (analogous to RIP - Routing Information Protocol, RFC 2453).
* **Core Logic**:
  - Each router knows only its immediate neighbors and their link costs: $c(x, v)$.
  - Periodically (every `periodic_interval_s = 2.0s`) and upon network changes (Triggered Updates), each router sends its full distance vector $D_x = [D_x(y) : y \in V]$ to all active neighbors.
  - Upon receiving an advertisement from neighbor $v$, router $x$ updates its table using the Bellman-Ford equation:
    $$D_x(y) = \min_v \{ c(x, v) + D_v(y) \}$$
* **Loop Prevention & Mitigations**:
  - **Split Horizon**: A router does not advertise a route back out the interface through which it learned that route (`if route.next_hop == nbr: continue`).
  - **Poison Reverse**: Rather than omitting the route, the router advertises an unreachable metric $\infty$ (configured as `16.0`) back to the neighbor it uses as next-hop (`cost = self.infinity`).
  - **Triggered Updates**: Transmits delta updates immediately when link state or metric mutates, rather than waiting for the periodic timer.
  - **Hold-down Timers**: When a route fails, the router enters a hold-down state during which it ignores higher-cost alternative paths to prevent transient counting-to-infinity.

### 2.2 Link State Protocol (`backend/routelab/protocols/ls.py`)
* **Underlying Algorithm**: Reliable Link State Advertisement (LSA) flooding + Dijkstra's Shortest Path First (SPF) algorithm (analogous to OSPF, RFC 2328).
* **Core Logic**:
  - **Global Topology Map**: Unlike Distance Vector (where routers only share "distances to destinations"), every Link State router floods Link State Advertisements (`LSA`) describing its local links: `(neighbor_id, cost)`.
  - **Reliable Flooding & $O(1)$ Duplicate Suppression**: Each LSA contains an advertisement origin (`adv_router`) and a monotonically increasing sequence number (`seq`). When a router receives an LSA:
    ```python
    current_lsa = self.lsdb.get(adv)
    if current_lsa is not None and lsa.seq <= current_lsa.seq:
        return  # Drop duplicate or stale LSA immediately
    ```
    New LSAs are saved into the Link State Database (`LSDB`) and forwarded out all other active interfaces except the incoming link (Split-Horizon Flooding).
  - **Dijkstra SPF Computation**: When the LSDB changes (`self._spf_dirty = True`), the router constructs an adjacency graph from the LSDB and executes Dijkstra's algorithm using a min-heap priority queue (`heapq`):
    - Computes the shortest branch tree rooted at `self._node_id`.
    - Identifies the first-hop neighbor along the optimal branch for every destination.

### 2.3 BGP-Lite Protocol (`backend/routelab/protocols/bgp_lite.py`)
* **Underlying Algorithm**: Path-Vector Routing (analogous to BGP-4, RFC 4271).
* **Core Logic**:
  - Used for inter-domain routing between Autonomous Systems (`AS`). Each node is assigned an Autonomous System identifier (`as_id` or `as_number`, e.g., AS100, AS200).
  - Routes are advertised with an explicit path vector: `AS_PATH = [AS100, AS200, AS300]`.
* **AS_PATH Loop Prevention**:
  - Loop detection is mathematical and absolute: If a router receives a BGP advertisement whose `AS_PATH` already contains its own Autonomous System ID, the update is immediately discarded:
    ```python
    if self.as_id in as_path:
        logger.debug("BGP loop detected: AS %s already in path %s", self.as_id, as_path)
        continue
    ```
* **BGP Decision Process (Best Path Selection)**:
  When multiple candidate paths exist for destination $d$, BGP-Lite applies standard RFC tie-breaking:
  1. Highest Local Preference (`LOCAL_PREF`, configured via `peer_policies`).
  2. Shortest `AS_PATH` length (fewer AS hops).
  3. Lowest Multi-Exit Discriminator (`MED`).
  4. Lowest interior peer link cost.
  5. Deterministic tie-break on peer identifier.
* **Explicit Route Withdrawals**: When a link drops or reachability is lost, the router issues a `BGP_UPDATE` containing explicit `withdrawals: [dst]`.

### 2.4 Controlled Flooding Baseline (`backend/routelab/protocols/flooding.py`)
* **Underlying Algorithm**: Naive packet broadcast with sequence cache and Time-To-Live (`TTL`).
* **Core Logic**:
  - Whenever a node wants to announce its presence, it broadcasts a packet to all neighbors with `hops = 0` and `ttl = 16`.
  - Neighbors cache `(origin, seq)` in `self.seen_messages`. Duplicate packets are dropped.
  - Non-duplicates record the reverse path: `discovered_routes[origin] = (hops + 1, src)`.
  - If `ttl > 1`, the packet is decremented and re-flooded out all other links.
* **Purpose**: Serves as an educational baseline to show the massive packet overhead of naive flooding compared to Link State or Distance Vector.

### 2.5 Security Modules: Poisoning Attack & Secure DV Defense
* **Poisoning Attack (`backend/routelab/attacks/poisoning.py`)**:
  - Implements a Byzantine compromised router (`PoisoningAttackProtocol`).
  - Periodically broadcasts forged distance vectors claiming direct reachability to a target victim router (e.g., `R6`) with a malicious cost of `1.0`:
    ```python
    vector[self.victim_node] = self.poison_cost  # Forges 1.0
    ```
  - Legitimate routers adopt this false route, funneling traffic into a blackhole or man-in-the-middle intercept.
* **Secure DV Defense (`backend/routelab/attacks/mitigation.py`)**:
  - Implements `SecureDistanceVectorProtocol` with **Cryptographic Origin Validation** and metric sanity checks:
    ```python
    if dst in self.authorized_origins:
        allowed = self.authorized_origins[dst]
        if src not in allowed and dst != src:
            self.rejected_poison_count += 1
            continue  # Drops forged advertisement
    ```

### Protocol Comparison Summary Table

| Feature / Metric | Distance Vector (RIP) | Link State (OSPF) | BGP-Lite (BGP-4) | Flooding Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **Routing Algorithm** | Distributed Bellman-Ford | Dijkstra Shortest Path First (SPF) | Path-Vector Best Path Selection | Hop-by-Hop Broadcast |
| **Information Shared** | Distance vector to all known destinations | Local link states (`neighbor_id, cost`) | Destination prefix + `AS_PATH` vector | Hop count and sequence origin |
| **Knowledge Scope** | Local neighbors only ("routing by rumor") | Full network topology map in LSDB | Autonomous System path traversal | Hop distance to source |
| **Loop Prevention** | Split Horizon, Poison Reverse, Hold-down | Monotonic LSA sequence numbers | `AS_PATH` loop inspection | Monotonic packet cache `(origin, seq)` |
| **Convergence Speed** | Moderate to Slow (iterative relaxation) | Extremely Fast (immediate LSA flood) | Fast (explicit withdrawals) | Fast, but consumes link bandwidth |
| **Message Overhead** | Low to Moderate (periodic vectors) | Low steady-state, bursty during topology change | Very Low (incremental updates only) | Extremely High ($O(E)$ per packet) |
| **Metric Used** | Additive link costs / hop count | Additive link costs (bandwidth-derived) | Policy (`LOCAL_PREF`, AS hops, MED) | Hop count |

---

## 3. Packet Movement, Latency, and Route Calculation

### How Routing Messages are Created
1. **Creation**:
   When an event occurs (timer tick in `on_timer`, or link change in `on_link_change`), the active protocol calls:
   `ctx.send(nbr, payload)` or `ctx.broadcast(payload)`.
2. **Binary Wire Encoding**:
   In `RouterNode.send()` (`backend/routelab/core/node.py`), the message is wrapped into a `Packet` dataclass (`backend/routelab/core/packet.py`):
   ```python
   pkt = Packet(
       src=self.node_id,
       dst=nbr,
       proto=self._protocol.name,
       seq=self._seq,
       ttl=32,
       timestamp=self.clock.now(),
       payload=payload,
       packet_type=PacketType.CONTROL,
   )
   ```
   The packet is serialized using high-performance binary **MessagePack** (`msgpack.packb`), caching its exact wire size (`pkt.byte_size = len(encoded)`).

### How Packets Traverse Links (Latency, Jitter, and Bandwidth)
Packets do not reach the destination instantaneously. They pass through the `LinkEmulator` (`backend/routelab/core/link.py`):
1. **Link Status Verification**:
   If `link.is_up == False`, the packet is dropped immediately (`stats.packets_dropped_down += 1`).
2. **Stochastic Packet Loss**:
   If `random.random() < link.loss_rate`, the packet is dropped (`stats.packets_dropped_loss += 1`).
3. **Delay Calculation**:
   The transmission delay models real physical line properties:
   $$\text{Total Delay} = \max\left(0.001, \frac{\text{latency\_ms}}{1000} + \text{jitter\_s}\right) + \frac{\text{pkt\_bytes} \times 8}{\text{bandwidth\_bps}}$$
   - $\text{latency\_ms}$: Propagation delay across the medium (e.g., 10ms).
   - $\text{jitter\_s}$: Uniform random fluctuation drawn from $[-\text{jitter\_ms}, +\text{jitter\_ms}]$.
   - $\frac{\text{pkt\_bytes} \times 8}{\text{bandwidth\_bps}}$: Serialization delay on band-limited links.
4. **Heap-Based In-Flight Pipeline**:
   The packet is wrapped into `_InFlightPacket(delivery_time = now + total_delay, packet=pkt, callback=...)` and inserted into a min-heap priority queue (`heapq.heappush(self._queue, in_flight)`).
   A dedicated worker coroutine sleeps until the earliest packet's `delivery_time`, popping it from the heap and invoking the neighbor's `receive_packet(pkt)` callback.

### How Packets are Animated on Screen
* The React frontend runs a 60 FPS animation loop driven by `requestAnimationFrame` in `frontend/src/App.tsx`.
* The simulator maintains an array of `PacketCourier` objects:
  ```typescript
  interface PacketCourier {
    id: string;
    src: string;
    dst: string;
    progress: number; // 0.0 (source) to 1.0 (destination)
    speed: number;
    protocol: string;
    payloadType: 'LSA' | 'VECTOR' | 'BGP';
  }
  ```
* On each frame tick, `pkt.progress += pkt.speed * dt * speed_multiplier`.
* In `frontend/src/components/TopologyCanvas.tsx`, the 2D Canvas computes the interpolated pixel coordinate:
  $$x(t) = x_{\text{src}} + (x_{\text{dst}} - x_{\text{src}}) \times \text{progress}$$
  $$y(t) = y_{\text{src}} + (y_{\text{dst}} - y_{\text{src}}) \times \text{progress}$$
  The canvas renders a luminous courier particle with an outer pulse ring, color-coded by protocol:
  - **Copper / Ochre (`#C87533`)**: Distance Vector
  - **Verdigris Green (`#3D8B7A`)**: Link State
  - **Cobalt Blue (`#2A5298`)**: BGP-Lite
* When `progress >= 1.0`, the courier is removed, the arrival chime plays (Web Audio API synthesis), and the target router's RX counter increments.

### How the Optimal Path is Calculated
1. **Next-Hop Forwarding**:
   Routers do not pre-calculate whole end-to-end paths when forwarding. Instead, each router $u$ inspects its local routing table for destination $d$. If the entry says `next_hop = v`, router $u$ forwards the packet to adjacent neighbor $v$. Router $v$ then performs its own lookup.
2. **Optimal Path Selection**:
   - In **Distance Vector**, shortest paths emerge iteratively through Bellman-Ford equation relaxation.
   - In **Link State**, shortest paths are computed directly by running Dijkstra's algorithm over the synchronized LSDB.
   - In **BGP-Lite**, path selection follows policy preference (`LOCAL_PREF`) followed by AS-path length.
3. **Path Tracer Verification**:
   The frontend Golden Quill Path Tracer (`frontend/src/components/PathTracerPanel.tsx`) simulates hop-by-hop packet forwarding from a source router to a destination router using the routers' actual computed `next_hop` pointers. If a node points back to an already visited node, the tracer flags **"LOOP DETECTED"**. If a next-hop pointer is missing or points to a crashed router, it flags **"BLACKHOLE"**.

---

## 4. Routers and Nodes: Implementation & Virtualization Model

### Are these actual routers, virtual machines, or software objects?
The nodes labeled **R1, R2, R3...** are **software objects** running inside an asynchronous Python runtime. They are **not** hardware routers, and they are **not** heavyweight operating system Virtual Machines (like VirtualBox, QEMU, or Docker containers). 

Each router is an instance of the `RouterNode` class (`backend/routelab/core/node.py`).

```
+-------------------------------------------------------------------+
|                           RouterNode (R1)                         |
|                                                                   |
|  [Operational State: NodeStatus.RUNNING]                          |
|  [Localhost UDP Socket: 127.0.0.1:52341 (DatagramTransport)]      |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |           IsolatedProtocolRunner (Security Sandbox)         |  |
|  |  +-------------------------------------------------------+  |  |
|  |  | Protocol Plugin: DistanceVectorProtocol / LinkState   |  |  |
|  |  | Routing Table: { Dest -> DVRoute(cost, next_hop) }    |  |  |
|  |  +-------------------------------------------------------+  |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
|  Links: {"R2": LinkEmulator, "R3": LinkEmulator}                  |
|  Counters: TX=42, RX=38, Flaps=3                                  |
+-------------------------------------------------------------------+
```

### Real Networking Behavior vs. Simulated Behavior

#### What is REAL:
1. **Real Operating System UDP Sockets**:
   During `node.start()`, each router creates an actual operating system datagram socket bound to `127.0.0.1` on an ephemeral OS port using Python's asyncio event loop:
   ```python
   loop = asyncio.get_running_loop()
   transport, _ = await loop.create_datagram_endpoint(
       lambda: _UDPProtocol(self),
       local_addr=(self.bind_host, self.bind_port),  # 127.0.0.1:0
   )
   self._assigned_port = transport.get_extra_info("sockname")[1]
   ```
2. **Real Binary Serialization**:
   Messages are not Python object references in memory; they are encoded into raw binary wire bytes via `msgpack` and parsed through `Packet.from_bytes(data)`.
3. **Real Sandboxing**:
   Protocols execute inside an `IsolatedProtocolRunner` (`backend/routelab/plugins/loader.py`). If a protocol crashes (e.g., divide-by-zero or memory fault), the runner intercepts the exception, marks the node as `FAULTY`, and prevents the simulation engine from failing.
4. **Real Async Concurrency**:
   Timers, periodic heartbeats, and packet deliveries execute concurrently using standard Python `asyncio` tasks.

#### What is SIMULATED:
1. **No Physical Cables / Layer-1 PHY**:
   Ethernet frames, optical transceivers, and CSMA/CD are not simulated. Packets travel across `LinkEmulator` priority queues.
2. **Logical Link Topologies**:
   Instead of physical switch ports (`eth0`, `ge-0/0/0`), nodes have a dictionary of logical link mappings: `self.links: dict[str, LinkEmulator]`.
3. **Client-Side Engine (Offline Mode)**:
   In standalone browser mode (when the Python backend is disconnected), `frontend/src/App.tsx` and `frontend/src/services/api.ts` execute a high-fidelity client-side simulation engine in TypeScript. It computes shortest-path relaxations at 60 FPS and animates couriers directly on the canvas without needing server round-trips.

---

## 5. Router Information Popup: Field-by-Field Breakdown

When you click on any router (e.g., **R1**), the **Node Inspector Drawer** (`frontend/src/components/NodeInspectorDrawer.tsx`) opens.

```
+-------------------------------------------------------------+
| (R1) Router R1                        [STATUS: RUNNING] [X] |
+-------------------------------------------------------------+
| [Crash Node]                  TX: 48  RX: 52   Flaps: 3     |
+-------------------------------------------------------------+
| [ Routing Table ]   [ Neighbors (2) ]   [ LSDB View ]       |
+-------------------------------------------------------------+
| DEST   | NEXT HOP | METRIC | PROTOCOL                       |
| R2     | R2       | 1      | [DV]                           |
| R3     | R2       | 3      | [DV]                           |
| R4     | R2       | 4      | [DV]                           |
| R5     | R2       | 6      | [DV]                           |
| R6     | R2       | 6      | [DV]                           |
+-------------------------------------------------------------+
```

### 1. Header & Telemetry Chips
* **STATUS**:
  - `STATUS: RUNNING`: Router is operating normally. Protocol timers are running and incoming packets are processed.
  - `STATUS: CRASHED`: Router has experienced an abrupt power failure or kernel panic. All active timers are purged, and incoming packets are dropped.
* **TX (Packets Transmitted)**:
  Cumulative count of all control packets sent by this router across all connected interfaces (`node.packets_sent`).
* **RX (Packets Received)**:
  Cumulative count of valid packets delivered to this router by link emulators (`node.packets_received`).
* **Flaps (Route Flap Count)**:
  A **route flap** occurs when a route's metric, next-hop, or reachability state changes. In `RouterNode._check_table_flaps()`:
  ```python
  table_sig = hash(tuple((r.destination, r.next_hop, r.cost) for r in table))
  if self._last_table_hash != 0 and table_sig != self._last_table_hash:
      self.flaps_count += 1
  ```
  High flaps indicate route instability or oscillations (such as during count-to-infinity).

### 2. Routing Table Tab
* **DEST (Destination)**:
  The target router ID that this route reaches (e.g., `R2`, `R3`, `R4`, `R5`, `R6`).
* **NEXT HOP**:
  The immediate neighboring router to which packets addressed to `DEST` should be handed off.
  - In our Course 6-Node screenshot example for **R1**, every destination lists `NEXT HOP = R2`. This means R1 reaches the entire network via R2 because link `R1 <-> R2` (cost 1) is cheaper than link `R1 <-> R3` (cost 4).
  - If a destination is directly connected and reached through a local interface, it displays `DIRECT`.
* **METRIC**:
  The cumulative routing cost from this router to `DEST`.
  - In the screenshot:
    - Path $R1 \to R2$: Metric = $1$
    - Path $R1 \to R2 \to R3$: Metric = $1 + 2 = 3$
    - Path $R1 \to R2 \to R4$: Metric = $1 + 3 = 4$
    - Path $R1 \to R2 \to R3 \to R5$: Metric = $1 + 2 + 3 = 6$
    - Path $R1 \to R2 \to R3 \to R5 \to R6$: Metric = $1 + 2 + 3 + 1 = 6$ (or $1 + 3 + 2 = 6$)
  - If metric $\ge 16$ (in RIP) or $\ge 9999$, the UI renders in red: `∞ (POISON)`.
* **PROTOCOL**:
  The protocol module responsible for installing this routing table entry:
  - `[DV]`: Distance Vector protocol plugin.
  - `[LS]`: Link State protocol plugin.
  - `[BG]`: BGP-Lite (displays `AS_PATH`, e.g., `[AS100 AS200]`).

### 3. Neighbors Tab
* **Neighbor**: The adjacent node ID connected via a physical/logical link (e.g., `R2`, `R3`).
* **COST**: The configured routing metric weight assigned to that link (e.g., `1` for link `R1-R2`, `4` for link `R1-R3`).
* **LATENCY**: The simulated transmission delay across that link (e.g., `10ms`).
* **STATUS**:
  - `ONLINE`: Link is intact; packets can pass.
  - `DOWN`: Link is broken (fiber cut or neighbor crash); packets are dropped.

---

## 6. Crash and Recovery Internals

The Node Inspector features **Crash Node** and **Recover Node** buttons.

### What Happens Internally During "Crash Node"?
When `handleCrashNode("R2")` is triggered in the frontend and `inject_node_crash("R2")` executes in the backend engine (`backend/routelab/sim/engine.py`):

```
                       1. Node R2 Crashes
                     [status = NodeStatus.CRASHED]
                     [Timers canceled, sockets stopped]
                                  |
                                  v
                  2. Neighbor Notification Loop
           For each neighbor N in [R1, R3, R4]:
           N.notify_link_change("R2", cost=999999, up=False)
                                  |
                                  v
              3. Neighbor Protocol State Adaptation
   - Distance Vector: Invalidate all routes where next_hop == "R2"
                      (Set metric = 16 / Infinity).
                      Trigger immediate Poison Reverse advertisements.
   - Link State:      Originate new LSA with seq + 1 (omitting R2).
                      Flood LSA across surviving links.
                      Re-run Dijkstra SPF to find detour paths.
                                  |
                                  v
              4. Network Convergence Invalidation
           engine._is_converged = False
           Packet couriers in transit to R2 are dropped.
```

1. **Abrupt Node Halt**:
   `node.crash()` changes `node.status` from `RUNNING` to `CRASHED`. All registered timers (`periodic_update`, `refresh_lsa`) are canceled via `node._cancel_all_timers()`. The node stops emitting packets.
2. **Neighbor Notification**:
   All links connected to the crashed node have their status toggled to `is_up = False`. The engine invokes `notify_link_change(crashed_id, cost=999999, up=False)` on all adjacent peers.
3. **Routing Table Invalidation**:
   - In **Distance Vector**: Surviving neighbors scan their routing tables. Any destination whose `next_hop` was the crashed router is marked with metric $\infty$ (`16.0`). Triggered updates propagate the failure across the network.
   - In **Link State**: Neighbors generate a new Link State Advertisement (`LSA`) with an incremented sequence number, removing the crashed node from their link lists. The LSA floods throughout the surviving topology, and each router re-runs Dijkstra's algorithm.
4. **Packet Movement & Blackholes**:
   Any packet couriers currently in transit toward the crashed router reach a dead link and are discarded (`packets_dropped_down`).
5. **Convergence Reset**:
   `_is_converged` is reset to `False`. The convergence clock restarts to measure how long the network takes to re-route around the failure.

### What Happens Internally During "Recover Node"?
1. `node.recover()` sets `status = NodeStatus.RUNNING` and re-invokes `protocol.on_start()`.
2. Connected links are restored to `is_up = True`.
3. The recovered node re-discovers its neighbors and broadcasts its initial routing advertisements.
4. Neighbors update their adjacency tables, lower their route metrics back to optimal values, and the network achieves a new converged state.

---

## 7. Simulation Controls & Golden Quill Path Tracer

```
+------------------------------------------------------------------------------------------------------+
| [RouteLab] [Course 6-Node v] [Distance Vector v] [|| Pause] [>> Step] [Ccw Reset] 1.0x [---O---]     |
| [ * CONVERGED (0.620s) ]                           [Compare] [Scenarios] [Attacks] [Logs] [Export]   |
+------------------------------------------------------------------------------------------------------+
```

### 1. Playback Instruments
* **Run / Pause (`handleTogglePlay`)**:
  Toggles the simulation clock. In Pause mode, `simTime` stops advancing, packet couriers freeze in mid-flight on the canvas, and protocol timers pause.
* **Step Forward (`handleStep`)**:
  Advances simulation time by an incremental delta (e.g., $+0.1\text{s}$). Allows step-by-step observation of routing exchanges.
* **Reset (`handleReset`)**:
  Restores `simTime = 0.0s`, clears active packet couriers, flushes event logs, resets telemetry counters (`tx = 0, rx = 0`), and recalculates baseline routing tables.
* **Speed Slider (`0.2x` to `4.0x`)**:
  Controls the time multiplier. Modifies both the simulation clock rate and the canvas animation velocity:
  ```typescript
  const simDelta = dt * speed;
  setSimTime((t) => t + simDelta);
  ```

### 2. The CONVERGED Indicator
In the top instrument bar, a parchment seal displays:
* **`CONVERGED (0.620s)`** in Verdigris Green when stable.
* **`ADAPTING (Flapping...)`** in Amber while routing tables are updating.

**Convergence Criteria (`backend/routelab/sim/engine.py:check_convergence()`)**:
A network is strictly defined as converged if and only if **both** of the following conditions are met:
1. **Empty In-Flight Queues**:
   Every `LinkEmulator` queue has zero packets currently in transit:
   $$\sum \text{link.in\_flight\_count}() == 0$$
2. **Quiescence Window Elapsed**:
   No router has updated any routing table entry (no flaps) for a duration $\ge \text{quiescence\_window\_s}$ (default $0.5\text{s}$):
   $$t_{\text{now}} - t_{\text{last\_mutation}} \ge \text{quiescence\_window\_s}$$

When both criteria pass, the engine freezes the convergence stopwatch, plays an audio chime, and records the total message count and flap count in the `ConvergenceRecord`.

### 3. Timeline Scrubber (`frontend/src/components/TimelineScrubber.tsx`)
Located at the bottom of the screen:
* Displays current simulation time: `currentTime / maxTime` (e.g., `4.25s / 10.0s`).
* **Event Markers Overlay**: Vertical color-coded tick marks indicate key events:
  - **Red markers**: Link failure or attack injection.
  - **Green markers**: Network convergence achieved.
  - **Brass markers**: Link cost changes.
* Users can drag the scrubber slider or click "Step Back / Step Forward" ($0.5\text{s}$) to inspect historical network states.

### 4. Golden Quill Path Tracer (`frontend/src/components/PathTracerPanel.tsx`)
The Path Tracer tests end-to-end routing reachability across the network:
* **Interactive Source & Destination Selectors**:
  Allows selecting any source (e.g., `R1`) and destination (e.g., `R6`).
* **Hop-by-Hop Trace Algorithm (`computePath`)**:
  ```typescript
  const computePath = (src: string, dst: string) => {
    const visited = new Set<string>();
    const path = [src];
    let curr = src;
    while (curr !== dst) {
      visited.add(curr);
      const entry = allRoutes[curr]?.find((r) => r.destination === dst);
      if (!entry || !entry.next_hop) return { path, isBlackhole: true };
      const next = entry.next_hop;
      if (visited.has(next)) {
        path.push(next);
        return { path, hasLoop: true }; // Loop detected!
      }
      path.push(next);
      curr = next;
    }
    return { path, hasLoop: false, isBlackhole: false };
  };
  ```
* **Visual Highlighting on Canvas**:
  - **Normal Optimal Path**: Traversed links illuminate in glowing golden amber with a subtle canvas blur: `R1 -> R2 -> R3 -> R5 -> R6`.
  - **Loop Detected**: If a loop forms (e.g., during count-to-infinity: `R1 -> R2 -> R1`), the path turns crimson red with a flashing warning halo on the looping routers.
  - **Blackhole**: If a router drops traffic because it lacks a valid next-hop, an amber blackhole alert appears.

---

## 8. Implementation Architecture

RouteLab connects its frontend and backend across a decoupled, asynchronous architecture:

```
+--------------------------------------------------------------------------------+
|                         BROWSER CLIENT (React 19 + TypeScript)                 |
|                                                                                |
|  +--------------------+  +----------------------+  +------------------------+  |
|  |   TopologyCanvas   |  | NodeInspectorDrawer  |  |  PathTracerPanel       |  |
|  | (HTML5 Canvas 2D)  |  | (Routes/Flaps/LSDB)  |  |  (Hop-by-Hop Tracer)   |  |
|  +--------------------+  +----------------------+  +------------------------+  |
|           ^                         ^                          ^               |
|           |                         |                          |               |
|           +-------------------------+--------------------------+               |
|                                     |                                          |
|                          App.tsx Main Tick Loop (60 FPS)                       |
|                 [Embedded Client Engine / Fallback Topologies]                 |
+--------------------------------------------------------------------------------+
             |                                              ^
             | REST API Requests                            | WebSocket Deltas
             | (GET/POST /api/v1/...)                       | (/ws/simulation)
             v                                              |
+--------------------------------------------------------------------------------+
|                           PYTHON BACKEND (FastAPI + Asyncio)                   |
|                                                                                |
|  FastAPI Application (server.py)                                               |
|  ├── routes_simulation.py (Start, Pause, Step, Compare)                        |
|  ├── routes_topologies.py (Generate, Import, Export GraphML)                   |
|  ├── routes_plugins.py    (Protocol Registration & Schema Validation)          |
|  └── routes_ws.py         (WebSocket Event Broadcaster & Command Ingestion)    |
|                                                                                |
|  SimulationEngine (backend/routelab/sim/engine.py)                             |
|  ├── Dual Clock: RealtimeClock (Monotonic) / VirtualClock (Deterministic Heap) |
|  ├── Append-Only EventStore (High-Resolution Audit Log)                        |
|  ├── Convergence Detector (In-Flight Queue Counter + Quiescence Window)       |
|  └── LinkEmulator Pipeline (Latency, Jitter, Loss, Bandwidth Heap)             |
|                                                                                |
|  RouterNode Pool (backend/routelab/core/node.py)                               |
|  ├── Ephemeral UDP Sockets (127.0.0.1:port via asyncio.DatagramTransport)      |
|  ├── IsolatedProtocolRunner (Plugin Sandboxing & Fault Interception)           |
|  └── Active Routing Protocols:                                                 |
|      ├── DistanceVectorProtocol (Bellman-Ford, Split Horizon, Poison Reverse)  |
|      ├── LinkStateProtocol      (LSA Flooding, LSDB, Dijkstra SPF)             |
|      ├── BGPLiteProtocol        (Path Vector, AS_PATH Rejection, Local Pref)   |
|      ├── FloodingProtocol       (Sequence Cache, TTL Decrement)                |
|      └── Security Modules       (Poisoning Attack & Secure DV Defense)         |
+--------------------------------------------------------------------------------+
```

### Component Roles & Communication Flow
1. **Frontend (`frontend/src/`)**:
   - Built with React 19, TypeScript, and Vite.
   - Canvas visualization does not rely on third-party heavy charting libraries; it uses a high-performance custom HTML5 Canvas 2D context capable of rendering 100+ nodes and packet couriers at 60 FPS.
   - Dual-mode operation:
     - **Connected Mode**: Streams state deltas from FastAPI via WebSocket (`/ws/simulation`).
     - **Offline / Standalone Mode**: Uses internal graph algorithms in `App.tsx` and `api.ts` to run full interactive simulations directly in the browser.
2. **REST API (`backend/routelab/api/routes_*.py`)**:
   - `/api/v1/simulation/start`: Boots a new simulation session with a given topology and protocol.
   - `/api/v1/simulation/step`: Advances the simulation clock deterministically.
   - `/api/v1/simulation/compare`: Executes automated head-to-head benchmarks comparing Distance Vector and Link State on identical topologies.
   - `/api/v1/topologies`: Lists, creates, and exports topologies in JSON and GraphML formats.
3. **WebSockets (`backend/routelab/api/routes_ws.py`)**:
   - Full-duplex connection at `/ws/simulation`.
   - Backend pushes state deltas (link cuts, node flaps, packet hops, convergence events) to the UI at ~50 FPS.
   - Client sends commands (`step`, `inject_event`, `ping`) over the socket.
4. **Engine & Protocols (`backend/routelab/sim/`, `backend/routelab/protocols/`)**:
   - Orchestrates time, link delivery queues, and node lifecycle.
   - Protocols are strictly decoupled from the engine; they communicate exclusively through the `ProtocolContext` interface (`ctx.send`, `ctx.broadcast`, `ctx.set_timer`).

---

## 9. Viva / Presentation Quick Reference Cheatsheet

Use these concise summary points when answering questions during a viva or presentation:

1. **What is the primary difference between Distance Vector and Link State in RouteLab?**
   * *Answer*: Distance Vector routers share **calculated distances to all destinations** only with immediate neighbors ("routing by rumor"). Link State routers share **local link connectivity states** with the entire network via LSA flooding, building an identical topology map (LSDB) on every router, and then running Dijkstra's algorithm independently.
2. **How does RouteLab handle Count-to-Infinity?**
   * *Answer*: In Distance Vector, if a link breaks and split-horizon is disabled, two neighbors can iteratively bounce incrementing metrics between each other. RouteLab demonstrates this in Course Scenario 3, where metrics count up to 16 ($\infty$). RouteLab solves this using **Split Horizon** (not advertising learned routes back to the source) and **Poison Reverse** (advertising metric 16 back to the next-hop).
3. **Are the routers actual VMs or containers?**
   * *Answer*: No. They are asynchronous Python `RouterNode` software objects running inside Python's asyncio runtime. However, they use **real OS UDP sockets** on `127.0.0.1` and serialize binary packets using **MessagePack**, while physical wires are simulated via `LinkEmulator` priority queues.
4. **How is Convergence defined in RouteLab?**
   * *Answer*: Convergence requires two conditions: (1) all `LinkEmulator` in-flight packet queues must be completely empty ($0$ packets in transit), and (2) no routing table changes (flaps) have occurred for at least the `quiescence_window_s` (default $0.5\text{s}$).
5. **How does BGP prevent routing loops?**
   * *Answer*: BGP is a path-vector protocol. Every route advertisement carries an explicit list of Autonomous Systems it has traversed (`AS_PATH`). If a router sees its own Autonomous System ID inside the `AS_PATH` of an incoming advertisement, it immediately discards the packet, preventing inter-domain loops.
6. **What is a "Route Flap"?**
   * *Answer*: A route flap is any mutation in a routing table entry — specifically when a destination's next-hop changes, its metric increases or decreases, or the route is dropped. RouteLab tracks this monotonically using hashes of `(destination, next_hop, cost)`.
7. **What is Path Stretch?**
   * *Answer*: Path stretch is the ratio of the actual routed path cost to the theoretical shortest path cost computed by an oracle (NetworkX). A stretch factor of $1.0$ indicates perfect optimal routing.

---
*End of RouteLab Technical Guide.*
