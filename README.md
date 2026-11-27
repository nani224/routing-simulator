# PHANTOMNET — Steganographic Adversarial Tunnel & Traffic Masking Network

[![CI](https://github.com/nani224/routing-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/nani224/routing-simulator/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen.svg)](htmlcov/index.html)
[![Type-Check](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Code-Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**PHANTOMNET** is an adversarial encrypted tunnel, steganographic traffic masking engine, and defense research platform. It couples a real user-space Noise-authenticated transport tunnel with an event-driven telemetry spine, a 60 FPS WebGL visualization observatory, and an empirical machine-learning traffic morphing engine evaluated against state-of-the-art Random Forest deep packet inspection (DPI) classifiers.

---

## 🏛️ System Architecture

```
                                      [ SOCKS5 Front-Door ] (RFC 1928)
                                               │
                                               ▼
                              ┌──────────────────────────────────┐
                              │    PHANTOMNET User-Space Tunnel   │
                              │   - Noise XX Mutual Handshake    │
                              │   - ChaCha20-Poly1305 AEAD       │
                              │   - RFC 6479 Anti-Replay Window  │
                              └────────────────┬─────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
        ┌─────────────────────────────┐                 ┌─────────────────────────────┐
        │   Egress Traffic Morphing   │                 │     Unified Event Spine     │
        │ - Target TLS 1.3 sampling   │                 │ - Typed events: HANDSHAKE,  │
        │ - CMA-ES distribution tuner │                 │   PKT_TX, CENSOR_SCORE...   │
        │ - Dynamic dummy injection   │                 │ - JSONL & MsgPack streams   │
        └──────────────┬──────────────┘                 └──────────────┬──────────────┘
                       │                                               │
                       ▼                                               ▼
        ┌─────────────────────────────┐                 ┌─────────────────────────────┐
        │   Adversarial DPI Censor    │                 │     Phantom Observatory     │
        │ - 42-D statistical features │                 │ - 60 FPS PixiJS WebGL       │
        │ - 60-site TLS 1.3 baseline  │                 │ - Physical Conduit & Pipe   │
        │ - Adaptive retraining loop  │                 │ - Real-time Fingerprint Bar │
        └─────────────────────────────┘                 └─────────────────────────────┘
```

---

## 🔬 Quality Gates & Verification Matrix

PHANTOMNET enforces zero tolerance for flaky tests, untyped interfaces, or unbacked marketing claims:

| Quality Gate | Requirement | Measured Value | Status |
|---|---|---|---|
| **Linter & Code Style** | `ruff check .` | 0 errors across entire codebase | **PASS** |
| **Code Formatting** | `ruff format --check .` | 100% compliant across all files | **PASS** |
| **Strict Type Safety** | `mypy --strict` | 0 errors across 68 modules | **PASS** |
| **Test Suite** | Unit, property, fuzz, chaos | 125 passed, 0 failed | **PASS** |
| **Frame Header Fuzzing** | Hypothesis frame fuzzer | 10,000 cases without crash/hang | **PASS** |
| **Anti-Replay Window** | RFC 6479 / RFC 4303 | 100% duplicate & stale frame rejection | **PASS** |
| **1-Bit Tamper Test** | ChaCha20-Poly1305 MAC | 100% corrupted frame rejection | **PASS** |
| **UI Performance** | PixiJS v8 WebGL Canvas | 59.9 FPS median under 5,000 sprites | **PASS** |
| **Event Determinism** | SHA-256 match over 3 seeds | `faf31568753c5549...` (100% bit-for-bit) | **PASS** |

---

## ⚡ The Phantom Observatory UI

Unlike generic SaaS dashboards, the **Phantom Observatory** draws solely from verified backend telemetry emitted through the typed event spine (`/ws/events` and `/api/replay/{run_id}`):

1. **The Conduit:** Real physical pipe modeling packet transmission between local client and remote proxy. Each packet is rendered as an object whose length reflects packet size, textured with opaque ciphertext glyphs. Link packet loss is visualized as shattering fragments; reconnect events render as pipe re-welding.
2. **Handshake Ritual:** Visualizes the Noise XX ephemeral Diffie-Hellman key exchange step-by-step, terminating in key confirmation, session ID lock-in, and rolling monotonic ratchet rekeys.
3. **The Fingerprint Strip:** A real-time scrolling barcode of packet sizes and inter-arrival gaps. Compares the raw, unshaped tunnel signature against the post-morphing signature, exposing the exact statistical features visible to DPI censors.
4. **Lens Switcher:** Instantly toggle between Observatory lenses: Protocol Flow, Censor Heatmap, Topologies, and Performance Telemetry.

---

## 📊 Scientific Arms Race Evaluation & Evasion Findings

Traffic morphing and censor evasion were evaluated under an audited, threshold-free protocol over 2,400 genuine network flows captured across **60 locally served site profiles** in 5 categories (video, tech, news, shopping, collab), partitioned into disjoint site splits (40 train, 10 validation, 10 held-out test sites).

### Threshold-Free Evasion Across 10 Independent Seeds

| Regime | Static Censor AUC (95% CI) | Static TPR @ 1% FPR | Retrained Censor AUC | Retrained TPR @ 1% FPR | Bandwidth Overhead | Latency Penalty |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **No Shaping** | `1.0000` [1.0000, 1.0000] | `1.0000` | `1.0000` [1.0000, 1.0000] | `1.0000` | **0.00%** | `0.145 ms` |
| **Random Shaping** | `1.0000` [1.0000, 1.0000] | `1.0000` | `1.0000` [1.0000, 1.0000] | `1.0000` | **52.99%** | `9.256 ms` |
| **Fixed Padding** | `1.0000` [1.0000, 1.0000] | `1.0000` | `1.0000` [1.0000, 1.0000] | `1.0000` | **195.05%** | `0.145 ms` |
| **Learned Morphing** | `0.9981` [0.9921, 1.0000] | `0.9950` | `1.0000` [1.0000, 1.0000] | `1.0000` | **63.71%** | `3.798 ms` |

### Key Scientific Findings:
- **Directional Invariance:** Under directional features alone, the censor drops to chance (`AUC = 0.5213`), proving packet directions do not leak tunnel identity.
- **Root-Cause Asymmetry:** Discrimination stems from transport-layer record chunking differences (Python SSL buffering vs user-space socket framing) producing divergent moments (`tx_mean`, `tx_std`, `tx_size_bin_0`).
- **The Arms Race Reality:** Against a frozen **Static Censor**, continuous CMA-ES distribution morphing achieves modest separation reduction (`AUC = 0.9981`, `TPR@1% = 0.9950`). However, when the adversary **retrains on shaped traffic**, the censor recovers full detection (`AUC = 1.0000`). Static feature morphing provides transient evasion against static models, but does not survive adversarial retraining.

Full data audits, Kolmogorov-Smirnov divergence analyses, and bootstrap CI validation scripts are committed in [`evidence/REPORT.md`](evidence/REPORT.md) and [`evidence/ml/ROOT_CAUSE.md`](evidence/ml/ROOT_CAUSE.md).

---

## 🛠️ Quickstart & Reproduction

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Git

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/nani224/routing-simulator.git
cd routing-simulator

# Set up Python virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install -e .[dev]

# Install frontend dependencies
cd frontend
npm ci
cd ..
```

### 2. Run Verification Suite

```bash
# Run strict linter and style check
ruff check .
ruff format --check .

# Run strict type checking
mypy --strict backend/routelab backend/phantomnet

# Run full test suite (125 tests)
pytest backend/tests/

# Verify evidence report consistency & guard rails
pytest backend/tests/phantomnet/test_no_unsupported_evasion_claims.py
pytest backend/tests/phantomnet/test_report_consistency.py
```

### 3. Launch the Live System

**Terminal 1 — Backend API & Event Spine:**
```bash
python -m uvicorn routelab.api.server:app --host 127.0.0.1 --port 8000 --app-dir backend
```

**Terminal 2 — Frontend Observatory (Vite):**
```bash
cd frontend
npm run dev
```

Open your browser at `http://localhost:5173` to explore the **Phantom Observatory**.

---

## 🧭 Comparative Routing Simulation (RouteLab Substrate)

PHANTOMNET incorporates **RouteLab** as an underlying distributed routing engine:
- Pluggable routing protocols: Distance Vector (Bellman-Ford), Link State (Dijkstra), BGP-Lite, and Poisoning Attacks.
- Deterministic virtual clock vs wall-clock execution.
- Emulated network link queues with jitter, latency, asymmetric costs, and real UDP socket bindings on localhost.

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
