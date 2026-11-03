# PHANTOMNET: agent constitution
Repo: existing routing-simulator. Work on branch `phantomnet`. Never push to main.

PRINCIPLES
- Event spine: backend emits typed events (schema in /spec/events.md). UI renders events only. No fake animations.
- Determinism: every experiment takes a seed; same seed => identical event-log hash.
- Crypto: only audited libraries (noiseprotocol or cryptography: X25519, ChaCha20-Poly1305). NEVER invent a cipher, handshake or KDF. If unsure, stop and ask.
- Simulator sees metadata only (size, direction, timestamp), never payloads.
- Strict typing (mypy --strict, tsc strict), ruff, small modules, ADR for each major decision in /docs/adr.

THE LOOP (mandatory for every task)
1. Write/extend tests first for the task's acceptance criteria.
2. Implement.
3. Run `make verify` (lint + types + unit + property + integration + UI e2e + perf gates).
4. If red: diagnose root cause, fix, rerun. Max 6 attempts per distinct failure.
5. After 6 attempts: STOP, write the failure analysis to .agent/BLOCKERS.md and move to the next task.
FORBIDDEN: editing/deleting/skipping tests, loosening thresholds, catching-and-ignoring errors, mocking away the thing under test just to pass.
After each task: update .agent/STATE.md (done / evidence file paths / open issues) and commit with a conventional message.

DEFINITION OF DONE for a phase: `make verify` green, evidence artifacts generated under /evidence, STATE.md updated, a screen recording of the phase's UI captured by Playwright.

SKILLS: before installing any skill from GitHub, read its source, pin the commit hash, record it in /docs/skills.md. Prefer anthropics/skills (frontend-design, webapp-testing). Reject anything that runs unexplained shell commands or fetches remote code.

