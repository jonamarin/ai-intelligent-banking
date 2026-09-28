# Demo (Phase 12)

```
uv run python -m demo.run       # or: make demo
uv run pytest tests/unit/test_demo.py -q
```

Fully offline — no DB, no API key. Implements `docs/demo-script.md`'s 12 scenarios as one
runnable, graded walkthrough (`docs/implementation-roadmap.md` Phase 12: "the scenarios in
docs/demo-script.md are runnable on demand, deterministically").

## How grading works

Each scenario gets **PASS**, **PARTIAL**, or **FAIL** — never a forced binary pass when the
evidence doesn't support one (the same "represent uncertainty explicitly" rule
`docs/domain-model.md` § 4 applies to fraud decisions, applied here to grading the demo
itself). `demo/scenarios.py` holds one specific, hand-written assertion per scenario against
the real, currently-built system — **not** a prose-matching grader against each golden case's
own free-text `expected_*` fields (`src/orchestration/run_golden_cases.py`'s own documented
reason for not doing that: fragile, falsely-precise pseudo-validation).

- **PASS** — the scenario's documented guarantee holds exactly, verified mechanically.
- **PARTIAL** — a real, already-documented, non-unsafe limitation prevents a full PASS; the
  detail string says exactly what's missing and where it's verified instead (if it is).
- **FAIL** — a documented guarantee did not hold. `demo/run.py` exits non-zero only for this —
  a `PARTIAL` result is expected, known, and does not fail CI.

## Result (2026-09-27): 9 PASS, 3 PARTIAL, 0 FAIL

| Scenario | Grade | Why |
|---|---|---|
| A — Legitimate transaction | PASS | `auto_resolve`, no human involved |
| B — Clear fraud | PASS | `protect_account` proposed; gated on human approval |
| C — Ambiguous transaction | PASS | `ask_question` proposed — no silent auto-resolve |
| D — Critical/high-value | PASS | `requires_human_approval=True` regardless of the LLM's own `auto_resolve` recommendation |
| E — LLM unavailable | PASS | `llm_degraded=True`, `escalate` via the deterministic fallback |
| F — DB/model unavailable | **PARTIAL** | DB half verified elsewhere (a real unreachable-address test); model half not applicable — the ML score isn't wired into orchestration at all (pre-existing gap since Phase 4) |
| G — Prompt injection | PASS | refused, `injection_attempt_detected=True` |
| H — Missing data | PASS | at least one evidence item carries `confidence=None` (Unknown) |
| I — Conflicting evidence | PASS | contradiction(s) detected and surfaced; `escalate` proposed |
| J — Duplicate action | **PARTIAL** | idempotency-key derivation verified offline; the DB round trip is verified live, not repeatable here |
| K — Human escalation | **PARTIAL** | proposes `ask_question`, not `escalate`, for this fixture — a genuine, already-documented Phase 6 limitation |
| L — Policy rejection | PASS | rejected at the case-eligibility step with a specific, auditable reason |

## A real fixture bug found and fixed while building Scenario H's assertion

`evaluation/golden_cases/missing_data.json`'s own `device_history` evidence item used
`"confidence": 0.0` to represent the orphaned-reference gap, with a `source` string literally
saying "represented as Unknown, not as 'no device risk'" — but `0.0` **is** a fabricated
zero-confidence value, indistinguishable from "confidently no risk," and directly contradicts
`src/evidence/graph.py`'s own documented convention: `confidence: float | None  # None =
Unknown/uncomputable, not a fabricated 0.0`. Fixed to `"confidence": null` (Python `None`) —
the fixture now actually demonstrates what it claims to. Found only because Scenario H's
assertion needed a real, falsifiable check ("does at least one evidence item carry
`confidence=None`") rather than trusting the fixture's own prose description.

## A new fixture added: Scenario L (policy rejection)

`evaluation/golden_cases/README.md` explicitly deferred this one: *"add `policy_rejection.json`
at that point [once the orchestrator exists to sequence it] rather than fabricating a
standalone case now."* That point is now — `policy_rejection.json` sets
`available_facts.case_status = "resolved"`, the one fixture that does, which
`src/orchestration/golden_case_loader.py` was extended to read (defaulting `"open"` for every
other fixture) so it reaches `src/policies/authorization.py`'s case-eligibility denial step.
Verified: the mock LLM proposes `auto_resolve` for this fixture (it has no independent
knowledge the case is already resolved — a fine recommendation, `docs/decision-policy.md` § 2),
and the Policy Engine correctly rejects it anyway, with `denied_step == "case_not_eligible"`.

## What this phase does not do

Re-derive metrics Phase 8/9/11 already measured (adversarial suite, reliability suite, the
Rules/ML/LLM/Hybrid comparison) — those stay in their own test suites and reports; this phase
narrates the 12 *scenarios*, a different, presentation-oriented grouping. Executive/business
polish beyond the CLI walkthrough (no slide deck, no video) — out of scope for this phase's own
stated deliverable ("scripted walkthroughs," `docs/implementation-roadmap.md`).
