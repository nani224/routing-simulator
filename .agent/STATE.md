# PHANTOMNET State Tracker

## Current Phase: Phase 3 (Phantom Observatory UI)
Status: COMPLETED

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
- [x] Verified 60 FPS rendering, zero console errors, full strict TypeScript compliance

### Evidence Files
- `/spec/events.md`
- `/spec/events.d.ts`
- `/frontend/src/types/events.ts`
- `/docs/adr/0001-event-bus-and-routelab-reuse.md`
- `/docs/skills.md`
- `/evidence/bench/tunnel.json`
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
- `frontend/src/workers/eventDecoder.worker.ts`
- `frontend/src/store/phantomStore.ts`
- `frontend/src/components/phantom/`

### Verification Summary
- `make verify` status: GREEN (code 0)
- Ruff Lint & Format Check: Clean (0 errors across 103 files)
- Mypy Strict Typecheck: Clean (53 source files passed with zero warnings)
- Pytest Suite: 101 passed, 0 failed (all 67 RouteLab tests preserved + 34 PhantomNet tests)
- Frontend Build: Clean (compiled in 1.27s)
- UI Visual Verification: Clean (rendered in browser via Playwright, verified against design standards)

### Open Issues / Blockers
- None. Ready for Phase 4: The AI (Adversarial learning, feature extraction, Mask Engine CMA-ES tuner, co-training loop, ablations with 95% CIs).
