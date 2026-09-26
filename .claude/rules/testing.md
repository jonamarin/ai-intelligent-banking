# Testing Rules

Applies to `tests/unit/`, `tests/integration/`, `tests/security/`, `tests/end_to_end/` once
they exist. See `docs/evaluation-plan.md` for system-level evaluation (a different, broader
activity than these tests) and `evaluation/golden_cases/` for adversarial/scenario fixtures
these tests should draw on.

Tests must cover, at minimum:

- Happy paths for every workflow stage.
- Invalid inputs (malformed request, out-of-range values, wrong types).
- Unauthorized requests (wrong role, unauthenticated, cross-customer access attempt).
- Duplicate actions (idempotency — `docs/architecture.md` § 11).
- Timeouts and dependency failures for every external dependency
  (`docs/architecture.md` § 10's fallback table — one test per row, minimum).
- Missing data and conflicting evidence (`docs/demo-script.md` Scenarios H, I).
- Policy rejection (`docs/demo-script.md` Scenario L).
- Human escalation triggering correctly (`docs/demo-script.md` Scenario K).
- Prompt injection and other red-team cases (`docs/guardrails.md` § 4) — every case there
  needs a corresponding automated test, not just a documented expectation.
- Tool misuse / malformed tool output.
- Regression cases for any bug fixed — add the failing case as a test before/alongside the
  fix, not after.

Rules:

- Tests must not require a real LLM API — use `LLM_MODE=mock` with deterministic scenario-based
  responses (`prompt.md` § 8, § 52). A test suite that can't run offline is a broken test
  suite for this project.
- Never weaken a production security control, disable a check, or loosen a validation rule
  merely to make a test pass. If the test is wrong, fix the test; if the code is wrong, fix the
  code; never both-hands-wave by disabling the thing being tested.
- Unit tests: fraud features, policy rules, risk thresholds, PII redaction, evidence
  generation, tool authorization (`prompt.md` § 31).
- Integration tests: API → orchestrator, orchestrator → database, orchestrator → fraud model,
  orchestrator → RAG, orchestrator → tool gateway.
- End-to-end: at minimum the twelve scenarios in `docs/demo-script.md`.
- Every new state-changing action or tool ships with its authorization test (allow path and at
  least one deny path) in the same change.
- Record actual test/lint/typecheck commands and their real output when reporting verification
  — never claim tests pass without having run them (`docs/implementation-roadmap.md` phase
  exit criteria depend on this being true).
