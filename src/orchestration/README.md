# AI Agent / Orchestration (Phase 6)

```
# Offline, no DB, no API key — runs every evaluation/golden_cases/*.json fixture:
uv run python -m src.orchestration.run_golden_cases

# Against a real transaction (needs Phase 3-5 data loaded):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" \
  uv run python -m src.orchestration.live_case --pick-fraud
```

Wires Phases 1-5 (DB, ingestion, fraud model, evidence engine) into the explicit case
orchestration state machine (`docs/architecture.md` § 2, § 8):

```
intent extraction -> (refuse if injection) -> next-question gate
-> action proposal -> policy grounding (RAG) -> dual explanation
```

Every stage's input/output is a Pydantic-validated structured type (`src/agents/schemas.py`,
`extra="forbid"`) — never raw text threaded between stages. **Nothing this phase produces is
executed.** `CaseResult.action` is a proposal (`docs/decision-policy.md` § 2); no action tool is
ever called from `flow.py`, and `flow.py` doesn't even import `src/tools/action_tools.py` — that
wiring is deliberately left for Phase 7 (Policy Engine), which doesn't exist yet.

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
  share so `flow.py` has exactly one code path.
- `flow.py` — the state machine itself.
- `golden_case_loader.py` — converts `evaluation/golden_cases/*.json` into `CaseInput`.
- `live_case.py` — converts a live, DB-backed `EvidenceGraph` (Phase 5) into the same
  `CaseInput` shape, sourcing `customer_message` from the customer's own
  `call_transcripts.customer_text` (a real raw-dataset field) with a clearly-labeled placeholder
  when none exists.
- `run_golden_cases.py` — the fixture-suite CLI.

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

## What this phase does not do

Authorize or execute any action. Persist anything (no `Decision`, no `HumanReview` row is
written — that's Phase 7/8's job once a policy engine exists to make those calls legitimately).
Call a real LLM provider (`LLM_MODE=live` is `NotImplementedError`, honestly, not a stub that
silently no-ops). Auto-grade golden cases against free-text expected outcomes — `run_golden_cases.py`
reports them for human comparison instead of pattern-matching prose into a pass/fail.
