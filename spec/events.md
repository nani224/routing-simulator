# PHANTOMNET Event Spine Specification

Version: `1.0.0`
Status: `STABLE`

The **Event Spine** is the single source of truth for PHANTOMNET. Every backend subsystem—including the real socket tunnel, the RouteLab discrete-event simulator, adversarial ML agents, on-path censors, and replay engines—emits typed events adhering to this specification.

The UI ("Phantom Observatory") renders **only** events received across this spine. No visual state or fake animation is generated without a corresponding event.

---

## 1. Event Kinds

The spine defines 13 canonical event kinds across 6 subsystem domains:

| Kind | Subsystem | Description |
| :--- | :--- | :--- |
| `HANDSHAKE_MSG` | Tunnel / Crypto | Discrete Noise protocol handshake message exchange (e.g. DH mixing, ephemeral keys). |
| `CONN_STATE` | Tunnel / Session | Connection state machine transitions (`CONNECTING`, `ESTABLISHED`, `BLOCKED`, etc.). |
| `PKT_TX` | Tunnel / Transport | Outbound packet transmission with explicit byte size and timing. |
| `PKT_RX` | Tunnel / Transport | Inbound packet reception with explicit byte size and timing. |
| `PKT_DROP` | Hostile Network / Censor | Dropped packet event due to censorship, link impairment, or buffer overflow. |
| `REKEY` | Tunnel / Crypto | Session key rollover / rekey handshake (replayed in miniature). |
| `CENSOR_SCORE` | Censor Lab | Continuous inspection score and confidence emitted by on-path classifiers. |
| `CENSOR_ACTION` | Censor Lab | Discrete enforcement action taken by censor (`ALLOW`, `THROTTLE`, `BLOCK`). |
| `MASK_SWITCH` | Defender / Shaping | Transition from one traffic morphing profile to another. |
| `POLICY_DECISION` | Defender / ML | Decision ticker reasoning, explored candidates, and overhead penalty evaluation. |
| `ROUTE_CHANGE` | RouteLab / Mesh | RouteLab topology perturbation, link failure, or reroute against oracle shortest path. |
| `TRAIN_ROUND` | ML / Adversarial | Adversarial co-training round stats (censor accuracy vs defender stealth/Pareto frontier). |
| `BENCH_MARK` | Evidence / Benchmarks | Measured performance metric record (throughput, RTT, overhead, AUC). |

---

## 2. Canonical Schema Fields

Each event record contains the following fields:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `version` | `int` | Yes | Schema version integer (currently `1`). |
| `seq` | `int` | Yes | Monotonically increasing sequence number (1-based per run). |
| `t` | `float` | Yes | High-resolution timestamp in seconds (simulation clock or epoch seconds). |
| `kind` | `EventKind` | Yes | One of the 13 canonical event kind strings. |
| `flow_id` | `str \| null` | No | Flow identifier (e.g. `flow-01`, `client:49152->server:443`). |
| `src` | `str \| null` | No | Source node or socket address (`127.0.0.1:49152`, `client`, `node-1`). |
| `dst` | `str \| null` | No | Destination node or socket address (`127.0.0.1:8443`, `server`, `node-4`). |
| `size` | `int \| null` | No | Packet length in bytes (length-proportional conduit rendering & barcode strip). |
| `dir` | `str \| null` | No | Direction flag (`TX` for outbound, `RX` for inbound). |
| `state` | `str \| null` | No | Connection or censor state string. |
| `mask_id` | `str \| null` | No | Active mask profile identifier (e.g. `plain`, `burst_pad_v1`, `tls_mimic`). |
| `meta` | `dict` | Yes | Key-value dictionary containing kind-specific telemetry metadata. |

---

## 3. Wire Formats & Streaming Protocols

### 3.1 Binary Msgpack Format (Live WebSocket `/ws/events`)
For live transmission over WebSocket connections:
- Frames are serialized as binary MessagePack (`application/msgpack`).
- Batched at **60 Hz** (~16.6 ms per frame) to prevent UI thread lock and excessive WebSocket frame overhead.
- Batched frame container structure:
  ```json
  {
    "type": "event_batch",
    "batch_seq": 420,
    "timestamp": 12.456789,
    "events": [
      {
        "version": 1,
        "seq": 1001,
        "t": 12.450123,
        "kind": "PKT_TX",
        "flow_id": "flow-01",
        "src": "client",
        "dst": "server",
        "size": 1420,
        "dir": "TX",
        "state": null,
        "mask_id": "plain",
        "meta": {"proto": "ChaCha20-Poly1305"}
      }
    ]
  }
  ```

### 3.2 JSONL Persistence (Storage & Audit)
For human-readable offline logs and differential verification:
- UTF-8 newline-delimited JSON (`.jsonl`).
- Exactly one canonical event per line.

### 3.3 Replay API (`/api/replay/{run_id}`)
- Query parameters:
  - `start_t` (float, default 0.0): Starting simulation timestamp.
  - `end_t` (float, optional): Ending simulation timestamp.
  - `kinds` (list of str, optional): Filter by event kinds.
  - `since_seq` (int, default 0): Incremental sequence polling.
- Responds with `application/msgpack` (or `application/json` when requested via HTTP `Accept` header).
- Includes the overall run cryptographic SHA-256 hash in header `X-Run-Hash`.

---

## 4. Determinism Guarantee

Every experiment and synthetic episode is parameterized by an integer `seed`.
- The event generator and simulation engine are strictly deterministic.
- Given identical inputs and seed, the sequence of emitted events and their serialized representations are byte-for-byte identical.
- The Event Bus computes an incremental SHA-256 digest across all serialized events:
  $$\text{Hash}_{\text{run}} = \text{SHA256}(\text{event}_1 \parallel \text{event}_2 \parallel \dots \parallel \text{event}_N)$$
- Property and regression tests enforce:
  $$\text{Hash}_{\text{run}}(S) = \text{Hash}_{\text{run}}(S)$$

