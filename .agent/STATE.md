# PHANTOMNET State Tracker

## Current Phase: Phase 2 (Real tunnel + hostile network)
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

### Evidence Files
- `/spec/events.md`
- `/spec/events.d.ts`
- `/frontend/src/types/events.ts`
- `/docs/adr/0001-event-bus-and-routelab-reuse.md`
- `/evidence/bench/tunnel.json`
- `backend/phantomnet/events.py`
- `backend/phantomnet/bus.py`
- `backend/phantomnet/api.py`
- `backend/phantomnet/synthetic.py`
- `backend/phantomnet/tunnel/replay_window.py`
- `backend/phantomnet/tunnel/framing.py`
- `backend/phantomnet/tunnel/crypto.py`
- `backend/phantomnet/tunnel/server.py`
- `backend/phantomnet/tunnel/client.py`
- `backend/phantomnet/tunnel/socks5.py`
- `backend/phantomnet/censor/interface.py`
- `backend/phantomnet/censor/censors.py`
- `backend/phantomnet/censor/proxy.py`
- `backend/tests/phantomnet/test_events.py`
- `backend/tests/phantomnet/test_bus.py`
- `backend/tests/phantomnet/test_determinism.py`
- `backend/tests/phantomnet/test_api.py`
- `backend/tests/phantomnet/test_crypto.py`
- `backend/tests/phantomnet/test_fuzzing.py`
- `backend/tests/phantomnet/test_censor.py`
- `backend/tests/phantomnet/test_tunnel.py`
- `backend/tests/phantomnet/test_bench.py`

### Verification Summary
- `make verify` status: GREEN (code 0)
- Ruff Lint & Format Check: Clean (0 errors across 102 files)
- Mypy Strict Typecheck: Clean (53 source files passed with zero warnings)
- Pytest Suite: 101 passed, 0 failed (all 67 RouteLab tests preserved + 34 PhantomNet tests)
- Frontend Build: Clean (compiled in 15.02s)

### Open Issues / Blockers
- None. Advancing to Phase 3: Phantom Observatory UI.
