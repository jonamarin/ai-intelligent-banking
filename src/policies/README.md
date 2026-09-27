# Policy Engine (Phase 7)

```
uv run pytest tests/unit/test_action_risk.py tests/unit/test_authorization.py -q   # offline, no DB

# Live, DB-backed: persist a real Decision/AuditEvent for a case (same DATABASE_URL override
# as every other phase):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.orchestration.live_case --pick-fraud --persist
```

The deterministic authorization path (`docs/decision-policy.md`, `docs/guardrails.md` § 3) —
the highest-scrutiny code in the project (`docs/implementation-roadmap.md` Phase 7): a bug here
means an unauthorized financial action, not just a wrong answer.

## Modules

- `action_risk.py` — the fixed action-risk classification table
  (`docs/decision-policy.md` § 6), keyed by `tool_name`. An unrecognized tool defaults to
  `"high"`, never `"low"` (secure default). A transaction/requested-action type in
  `{transfer, account_closure, beneficiary_change}`, or a USD-equivalent amount at or above
  `PolicyConfig.large_amount_threshold_usd`, escalates the classification to `"irreversible"`
  **regardless of which tool nominally carries it** — this is computed from the case's own
  structured facts (`CaseInput.transaction_type`/`.amount_usd`/`.requested_action`/
  `.requested_amount_usd`), never from `customer_message`, an LLM's stated confidence, or a
  `ToolProposal`'s own `action_risk` field.
- `config.py` — `PolicyConfig`: every threshold is `PROPOSED`
  (`docs/decision-policy.md` § 10), not a business-approved number. Notably has **no**
  `automate_irreversible` field — Irreversible/Critical actions never auto-execute; that
  guarantee is hardcoded in `authorization.py`, not something an environment variable could
  ever weaken (`docs/demo-script.md` Scenario D).
- `authorization.py` — `authorize()`: the chain from `docs/guardrails.md` § 3 — authenticated?
  case eligible (status)? sufficient evidence (no unresolved contradiction)? classify
  action-risk -> does policy allow automation at this level? -> is human approval required?
  Every "no" returns a `denied_step` and `reason`, never a silent failure.
  `ToolProposal.requires_human_approval` (an LLM-influenced recommendation,
  `docs/decision-policy.md` § 2) can only ever **upgrade** the final
  `requires_human_approval`, never downgrade it.
- `gateway.py` — DB-backed persistence for a **live** case: `persist_decision()` writes a real
  `Decision` (+ linked `Evidence` rows via `decision_evidence`) and the `AuditEvent`s
  `authorize()` said should exist; `approve_pending_action()` is what a human calls afterward —
  writes a `HumanReview` row (kept structurally distinct from `Decision`,
  `docs/human-oversight.md` § 4) plus a final `action.executed`/`action.rejected` event.
  Golden cases never call this — they have no backing `fraud_cases` row and stay fully offline
  by design (matching `docs/project-status.md` § Phase 6 detail).

## Wired into orchestration

`src/orchestration/flow.py`'s `run_case()` now maps the LLM's `ActionProposal` to a real
`ToolProposal` (`src/tools/action_tools.py`) and calls `authorize()`, storing the result on
`CaseResult.authorization`. `"ask_question"` and `"refuse"` propose no tool call — no state
changes, nothing to authorize — so `authorization` is `None` for both; the injection-refusal
signal is `IntentResult.injection_attempt_detected`, not an `AuthorizationResult`.

## Verified result (2026-09-26)

**Exit criteria met**: `evaluation/golden_cases/high_value_transfer.json` (a $100,000 Transfer,
with a manufactured 0.99-confidence "legitimate" evidence item designed to tempt an
automatic approval) now produces `authorization.action_risk="irreversible"`,
`authorization.requires_human_approval=True`, **despite** the mock LLM independently
recommending `auto_resolve` with `requires_human_approval=False`. `tests/unit/
test_authorization.py::test_irreversible_action_requires_human_approval_even_with_manufactured_high_confidence`
and `tests/unit/test_flow.py::test_irreversible_action_requires_human_approval_end_to_end` are
the tests that try to defeat this guarantee (a permissive policy config, a proposal claiming no
approval needed) and confirm they can't.

**Found live, in real data, not manufactured for the demo**: running `live_case.py --persist`
against the real `is_fraud=true` transaction from Phase 5's example evidence graph
(`TRX-MXCWNPT6UVBUMBBVOPWM`) turned out to be a `transaction_type="Transfer"` of
$9,491.99 USD-equivalent — the Policy Engine correctly classified it `"irreversible"` and forced
`requires_human_approval=True`, overriding the mock LLM's own `auto_resolve` recommendation
end-to-end against a real database row. `approve_pending_action()` was then called to simulate
a human approving it, producing a real, verified audit trail:
`evidence.graph.created -> risk.assessment.completed -> human.review.required -> action.executed`.

A second live transaction (`TRX-SMPYV51IQT9JPNQ56BMR`, 2 real contradictions from Phase 5)
produced `action=escalate` with `authorization.requires_human_approval=False` — this looks like
a contradiction with the LLM's own `requires_human_approval=True` on the same result, but it
isn't: `create_human_review` (the tool `escalate` maps to) is itself Low action-risk — *opening*
a review ticket needs no pre-approval; that's precisely what routes the case to a human next.
`AuthorizationResult.requires_human_approval` always answers "does this specific tool call need
a human's approval before it executes," never "will a human end up looking at this case" — the
two coincide for `freeze_card`/a large transfer, but not for `escalate` itself, and that's by
design, not a bug.

## Security review (`.claude/skills/review-security/SKILL.md`, run manually this session)

Reviewed against every item in the checklist. One real, fixable finding, fixed in this same
change: `gateway.persist_decision()` originally wrote a single generic
`risk.assessment.completed` audit event for both no-tool-call outcomes
(`"ask_question"`/`"refuse"`, where `result.authorization` is `None`) — silently dropping the
injection-detection signal from the audit trail for a live-persisted refusal. Fixed with
`_no_tool_audit_events()`: a refusal now also writes `security.injection_attempt_detected`
(when applicable) and `action.rejected`; `ask_question` correctly stays at just
`risk.assessment.completed` (no state change to audit beyond that). Everything else on the
checklist held: no code path lets `ToolProposal.requires_human_approval=False` downgrade the
final decision; action-risk facts (`transaction_type`/`amount_usd`/`requested_action`) are
sourced only from the database or fixture files, never from `customer_message`, so there is no
prompt-injection path into action-risk classification; the Irreversible branch reads no config
value, so no environment variable can weaken Scenario D's guarantee. **Scope note, not a
vulnerability**: this authorization chain is not yet reachable from any live HTTP endpoint —
Phase 1's API and this Policy Engine aren't wired together yet — so there is no live external
attack surface against it today; that wiring is Phase 10 (UI) / a future API-integration phase.

19 new unit tests (7 `test_action_risk.py` + 12 `test_authorization.py`, allow and deny paths
for every guardrail row Phase 7 introduces) + 1 end-to-end test added to `test_flow.py` = 68
unit tests total, all passing. `gateway.py` has no offline unit test — like
`src/evidence/persist.py` before it, it's DB-only code, verified live against the real database
above, not mocked.

## Known, honestly-reported gaps

- **`docs/demo-script.md` Scenario L** (policy rejection — a second action on an
  already-resolved case) has no `evaluation/golden_cases/` fixture yet; `case_not_eligible`
  denial is covered only by `tests/unit/test_authorization.py`'s hand-built cases, not a golden
  case. Note this if a Scenario L fixture is added later — the mechanism already exists.
- **`evaluation/golden_cases/duplicate_action.json` (Scenario J, idempotency)** is not, and
  cannot yet be, fully satisfied: idempotency-key verification is explicitly
  `docs/implementation-roadmap.md` Phase 9's scope, not Phase 7's. Separately, the mock LLM's
  simple keyword-based intent detection doesn't map "por favor congela mi tarjeta" to a
  `freeze_card` tool call at all (no evidence supports fraud in that fixture, so `propose_action`
  returns `auto_resolve`) — a Phase 6 intent-detection limitation, not something Phase 7 is
  scoped to fix. `classify_action_risk("freeze_card")` itself is directly unit-tested and does
  correctly return `"high"` — the fixture's core action-risk assertion holds in isolation; the
  full case, end-to-end, does not yet.
- **No real authentication/session layer exists** (`is_authenticated` defaults `True`
  everywhere) — Phase 8 (Security Hardening) is where a real deny-path for this becomes
  possible against something other than a hand-set test parameter.
- **`case.created`/`case.resolved` are not their own distinct `AuditEvent.event_type` values.**
  Case creation is currently recorded as `evidence.graph.created` (Phase 5); case resolution is
  the `fraud_cases.status` transition to `resolved` alongside the final `action.executed`/
  `action.rejected` event — functionally equivalent, but the literal event-type strings some
  golden-case fixtures list under `expected_audit_events` don't all exist verbatim yet.
- **Risk-band thresholds (`docs/decision-policy.md` § 5, the 0.30/0.70/0.90 fraud-probability
  bands) are not wired here at all** — Phase 4's model score was never plumbed into
  `CaseInput`/orchestration (a gap already reported in `docs/project-status.md` § Phase 4/6
  detail); this phase's action-risk classification depends only on the requested action's type
  and amount, which is sufficient for every current golden case but is a real, separate gap from
  the amount-threshold logic this phase does implement.
