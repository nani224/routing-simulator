# ADR 0001: Event Bus Design and RouteLab EventStore Reuse

## Status
**Accepted**

## Context
PHANTOMNET requires a unified, high-throughput Event Spine that serves as the single source of truth across all subsystems: the real local socket tunnel, on-path censors, RouteLab topology simulations, adversarial ML agents, and the WebGL "Phantom Observatory" UI.

Key architectural requirements include:
1. In-process asynchronous Pub/Sub for real-time WebSocket streaming.
2. An append-only log with bounded memory capabilities for long-running soak executions.
3. Cryptographic per-run SHA-256 hashing to enforce strict determinism guarantees across runs with identical seeds.
4. Export and import of event episodes in both MessagePack (binary, wire-efficient) and JSONL (human-readable, audit-friendly).
5. Fast temporal range slicing (`get_range`) and incremental sequence fetching (`get_since_seq`) for the Time Machine replay UI.

RouteLab already implements an `EventStore` (`routelab.core.events.EventStore`) providing sequence indexing, time-range querying, and memory-safe sliding window pruning.

## Decision
We build `PhantomEventBus` (`backend/phantomnet/bus.py`) by composing RouteLab's core `EventStore` primitives and extending them with:
1. **Strongly-typed validation:** Native support for `PhantomEvent` models with strict field validation and forward-compatible schema versioning.
2. **Incremental SHA-256 hashing:** An in-flight digest updating with every canonical event serialized byte sequence, yielding a deterministic `run_hash`.
3. **Async Pub/Sub channels:** Registration of `asyncio.Queue` subscribers for decoupled, non-blocking broadcast to WebSocket streams and recording agents.
4. **Bidirectional export/import:** Native methods for streaming and persisting full event runs to `.jsonl` and `.msgpack`.
5. **Replay Time Machine:** High-resolution temporal replay APIs supporting variable playback speed factors (0.1x to 5.0x).

## Consequences
- **Positive:** Maximum code reuse of tested range-query and sliding-window logic without reinventing basic indexing.
- **Positive:** Strict separation between RouteLab's internal simulation events and PHANTOMNET's 13 canonical spine event kinds.
- **Positive:** Enables identical replay behavior whether events originate from live sockets, RouteLab, or synthetic traces.

