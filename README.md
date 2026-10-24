# RouteLab — Distance Vector, Link State & BGP: A Comparative Routing Simulator

[![CI](https://github.com/nani224/routing-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/nani224/routing-simulator/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen.svg)](htmlcov/index.html)
[![Type-Check](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Code-Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Course Project (Team 20)**: Distance Vector, Link State & BGP: A Comparative Routing Simulator  
**Team Members**: Aakarsh, Sravan, Sneha  
**Design Theme**: Cartographer's Atlas / Drafting Table (Antique Parchment & Nautical Blueprint)

---

## 🗺️ Project Overview

**RouteLab** is a complete, production-grade, real-time, pluggable routing protocol simulator built from scratch for comparative evaluation of distributed networking algorithms.

Unlike legacy educational simulators, RouteLab enforces **zero protocol hardcoding**:
- The core simulation engine, event store, metrics collector, REST API, and canvas visualizer contain no protocol-specific logic.
- Distance Vector (Bellman-Ford / RIP), Link State (Dijkstra / OSPF), BGP-Lite, Flooding, and Adversarial Poisoning protocols are pluggable modules implementing the `RoutingProtocol` abstract base class.
- Router nodes execute on **real UDP sockets bound to localhost**, linked via logical **`LinkEmulator`** queues modeling latency, jitter, packet loss, bandwidth serialization, and asymmetric costs.
- The system features **dual clocks**: a wall-clock `RealtimeClock` for interactive visualization, and a deterministic `VirtualClock` for bit-for-bit reproducible unit tests and benchmarks.

---

## 🎨 Visual Design — Cartographer's Atlas / Drafting Table

RouteLab features a distinctive, human-crafted aesthetic inspired by antique cartography and nautical drafting:
- **Light Theme (Antique Parchment)**: Warm paper canvas (`#F5F2EB`), hand-drawn dark ink lines, topographic contour rings, brass compass accents, and compass rose watermarks.
- **Dark Theme (Nautical Blueprint)**: Deep slate-navy (`#0D1B2A`), chalk-white architectural grid, cyanotype accents, and warm amber sextant needles.
- **60 FPS Canvas Engine**: High-performance HTML5 Canvas 2D engine handling 100+ nodes and hundreds of traveling packet couriers smoothly.

---

## 🚀 Key Features

1. **Topology Canvas**: Interactive pan/zoom, draggable nodes, toggleable force-directed spring physics, minimap, severed link indicators, and metric cost badges.
2. **Live Packet Courier Animations**: Real-time particles traveling along link vectors color-coded by protocol (DV terracotta, LS verdigris, BGP cobalt, Flooding amber, Attack ruby).
3. **Per-Node Inspector**: Slide-out drawer with routing tables, Link State Database (LSDB), BGP RIB/AS_PATH, neighbor link metrics, and crash/recover controls.
4. **Interactive Failure & Attack Lab**: Dynamically sever/recover links, mutate link metric costs, inject forged route poisoning attacks, and activate cryptographic defense.
5. **Timeline Scrubber & Replay**: Scrub through simulation history at 50ms resolution with color-coded event pins.
6. **Side-by-Side Algorithm Comparison**: Run Distance Vector vs Link State vs Flooding on identical topologies and event schedules with live speedup, message, byte, and flap deltas.
7. **Golden Quill Path Tracer**: Visual hop-by-hop route tracing with automated routing loop and blackhole alarms.
8. **Pluggable Protocol Architecture**: Load custom `.py` protocol plugins dynamically into an isolated, exception-safe sandbox.
9. **Scenario Builder & Presets**: 1-click launch for all mandatory course scenarios (6/8/10 node topologies, count-to-infinity flaw, poison-reverse fix, BGP peering, poisoning attack).
10. **Virtualized Packet Log**: High-volume, filterable streaming table of every simulation event with auto-scroll.
11. **Comprehensive Export**: Export high-res PNG map snapshots, CSV/JSON run metrics, GraphML topologies, and printable PDF evaluation reports.
12. **Explain Mode**: 5-step guided audio-visual walkthrough explaining Bellman-Ford, count-to-infinity, Dijkstra SPF, BGP path-vectors, and cybersecurity mitigations.
13. **Settings Station**: Calibrate quiescence windows, toggle deterministic VirtualClock vs RealtimeClock, and configure WebSocket endpoints.

---

## 📊 Course Scenario Benchmark Results

Benchmarks executed on identical seeds and event schedules across 6, 8, 10, 20, 50, and 100-node topologies (from `docs/results/perf.md`):

| Topology | Nodes | Links | Sim Conv Time | Control Messages | Control Bytes | Peak Memory | Events/sec |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Course 6-Node** | 6 | 8 | 0.20s | 66 | 8,712 B | 1.93 MB | 66.3 |
| **Course 8-Node Mesh** | 8 | 10 | 0.20s | 112 | 14,896 B | 2.45 MB | 45.2 |
| **Course 10-Node WAN** | 10 | 14 | 0.20s | 190 | 26,571 B | 3.04 MB | 25.5 |
| **ScaleFree-20** | 20 | 36 | 0.20s | 1,060 | 161,368 B | 6.58 MB | 3.6 |
| **ScaleFree-50** | 50 | 96 | 0.20s | 7,150 | 1,128,217 B | 18.79 MB | 0.3 |
| **ScaleFree-100** | 100 | 196 | 0.20s | 29,300 | 4,691,968 B | 48.47 MB | 0.04 |

### Comparative Finding: Distance Vector vs Link State
- **Link State (Dijkstra)** converges **3.4x faster** with 38% fewer total control messages than Distance Vector on the course 6-node network.
- **Count-to-Infinity Vulnerability**: When link $B-C$ breaks without split-horizon, DV bounces metrics up to 16 over multiple iterations. With **Split-Horizon + Poison-Reverse**, the loop is resolved in a single iteration.

---

## 🛠️ Quickstart Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Installation
```bash
# 1. Clone repository
git clone https://github.com/nani224/routing-simulator.git
cd routing-simulator

# 2. Set up Python virtual environment and backend dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running Backend & Frontend
```bash
# Terminal 1: Start FastAPI REST & WebSocket streaming server (Port 8000)
uvicorn routelab.api.server:create_app --factory --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Start Vite Frontend dev server (Port 5173 / 4173)
cd frontend
npm run dev
```
Open **`http://localhost:5173/`** in your browser.

---

## 🧪 Testing & Verification

RouteLab includes **62 automated tests** across unit, integration, benchmark, and Hypothesis property suites:

```bash
# Run complete test suite with coverage
pytest backend/tests/ -v --cov=routelab --cov-report=term-missing

# Run strict type checking (zero errors across 38 source files)
mypy --strict backend/routelab

# Run linter and formatting checks
ruff check backend/
ruff format --check backend/

# Build and verify frontend production bundle
cd frontend
npm run build
```

---

## 📁 Repository Architecture

```text
routing-simulator/
├── backend/
│   ├── routelab/
│   │   ├── api/             # FastAPI REST routes & WebSocket streaming manager
│   │   ├── attacks/         # Route poisoning adversary & secure DV mitigation
│   │   ├── core/            # Node, LinkEmulator, Packet, Clocks, EventStore
│   │   ├── metrics/         # Correctness oracle (NetworkX), RunMetrics collector
│   │   ├── plugins/         # RoutingProtocol ABC, ProtocolContext, IsolatedRunner
│   │   ├── protocols/       # Distance Vector, Link State, BGP-Lite, Flooding
│   │   ├── sim/             # SimulationEngine, ScenarioRunner, CompareEngine
│   │   └── topology/        # Topology models, JSON/GraphML loaders, generators
│   └── tests/
│       ├── bench/           # 100-node scale benchmarks
│       ├── integration/     # Memory soak tests & multi-cycle perturbation tests
│       └── unit/            # Protocol, oracle, attack, and API test suites
├── frontend/
│   ├── src/
│   │   ├── components/      # 13 Cartographer UI workbenches & modals
│   │   ├── services/        # REST & WebSocket API clients
│   │   ├── types.ts         # TypeScript schema definitions
│   │   ├── index.css        # OKLCH Cartographer's Atlas design tokens
│   │   └── App.tsx          # Application shell & live simulation stepper
│   └── index.html           # Google Fonts & SEO metadata
├── docs/
│   ├── architecture.md      # System architecture & deep-dive technical specs
│   ├── plugin-guide.md      # Custom routing protocol developer tutorial
│   ├── demo_script.md       # Live presentation & viva walkthrough guide
│   ├── results/perf.md      # Verified benchmark measurements
│   └── uml/                 # Mermaid Use Case, Class, and Sequence diagrams
├── examples/
│   ├── plugins/             # Sample custom routing algorithms
│   └── scenarios/           # 6 course scenario JSON definitions
├── pyproject.toml           # Backend packaging & test configurations
└── Makefile                 # Build, test, and run automation targets
```

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
