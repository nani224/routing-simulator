# PHANTOMNET State Tracker

## Current Phase: Phase 5 (Evidence, Hardening, and Demo Mode)
Status: COMPLETED (ALL 5 PHASES COMPLETE)

### Completed Tasks
- [x] Initialized branch `phantomnet`
- [x] Established `AGENTS.md` constitution and `.agent/STATE.md`
- [x] Created `/spec/events.md` defining the 13 canonical event kinds, schema fields, msgpack wire format, and determinism contract
- [x] Built Pydantic models in `backend/phantomnet/events.py` and code generator `scripts/generate_types.py` producing TypeScript interfaces in `frontend/src/types/events.ts` and `spec/events.d.ts`
- [x] Built `PhantomEventBus` (`backend/phantomnet/bus.py`) with async pub/sub, append-only sliding window log, running SHA-256 digest, JSONL & msgpack export/import, temporal range queries, and replay streaming
- [x] Authored ADR-0001 (`docs/adr/0001-event-bus-and-routelab-reuse.md`) documenting RouteLab `EventStore` reuse and extensions
- [x] Built FastAPI endpoints: live 60 Hz batched msgpack WebSocket `/ws/events` and replay endpoint `/api/replay/{run_id}` with headers `X-Run-Hash` and `X-Event-Count`
- [x] Built deterministic synthetic event generator (`backend/phantomnet/synthetic.py`) covering all 13 canonical event kinds
- [x] Authored unit tests, hypothesis property-based round-trip tests, determinism tests, and API integration tests in `backend/tests/phantomnet/`
- [x] Integrated `make verify` running `ruff check`, `ruff format --check`, `mypy --strict`, all unit/property/determinism tests, and `npm run build`
- [x] Updated CI workflow (`.github/workflows/ci.yml`) to run `make verify` on `phantomnet` pushes
- [x] Implemented anti-replay sliding window RFC 6479 / RFC 4303 in `backend/phantomnet/tunnel/replay_window.py`
- [x] Implemented binary framing with length-prefix and stream reader in `backend/phantomnet/tunnel/framing.py`
- [x] Implemented Noise Protocol Framework (Noise XX with ChaCha20-Poly1305 and BLAKE2s) and monotonic nonce rekeying in `backend/phantomnet/tunnel/crypto.py`
- [x] Implemented metadata-only Censor interface, Rule-based censor, Trained Classifier censor slot, and Adaptive censor with online sensitivity multiplier and dynamic retraining rounds in `backend/phantomnet/censor/interface.py` and `censors.py`
- [x] Implemented on-path `CensorProxy` with token-bucket throttle, link emulation (latency, jitter, loss), and typed event emission
- [x] Implemented `TunnelServer` and `TunnelClient` over real sockets with automatic reconnects and rekeying
- [x] Implemented RFC 1928 `Socks5Server` front door routing browser traffic through the tunnel
- [x] Authored comprehensive Phase 2 test suite: `test_crypto.py` (vectors, 1-bit tamper reject, replay reject, nonce uniqueness), `test_fuzzing.py` (10,000 Hypothesis cases without crash/hang), `test_censor.py`, `test_tunnel.py` (20 forced drops in a row reconnect, SOCKS5 browser fetch, censor blocking unshaped flow), and `test_bench.py`
- [x] Generated Phase 2 baseline benchmark evidence at `/evidence/bench/tunnel.json`
- [x] Installed and configured PixiJS v8 (`pixi.js@^8.22.0`), `@msgpack/msgpack`, `zustand`, `d3`, `@types/d3` in frontend
- [x] Built Web Worker `frontend/src/workers/eventDecoder.worker.ts` for off-thread binary msgpack decoding
- [x] Built Zustand event & scene store in `frontend/src/store/phantomStore.ts` projecting all 13 typed events into visual state
- [x] Built WebGL Canvas engine `frontend/src/components/phantom/PixiObservatoryCanvas.tsx` with:
  - The Conduit: physical glowing pipe between YOU and SERVER with sized packet objects, ciphertext glyph texture, shattering packet drops, pipe fracture & electric sparks on disconnect, re-weld arc on reconnect, throttle ring narrowing
  - Handshake Ritual: Noise XX ephemeral DH key sparks, spiral mixing vortex, session lock-in
  - Fingerprint Strip: dual scrolling barcodes (raw flow vs masked flow)
  - Censor's Eye: scanning grid, rotating HUD confidence ring, gate-slam barrier
- [x] Built interactive HUD overlay lenses:
  - `LensToggleBar.tsx`: dynamic layer toggling for Conduit, Fingerprint Strip, Censor's Eye, Mask Foundry, Arms Race Orrery, Mesh Layer, Evidence Wall
  - `MaskFoundryLens.tsx`: policy decision reasoning ticker, active mask profile, overhead gauges (bandwidth %, latency cost, stealth gain)
  - `ArmsRaceOrreryLens.tsx`: attacker vs defender balance, live D3 Pareto frontier
  - `MeshLens.tsx`: RouteLab mesh topology lens, active vs oracle optimal path comparison, dead relay alerts
  - `EvidenceWallLens.tsx`: live dynamic benchmark cards and SHA-256 event-log digest verification
  - `TimeMachineControls.tsx`: scrub/seek slider, play/pause, 0.1x to 5x speed buttons, live stream vs replay toggle, 60 FPS counter
- [x] Integrated Dual Arena global switcher into `frontend/src/App.tsx` allowing seamless switching between Phantom Observatory and RouteLab Cartographer
- [x] Captured visual regression screenshots in `/evidence/ui/` (`phantom_observatory_all_lenses_active.png`, `phantom_observatory_lower_panels.png`, `phantom_observatory_bottom.png`, `phantom_observatory_overview.png`)
- [x] Built metadata-only capture pipeline in `backend/phantomnet/data/traces.py` with 30 representative sites across 5 categories and strictly disjoint site partitioner (Train=18, Val=6, Test=6) preventing site leakage
- [x] Implemented 42-dimensional metadata feature extractor in `backend/phantomnet/ml/features.py` (size/gap histograms, burst statistics, direction ratios, moments)
- [x] Implemented classifier baselines in `backend/phantomnet/ml/censor_models.py` (`RandomForestCensor` and `OneDCNNCensor`) reporting AUC, F1, accuracy, and confusion matrices
- [x] Implemented `MaskEngine` in `backend/phantomnet/ml/mask_engine.py` with 5-parameter shaping vector (`pad_bucket`, `jitter_ms`, `dummy_rate`, `burst_chop`, `morph_ratio`) and multi-objective reward
- [x] Implemented `CMAESTuner` and `TerrainScanner` bandit in `backend/phantomnet/ml/tuner.py`
- [x] Implemented `AdversarialCoTrainer` in `backend/phantomnet/ml/co_training.py` with iterative co-training loop emitting `TRAIN_ROUND` and `POLICY_DECISION` events
- [x] Authored 5-seed ablation study in `backend/phantomnet/ml/ablation.py` across 5 regimes (`no_shaping`, `random_shaping`, `fixed_padding`, `learned_policy`, `learned_vs_retrained`) with 95% Confidence Intervals
- [x] Generated ablation evidence at `/evidence/ml/ablation.json` and Pareto frontier at `/evidence/ml/pareto.json`
- [x] Authored soak and chaos test suite in `backend/tests/phantomnet/test_chaos.py` (20-episode chaos test with 100% recovery, 2,000 continuous event memory-bounded soak test < 5MB overhead, offline cached replay verification)
- [x] Added `make evidence` target in `Makefile` and built `scripts/generate_evidence.py` compiling commit hash, seeds, machine specs, benchmarks, Pareto frontier, 5-seed ablation table with 95% CIs, determinism proof, and threats declaration into publication-grade `/evidence/REPORT.md`
- [x] Authored comprehensive Threats and Operational Limits declaration in `docs/threats_and_limits.md` (no killswitch, DNS/IPv6 boundaries, retrained censor reality)
- [x] Built Demo Mode and Interactive Judge Controls into Phantom Observatory UI:
  - 1-Key keyboard shortcuts: `D` (Demo Run), `B` (Judge Block), `S` (Judge Shield), `R` (Rewind), `Space` (Play/Pause)
  - Cyberpunk interactive HUD buttons: `DEMO [D]`, `BLOCK [B]`, `SHIELD [S]`
  - Fully offline cached fallback mode guaranteed to play even without network connectivity
- [x] Verified 60 FPS WebGL rendering, zero console errors, full strict TypeScript compliance

### Evidence Files
- `/spec/events.md`
- `/spec/events.d.ts`
- `/frontend/src/types/events.ts`
- `/docs/adr/0001-event-bus-and-routelab-reuse.md`
- `/docs/skills.md`
- `/docs/threats_and_limits.md`
- `/evidence/REPORT.md`
- `/evidence/bench/tunnel.json`
- `/evidence/ml/ablation.json`
- `/evidence/ml/pareto.json`
- `/evidence/ui/phantom_observatory_all_lenses_active.png`
- `/evidence/ui/phantom_observatory_lower_panels.png`
- `/evidence/ui/phantom_observatory_bottom.png`
- `/evidence/ui/phantom_observatory_overview.png`
- `backend/phantomnet/events.py`
- `backend/phantomnet/bus.py`
- `backend/phantomnet/api.py`
- `backend/phantomnet/synthetic.py`
- `backend/phantomnet/tunnel/`
- `backend/phantomnet/censor/`
- `backend/phantomnet/data/`
- `backend/phantomnet/ml/`
- `backend/tests/phantomnet/test_chaos.py`
- `scripts/generate_evidence.py`
- `frontend/src/workers/eventDecoder.worker.ts`
- `frontend/src/store/phantomStore.ts`
- `frontend/src/components/phantom/`

### Verification Summary
- `make verify` status: GREEN (code 0)
- `make evidence` status: GREEN (code 0)
- Ruff Lint & Format Check: Clean (0 errors across 117 files)
- Mypy Strict Typecheck: Clean (62 source files passed with zero warnings)
- Pytest Suite: 111 passed, 0 failed (all 67 RouteLab tests preserved + 44 PhantomNet tests)
- Frontend Build: Clean (compiled in 3.95s)
- UI Visual Verification: Clean (rendered in browser via Playwright, verified against design standards, 60 FPS maintained)

### Open Issues / Blockers
- None. All 5 phases of the PHANTOMNET project are 100% completed, tested, evidenced, and verified.
