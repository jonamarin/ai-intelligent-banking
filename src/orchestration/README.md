# AI Agent / Orchestration (Phase 6; Phase 7 authorization wiring; Phase 9 reliability)

```
# Offline, no DB, no API key — runs every evaluation/golden_cases/*.json fixture:
uv run python -m src.orchestration.run_golden_cases

# Against a real transaction (needs Phase 3-5 data loaded), persisting a real Decision (Phase 7/9):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.orchestration.live_case --pick-fraud --persist
```

Wires Phases 1-5 (DB, ingestion, fraud model, evidence engine) into the explicit case
orchestration state machine (`docs/architecture.md` § 2, § 8):

```
intent extraction -> (refuse if injection) -> next-question gate
-> action proposal -> policy grounding (RAG) -> Policy Engine authorization -> dual explanation
```

Every stage's input/output is a Pydantic-validated structured type (`src/agents/schemas.py`,
`extra="forbid"`) — never raw text threaded between stages. `CaseResult.action` is still only a
**recommendation** (`docs/decision-policy.md` § 2) — `flow.py` now maps it to a real
`ToolProposal` and calls the Policy Engine's `authorize()` (Phase 7,
`src/policies/authorization.py`), storing the result on `CaseResult.authorization`. Nothing in
`src/orchestration/` itself still *executes* anything — `src/tools/action_tools.py` functions
only ever return a `ToolProposal`; only `src/policies/gateway.py` (used by `live_case.py`)
persists a real Decision/AuditEvent/HumanReview row for a live case, idempotency-key-aware
(Phase 9). See `src/policies/README.md` for the authorization/persistence detail — this README
covers the state machine and its Phase 9 reliability hardening.

## Modules

- `src/agents/schemas.py` — `IntentResult`, `NextQuestionDecision`, `ActionProposal`,
  `CaseExplanation`. All `extra="forbid"` so a malformed LLM response is a validation error,
  not a best-effort guess.
- `src/agents/llm_client.py` — `LLMClient` Protocol + `MockLLMClient`, a deterministic,
  rule-based simulation of plausible LLM behavior (never randomness — same input, same output,
  required for reproducibility). `get_llm_client()` raises `NotImplementedError` for
  `LLM_MODE=live`: this environment has no authorized API key, and CLAUDE.md § 7 forbids
  fabricating an untested provider integration. `LLM_MODE=mock` is the hard requirement anyway
  (`prompt.md` § 52).
- `src/retrieval/policy_rag.py` + `policy_docs/*.md` — TF-IDF (not embeddings — documented
  simplification given memory constraints and the no-paid-API-key constraint) retrieval over 4
  synthetic Spanish policy documents. Returns `None` rather than a weak guess when nothing
  clears `SIMILARITY_THRESHOLD` (`docs/architecture.md` § 7).
- `src/tools/read_tools.py` — real DB read queries (`get_customer`, `get_transaction`, etc.).
  Executed directly — read-only, low risk.
- `src/tools/action_tools.py` — `propose_create_dispute`, `propose_freeze_card`, etc. Every
  function returns a `ToolProposal` (`src/tools/base.py`); **none writes to the database.**
  Not imported by `flow.py` in this phase — see above.
- `case.py` — `CaseInput`/`CaseResult`, the shape both fixture-driven and live-data-driven cases
  share so `flow.py` has exactly one code path. `CaseResult.llm_degraded` (Phase 9) and
  `.authorization` (Phase 7) are both real fields now, not placeholders.
- `flow.py` — the state machine itself, including the Policy Engine call and (Phase 9) the
  retry-then-fallback wrapping around every `llm_client` call.
- `retry.py` (Phase 9) — `call_with_retry()`: bounded retries with backoff for
  transport/validation-shaped failures only (never a real programming bug), raising
  `LLMUnavailableError` once exhausted.
- `fallback.py` (Phase 9) — the deterministic path `flow.py` switches to when
  `LLMUnavailableError` is raised: local regex injection detection (no provider call), always
  `escalate` (never guess), a placeholder explanation clearly marked `[LLM_DEGRADED]`.
- `golden_case_loader.py` — converts `evaluation/golden_cases/*.json` into `CaseInput`.
- `live_case.py` — converts a live, DB-backed `EvidenceGraph` (Phase 5) into the same
  `CaseInput` shape, sourcing `customer_message` from the customer's own
  `call_transcripts.customer_text` (a real raw-dataset field) with a clearly-labeled placeholder
  when none exists. `--persist` writes a real Decision (Phase 7/9); `--persist-twice`
  demonstrates idempotency live.
- `run_golden_cases.py` — the fixture-suite CLI. Runs a fixture whose
  `synthetic_input.injected_fault` mentions an LLM outage through `FailingLLMClient` instead of
  `MockLLMClient` (Phase 9), genuinely exercising the fallback path against that fixture.

## A circularity bug found and fixed before any result could be trusted

The first version of `golden_case_loader.py` set `escalation_required` directly from each
fixture's own `expected_human_involvement` text:

```python
escalation_required=raw.get("expected_human_involvement", "none") not in ("none", None),
```

Running `run_golden_cases.py` against this produced suspiciously perfect alignment between the
orchestrator's decisions and each case's expected outcome — because the orchestrator was, in
effect, being handed the answer key as an input signal. This was caught immediately after the
first run, before the result was reported anywhere, and fixed by deriving `escalation_required`
the only way Phase 6 can legitimately compute it offline: `bool(detect_contradictions(items))` —
the same shared contradiction-detection function the live Evidence Engine (Phase 5) uses,
applied to the fixture's own evidence items, never to its prose expected-answer field.

## Verified result (2026-09-26) — after the fix, honestly reported

All 10 golden cases run end-to-end without error (`data/reports/golden_case_run.json`), and the
mechanically-checkable invariants in `tests/unit/test_flow.py` hold for all of them (injection is
always refused; `escalate`/`protect_account` always require human approval; `auto_resolve` is
never proposed over a detected contradiction). Comparing the actual decision against each
fixture's own `expected_human_involvement` field (for human review, not auto-graded):

| case | actual action | matches expectation? |
|---|---|---|
| `clear_fraud` | `protect_account` (human approval required) | Yes |
| `conflicting_evidence` | `escalate` (human approval required) | Yes |
| `prompt_injection` | `refuse` | Yes |
| `legitimate_transaction` | `auto_resolve` | Yes |
| `high_value_transfer` | `auto_resolve`, **no** human approval | **No** — expects mandatory escalation |
| `duplicate_action` | `auto_resolve` | **No** — expects human review because the underlying action is high-risk (`freeze_card`) |
| `human_escalation` | `ask_question` | Partial — case expects escalation; evidence alone isn't contradictory enough here to trigger it |
| `ambiguous_transaction`, `dependency_failure`, `missing_data` | mixed | For human judgment — these hinge on prose nuance no automated check should grade |

The two clear misses are not a bug to patch around — they are the honest, expected boundary of
this phase's scope. Evidence-graph contradiction is the **only** legitimate escalation signal
Phase 6 can compute without a policy engine. `high_value_transfer` needs escalation because of an
**amount threshold rule**, and `duplicate_action` needs it because of an **action-risk
classification** (`freeze_card` = High risk) — neither is a fact the evidence graph itself
carries. Both are exactly what Phase 7 (Policy Engine, `docs/implementation-roadmap.md`) is
scoped to add: rule-based authorization on top of these same proposals, not a redesign of them.

Live-data smoke test against two real transactions from the Phase 5 evidence-graph examples
(`DATABASE_URL=... uv run python -m src.orchestration.live_case --transaction-id <ID>`):

- `TRX-MXCWNPT6UVBUMBBVOPWM` (clean evidence, no contradictions) → `auto_resolve`, no approval
  required.
- `TRX-SMPYV51IQT9JPNQ56BMR` (2 contradictions: anomalous amount vs. known device/matching
  country) → `escalate`, human approval required.

Both real transactions had zero rows in `call_transcripts` for their customers (that table
wasn't populated in the currently loaded ingestion sample — `docs/project-status.md` § Phase 3
detail), so `customer_message` fell back to the documented placeholder in both cases. This is
reported honestly, not hidden: a live deployment needs either a populated `call_transcripts`
sample or a real conversational intake channel before `customer_message` reflects an actual
customer statement.

## What Phase 6 did not do (historical — see Phase 7/9 below for what closed these)

Authorize or execute any action, or persist anything — both are now real (Phase 7's
`src/policies/authorization.py`, Phase 9's `src/policies/gateway.py`). Call a real LLM provider
(`LLM_MODE=live` is still `NotImplementedError`, honestly, not a stub that silently no-ops —
Phase 9's fallback path is for when the *configured* client fails, not a second provider).
Auto-grade golden cases against free-text expected outcomes — `run_golden_cases.py` still
reports them for human comparison instead of pattern-matching prose into a pass/fail.

## Reliability (Phase 9)

```
uv run pytest tests/reliability/ -q     # offline, no DB, no API key
```

Makes the failure modes in `docs/architecture.md` § 10 real, not just documented, for the parts
that live in this package.

- **LLM unavailable/timeout (Scenario E)**: every `llm_client` call in `flow.run_case()` is
  wrapped in `retry.call_with_retry()` — bounded attempts (`Settings.llm_max_attempts`, default
  2), small backoff between them, retrying only transport/validation-shaped failures
  (`TimeoutError`, `ConnectionError`, `OSError`, `pydantic.ValidationError` — never a real bug
  like `TypeError`/`KeyError`, which would be masked, not handled, by a blind retry). Once
  exhausted, `LLMUnavailableError` is caught once at the top of `run_case()` and the whole case
  switches to `fallback.py`'s deterministic path: local regex injection detection still runs (no
  provider call needed), the Next-Best-Question gate is skipped entirely (scoring is
  LLM-assisted; guessing would be worse than not asking), and the action is always `escalate`
  (or `refuse`, if the fallback's own regex still catches an injection attempt) — never a guessed
  `auto_resolve`. `CaseResult.llm_degraded=True` and `AuditEvent` type `llm.degraded` both record
  the degradation (`docs/demo-script.md` Scenario E: "clearly flagged ... in the decision
  record" — now a real `decisions.llm_degraded` boolean column, not buried in a JSON payload).
- **Malformed model/tool output**: the same retry wrapper catches `pydantic.ValidationError` —
  `MockLLMClient` can't actually produce one (it always constructs valid objects), so this is
  exercised by `FlakyLLMClient`/hand-raised errors in `tests/reliability/`, future-proofing the
  mechanism for when a real provider (`LLM_MODE=live`) exists and can genuinely return malformed
  JSON.
- **Vector DB / RAG unavailable**: `flow._ground_in_policy()` catches any exception from
  `rag.retrieve()` and degrades to `policy_source=None` ("policy could not be verified") instead
  of crashing the whole case.
- **Database unavailable**: `src/models/base.py`'s `get_engine()` now passes a
  `connect_timeout` (`Settings.db_connect_timeout_seconds`, default 5s) — verified directly
  against a genuinely unreachable address (`tests/reliability/test_db_timeout.py`): fails with a
  clear `OperationalError` in ~2-6 seconds, not an unbounded hang on the OS's own TCP timeout.
- **Idempotency (Scenario J)**: `src/tools/base.py`'s `ToolProposal.idempotency_key` (default
  `f"{case_id}-{tool_name}"`, `src/tools/action_tools.py`) flows through
  `AuthorizationResult` into `src/policies/gateway.py`'s `persist_decision()`, which reserves it
  in the new `action_executions` table via `INSERT ... ON CONFLICT DO NOTHING RETURNING` — a
  database-level race, not a check-then-insert — before ever creating the `Decision` row. A
  detected duplicate writes exactly one `action.duplicate_detected` event against the *original*
  `decision_id` and creates no new `Decision`. Full detail and the live-verified proof (one
  `Decision` row, one `action.executed` event, after two `persist_decision()` calls with the
  same idempotency key against a real database): `src/policies/README.md`.
- **`evaluation/golden_cases/dependency_failure.json` now genuinely exercises Scenario E** — its
  `synthetic_input.injected_fault` field (previously inert documentation) is read by
  `run_golden_cases.py` and routes that one fixture through `FailingLLMClient`. Result: `intent
  confidence=0.00` (honestly reported as unknown, not guessed), `action=escalate`,
  `human_approval=True`, `llm_degraded=True` — matching the fixture's own
  `expected_human_involvement` ("likely required, since automated explanation/next-best-question
  generation is degraded"), found true by actually running it, not by inspection.

### Known, honestly-reported gaps

Kafka/event-bus unavailability (§ 10's last row) is not applicable — no message bus exists in
this project and none is planned unless a future phase actually needs asynchronous processing.
**Update (2026-10-01, Phase 15):** fraud-model unavailability now has a real code path —
`src/ml/score.py`'s cached scoring + `src/orchestration/live_case.py` setting
`CaseInput.model_degraded=True` when the artifact is missing, propagated through `run_case()` to
`CaseResult.model_degraded` and finally persisted to `decisions.model_degraded` (previously a
real column nothing ever set to `True`). Verified live both ways (a real score, and the artifact
temporarily removed) — `docs/project-status.md` § Phase 15 detail. Circuit breakers ("where
useful," per the roadmap's own scope
line) were judged not useful yet: every dependency here is called at most a handful of times per
case, not in a tight loop where a breaker would earn its complexity over a bounded retry.
