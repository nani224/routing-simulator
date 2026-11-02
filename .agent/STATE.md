# PHANTOMNET State Tracker

## Current Phase: Phase 1 (Spine, contract, harness)
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

### Evidence Files
- `/spec/events.md`
- `/spec/events.d.ts`
- `/frontend/src/types/events.ts`
- `/docs/adr/0001-event-bus-and-routelab-reuse.md`
- `backend/phantomnet/events.py`
- `backend/phantomnet/bus.py`
- `backend/phantomnet/api.py`
- `backend/phantomnet/synthetic.py`
- `backend/tests/phantomnet/test_events.py`
- `backend/tests/phantomnet/test_bus.py`
- `backend/tests/phantomnet/test_determinism.py`
- `backend/tests/phantomnet/test_api.py`

### Verification Summary
- `make verify` status: GREEN (code 0)
- Ruff Lint & Format Check: Clean (0 errors across 87 files)
- Mypy Strict Typecheck: Clean (43 source files passed with zero warnings)
- Pytest Suite: 84 passed, 0 failed (all 67 RouteLab tests preserved + 17 PhantomNet tests)
- Frontend Build: Clean (compiled in 499ms)

### Open Issues / Blockers
- None. Ready for Phase 2 (Real tunnel + hostile network) and Phase 3 (Phantom Observatory UI).
