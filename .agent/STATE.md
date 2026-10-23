# RouteLab — Agent Execution State

## Project Overview
- **Project**: RouteLab — Distance Vector, Link State & BGP: A Comparative Routing Simulator (Team 20)
- **Repository**: `https://github.com/nani224/routing-simulator`
- **Stack**: Python 3.11+ (real sockets + asyncio, msgpack), React + TypeScript + Vite (Canvas 2D/WebGL, Cartographer's Atlas design system)

## Phase Checklist
- [x] **P1: Repo, tooling, CI, core, plugin ABC + loader, topology loader/generators**
  - [x] Git branches (`main`, `dev`, `feature/p1-core`), `.pre-commit-config.yaml`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`
  - [x] Core: node, link emulator (priority queue / heap delay, jitter, loss, bandwidth, cost), real & virtual clocks
  - [x] Event store (append-only log, binary/msgpack serialized, scrubbing & replay ready)
  - [x] Plugin system: `RoutingProtocol` ABC, context isolation, watchdog, exception isolation, dynamic loader
  - [x] Topology: models, loader (JSON/GraphML), generators (ring, grid, tree, random geometric, scale-free)
  - [x] P1 Unit & integration tests, type-check (`mypy --strict`), lint (`ruff`), 100% pass (36 tests, 89% coverage)
- [ ] **P2: DV plugin, metrics, failure injection, convergence detector, oracle + property tests**
  - [ ] DV plugin (`dv.py`) with configurable split-horizon, poison-reverse, triggered updates, hold-down timer
  - [ ] Convergence detector: table stability quiescence window + zero in-flight messages
  - [ ] Failure injection: link down/up, cost change, node crash/recover
  - [ ] Metrics engine: convergence time, message/byte count, route flaps, transient loops/blackholes
  - [ ] Correctness oracle using NetworkX shortest paths
  - [ ] Hypothesis property-based tests over random topologies & failure sequences
- [ ] **P3: LS plugin, compare engine, deterministic runs, benchmarks & perf pass 1**
  - [ ] LS plugin (`ls.py`): LSA flooding, sequence numbers, age, link-state database (LSDB), Dijkstra (heapq)
  - [ ] Compare engine: parallel deterministic runs with identical seed, topology, and event schedule
  - [ ] Flooding baseline plugin (`flooding.py`)
  - [ ] Benchmarks suite: convergence time, message overhead, memory, event throughput
  - [ ] Performance pass 1: hot path verification, memory footprint, docs/results/perf.md
- [ ] **P4: Scenarios, count-to-infinity + fix, poisoning attack + mitigation, BGP-lite**
  - [ ] Count-to-infinity scenario reproduction & split-horizon/poison-reverse fix verification
  - [ ] Routing-table poisoning attack plugin & mitigation (validation/filtering)
  - [ ] BGP-lite plugin (`bgp_lite.py`): path vector, AS_PATH loop prevention, local-pref policy selection
  - [ ] Built-in scenarios (JSON/YAML) for 6/8/10 node topologies
- [ ] **P5: FastAPI & WebSocket streaming, delta updates, replay/export, perf pass 2**
  - [ ] FastAPI REST API: topology CRUD, plugin upload/inspect, scenario execution, metrics export
  - [ ] WebSocket streaming: 30-60 FPS batching, delta-only updates, backpressure drop/coalescing
  - [ ] Export engine: CSV, JSON, run replay file
  - [ ] 30-minute soak test validation script
- [ ] **P6: Frontend (Cartographer's Atlas aesthetic, Canvas 60 FPS, 13 features)**
  - [ ] Design system tokens: warm paper/parchment light theme, deep charcoal-brown dark theme, typography (Cinzel / Outfit / JetBrains Mono)
  - [ ] Feature 1-13 implementation:
    - 1. Topology Canvas (drag, zoom/pan, auto-layout, minimap, severed road visuals)
    - 2. Live packet courier animations
    - 3. Per-node inspector (routes, LSDB/RIB, counters)
    - 4. Interactive failure/attack tools
    - 5. Timeline scrubber & replay
    - 6. Side-by-side compare view
    - 7. Path tracer & loop/blackhole indicator
    - 8. Plugin management & dynamic config forms
    - 9. Scenario builder & preset runner
    - 10. Virtualized packet log
    - 11. PDF/CSV/JSON/Image export
    - 12. Explain mode & one-click demo
    - 13. Settings panel
  - [ ] Performance verification: 100 nodes @ 60 FPS, Lighthouse >= 90
- [ ] **P7: Documentation, UML, test tables, verified benchmark results**
  - [ ] README.md with screenshots & architecture overview
  - [ ] `docs/architecture.md`, `docs/plugin-guide.md`
  - [ ] UML diagrams (Mermaid): Use Case, Class, Sequence in `docs/uml/`
  - [ ] Verified benchmark reports in `docs/results/`
  - [ ] Demo script for viva presentation
- [ ] **P8: Final audit loop, clean clone verification, v1.0.0 release**
  - [ ] Fresh-clone verification test
  - [ ] Tag v1.0.0 pushed

## Current Task
- **Phase**: P2 Distance Vector, Metrics, Oracle & Property Tests
- **Task**: Implement `backend/routelab/protocols/dv.py` (Distance Vector / RIP-like with split-horizon, poison-reverse, triggered updates, hold-down) and `backend/routelab/metrics/collector.py` & oracle.

## Decisions Made
- Architecture: Core simulator separates physical time (asyncio) from virtual clock for deterministic bit-for-bit replay.
- Network transport: Real UDP localhost sockets per router for true networking semantics + link emulator layer for delay/jitter/loss/bandwidth.
- Serialization: Msgpack for high-performance compact binary wire protocol with exact byte counting.
- Design theme: "Cartographer's Atlas / Drafting Table" with warm linen/parchment surface, ink lines, severed-road broken link visuals, courier packet markers.
- P1 Gate: 36 unit tests passed, mypy --strict green with zero issues in 17 source files, ruff lint and format passed with 0 errors, core coverage at 89%.

## Known Issues
- None. All P1 gates green.

## Next Action
- Implement `backend/routelab/protocols/dv.py` and write property tests with NetworkX oracle in `backend/tests/unit/test_dv_oracle.py`.
