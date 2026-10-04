# Implementation Roadmap

Owns: future implementation sequence. See `docs/project-status.md` for what is actually built
right now (nothing yet — this is a pre-implementation initialization). Use vertical slices:
each phase should leave the system runnable end-to-end for the scope it adds, not a disconnected
layer waiting on a later phase to become useful.

Every phase below follows: objective, scope, deliverables, dependencies, tests, security
requirements, exit criteria, risks.

## Phase 1 — Foundation

**Objective:** a runnable, testable skeleton. **Scope:** `pyproject.toml`/dependency manifest,
project structure (`src/` tree per `docs/architecture.md`), configuration loading
(`.env.example`), structured logging, error-handling conventions, Docker/Docker Compose,
`Makefile`, pytest wiring, CI skeleton (lint/typecheck/test, no production credentials
required). **Deliverables:** `docker compose up` starts an empty-but-healthy service;
`make test` runs (even with zero tests) and `make lint`/`make typecheck` pass on an empty
codebase. **Dependencies:** none. **Tests:** CI pipeline itself is the test. **Security:** no
secrets committed; `.gitignore` covers `.env` and local artifacts (already in place from this
initialization). **Exit criteria:** a fresh clone can run the make targets in
`docs/product-requirements.md` § local-dev steps (mirrors `prompt.md` § 50) without manual
fixup. **Risks:** stack choices in `docs/architecture.md` § 15 turn out to be a poor fit once
real code exists — record any change as an ADR (`docs/decisions/README.md`).

## Phase 2 — Domain

**Objective:** the core domain objects exist as code. **Scope:** SQLAlchemy models and
migrations for the entities in `docs/domain-model.md` § 3; Pydantic schemas mirroring them.
**Deliverables:** migrations apply cleanly against a fresh PostgreSQL instance; unit tests for
model constraints. **Dependencies:** Phase 1. **Tests:** unit tests for each model's
constraints/validation. **Security:** no PII field is stored without the classification from
`docs/data-governance.md` § 1 being explicit in the model/schema docstring. **Exit criteria:**
every entity in `docs/domain-model.md` § 3 has a corresponding, migrated table.
**Risks:** over-modeling entities the dataset can't actually populate (e.g., `Device`,
`Merchant` are derived, not source tables — see `docs/data-dictionary.md`); keep derivation
logic explicit rather than pretending they're dimension tables.

## Phase 3 — Synthetic Data / Ingestion — `IMPLEMENTED` (sample mode; see docs/project-status.md)

**Objective:** the LATAM Bank dataset is loaded and usable. **Scope:** ingestion pipeline for
the tables this workflow actually uses, per `docs/data-dictionary.md` § Tables not used
(`branches`, `service_agents`, `marketing_campaigns`, `campaign_sends`,
`satisfaction_surveys` excluded — not just "initially," permanently, unless a later phase
changes scope); data-quality validation per `docs/data-lineage.md` § 7; a data-quality report.
**Deliverables:** `customers`, `products`, `daily_exchange_rates`, `transactions`,
`call_center_interactions`, `call_transcripts`, `complaints`, `digital_events` loaded into
PostgreSQL; data-quality report generated. **Delivered as:** `src/ingestion/` (loader,
partition discovery, quality report, CLI) — see `src/ingestion/README.md` and
`docs/project-status.md` § Phase 3 detail for exactly what was verified and how.
**Dependencies:** Phase 2; the raw dataset files must be obtained (done —
`docs/data-lineage.md` § 1). **Tests:** schema validation, duplicate/null-rate checks
against the documented baselines (`docs/data-lineage.md` § 2) — implemented; plus 3 regression
tests for a real pandas-version NA-handling bug found during verification
(`tests/unit/test_ingestion_loader.py`). **Security:** confirmed no real data in the dataset
before loading (sanity check; found nothing, as expected). **Exit criteria:** the fraud model
(Phase 4) can query real feature inputs from the loaded tables — met for the sample-mode data
currently loaded. **Risks:** confirmed, not just anticipated — the ~19M-row scale (and this
development machine's limited free RAM) made even a 3-day sample run get killed by
out-of-memory conditions twice before a memory-usage fix; `--full` has not been attempted here
(`src/ingestion/README.md` § Sample vs. full mode). Whoever runs `--full` next should budget
real time and memory headroom for it, not assume it "should just work" because the sample did.

## Phase 4 — Fraud ML — `IMPLEMENTED` (see docs/project-status.md § Phase 4 detail)

**Objective:** a working, evaluated fraud/risk model. **Scope:** baseline
(logistic regression/rules) + main model (XGBoost/LightGBM) per
`docs/model-evaluation.md` §§ 2–4; SHAP explainability; model versioning. **Deliverables:**
trained model artifact + evaluation report (`docs/evaluation-plan.md` § 2 metrics, `MEASURED`
and labeled with the actual temporal split used). **Delivered as:** `src/ml/` (dataset,
features, baseline, model, evaluate, explain, train) — see `src/ml/README.md` and
`docs/project-status.md` § Phase 4 detail for exactly what was built and verified.
**Dependencies:** Phase 3. **Tests:** feature unit tests, leakage checks (`fraud_score`/
`is_fraud` never used as an input), calibration check — implemented
(`tests/unit/test_ml_features.py`, 5 tests) and passing. **Security:** none beyond standard
data handling. **Exit criteria:** a documented, reproducible evaluation report exists with
real numbers, not placeholders — met (`data/reports/fraud_model_evaluation.json`, reproduced
twice with identical results). **Risks:** confirmed, not just anticipated — the synthetic
`is_fraud` label turned out to be effectively unpredictable from the transactional/behavioral
features this phase could build (test ROC-AUC 0.46–0.50, near chance), reported honestly per
this very risk note rather than tuned away. Verified this isn't a pipeline bug: the dataset's
own `fraud_score` field clearly separates the classes even though none of the 15 implemented
features do — see `src/ml/README.md` for the full diagnostic and the leading hypothesis
(device/IP signal via Phase 5's `Device` derivation, not yet loaded).

## Phase 5 — Evidence Engine — `IMPLEMENTED` (see docs/project-status.md § Phase 5 detail)

**Objective:** the evidence graph is real. **Scope:** evidence extraction from retrieved data,
graph construction (`docs/domain-model.md` § Evidence Graph), provenance stamping,
contradiction detection, uncertainty representation. **Deliverables:** given a case, produce a
structured evidence graph with `direction`/`confidence`/`provenance` on every node/edge.
**Delivered as:** `src/evidence/` (device derivation, graph construction, persistence, CLI) —
see `src/evidence/README.md` and `docs/project-status.md` § Phase 5 detail for exactly what
was built and verified. **Dependencies:** Phases 2–4. **Tests:** unit tests per
evidence-extraction rule; a contradiction-detection test using two conflicting signals —
implemented (`tests/unit/test_evidence_graph.py`, 13 tests) and passing, including the
required contradiction test using two genuinely conflicting signals. **Security:** evidence
records are append-only — no update/delete tool exists (`docs/guardrails.md` § 4, "delete the
fraud evidence" red-team case) — enforced by never calling UPDATE/DELETE on the table, not
just by policy. **Exit criteria:** the example graph shape in `prompt.md` § 10 is reproducible
from real data for at least one seeded case — met, and exceeded: two real cases (one
`is_fraud=true`, one `is_fraud=false` with genuine detected contradictions), not a single
cherry-picked or synthetic example. **Risks:** confirmed as anticipated — contradiction
detection's threshold-based heuristic was verified only against hand-crafted unit tests and
two real spot-checked cases, not against `evaluation/golden_cases/conflicting_evidence.json`
(that golden case is a hand-authored fixture, not live data, and wiring golden-case validation
into the evidence engine's test suite hasn't been done yet) — treat the specific confidence
thresholds as illustrative, not tuned/validated, until that's done.

## Phase 6 — AI Agent (Conversation + Orchestration) — `IMPLEMENTED` (see docs/project-status.md § Phase 6 detail)

**Objective:** the LLM-driven parts work, in both mock and real-provider mode. **Scope:**
intent detection, entity extraction, orchestration state machine, structured outputs, tool
definitions (`prompt.md` § 16), RAG over policy documents, Next-Best-Question gate
(`docs/architecture.md` § 8). **Deliverables:** a case can be driven end-to-end by a scripted
mock-mode conversation without any external API key. **Dependencies:** Phases 2, 5.
**Delivered as:** `src/agents/` (structured-output schemas, `LLMClient` Protocol +
`MockLLMClient`), `src/retrieval/` (TF-IDF policy RAG over 4 synthetic Spanish policy docs),
`src/tools/` (read tools executed directly; action tools return proposals only, never write),
`src/orchestration/` (the state machine, golden-case and live-case loaders, the fixture-suite
CLI) — see `src/orchestration/README.md` and `docs/project-status.md` § Phase 6 detail for
exactly what was built and verified, including a real circularity bug (`escalation_required`
derived from a fixture's own expected-answer field) found and fixed before any result was
reported. **Tests:** structured-output schema tests (via `extra="forbid"` Pydantic validation,
exercised in `tests/unit/test_flow.py`); tool-call-shape tests — implemented
(`tests/unit/test_policy_rag.py`, 4 tests; `tests/unit/test_flow.py`, 6 tests: injection always
refused, `escalate`/`protect_account` always require human approval, `auto_resolve` never
proposed over a contradiction, every golden case runs without raising, mock client is
deterministic) and passing. **Security:** tool calls are proposals only at this phase —
`flow.py` doesn't import `src/tools/action_tools.py` at all, so the Action Gateway (Phase 7) is
the only thing that can ever authorize them; verified by inspection, not just by convention.
**Exit criteria:** `LLM_MODE=mock` produces deterministic, reproducible output for each
`evaluation/golden_cases/` scenario — met (`data/reports/golden_case_run.json`, all 10 run
without error) and also verified against 2 real live transactions via `live_case.py`.
**Risks:** confirmed as anticipated — evidence-only escalation reasoning correctly handles
contradiction-driven cases but cannot satisfy scenarios requiring escalation for other reasons
(an amount threshold, an action's inherent risk classification); 2 of 10 golden cases expose
this gap honestly rather than being made to look correct. This is exactly the gap Phase 7 is
scoped to close, not a defect to work around here.

## Phase 7 — Policy Engine — `IMPLEMENTED` (see docs/project-status.md § Phase 7 detail)

**Objective:** the deterministic authorization path is real. **Scope:** action classification
(`docs/decision-policy.md` § 6), configurable risk-band thresholds, tool authorization chain
(`docs/architecture.md` § 6), human-escalation triggers, critical-action restrictions.
**Deliverables:** every tool call from Phase 6 now passes through real authorization code, not
a stub. **Delivered as:** `src/policies/` (`action_risk.py`'s fixed classification table,
`config.py`'s explicitly-`PROPOSED` thresholds, `authorization.py`'s tool-authorization chain,
`gateway.py`'s DB-backed Decision/AuditEvent/HumanReview persistence for live cases) wired into
`src/orchestration/flow.py`'s `run_case()` via the new `CaseResult.authorization` field — see
`src/policies/README.md` and `docs/project-status.md` § Phase 7 detail for exactly what was
built and verified, including a subtle, honestly-documented (non-bug) finding about what
`requires_human_approval` means for the `escalate` action specifically. **Dependencies:**
Phases 4–6. **Tests:** every guardrail row this phase introduces has a corresponding test —
implemented (`tests/unit/test_action_risk.py`, 7 tests; `tests/unit/test_authorization.py`, 12
tests covering both an allow and a deny path per stage of the chain) and passing.
**Security:** tool calls from Phase 6 now pass through this real authorization code — verified
by an actual bypass-attempt test (a permissive policy config, a proposal that itself claims no
approval is needed), both of which still produce `requires_human_approval=True` for an
Irreversible/Critical action, because that branch reads no configuration value at all.
**Exit criteria:** Scenario D (critical/irreversible action) in `docs/demo-script.md` requires
human approval regardless of a manufactured high-confidence AI recommendation, provably (a
test that tries to bypass it and fails) — met
(`tests/unit/test_authorization.py::test_irreversible_action_requires_human_approval_even_with_manufactured_high_confidence`,
`tests/unit/test_flow.py::test_irreversible_action_requires_human_approval_end_to_end`), and
also verified live against a real transaction (`src/policies/README.md`). **Risks:** confirmed
as anticipated — the single highest-risk phase to get wrong; the genuine remaining gaps are
idempotency verification (explicitly Phase 9's scope, not invented here) and no real
authentication/session layer yet (Phase 8's job), both honestly reported rather than
papered over with a stub that looks more complete than it is.

## Phase 8 — Security Hardening — `IMPLEMENTED` (see docs/project-status.md § Phase 8 detail)

**Objective:** the threats in `docs/security-model.md` § 2 have real mitigations, not just
documentation. **Scope:** PII redaction layer, prompt-injection defenses, tool-authorization
tests (red-team cases from `docs/guardrails.md` § 4), audit logging, security test suite.
**Deliverables:** every red-team case has an automated test that proves it fails safely.
**Delivered as:** `src/security/redaction.py` (centralized `mask_card_like()`/`redact_value()`,
now matching `docs/observability.md` § 2's documented mask format exactly, wired into every
`AuditEvent.payload` construction, not just log lines) and `tests/security/` (`test_redaction.py`,
7 tests; `test_red_team.py`, 17 tests covering every `docs/guardrails.md` § 4 case this codebase
can currently exercise) — see `src/security/README.md` and `docs/project-status.md` § Phase 8
detail for exactly what was built, found, and fixed. **Dependencies:** Phase 7. **Tests:**
`evaluation/golden_cases/prompt_injection.json` and related adversarial cases all pass — met,
plus 5 additional adversarial phrasings beyond that one fixture. **Security:** this phase's own
deliverable is security — the `review-security` skill's checklist was run manually (found and
fixed one real gap: 3 of 7 tested injection phrasings weren't caught by the original detection
patterns, fixed before this was reported done). **Exit criteria:** unsafe-action rate is 0
across the full adversarial suite (`MEASURED`, with the sample size stated) — met: **0/17**
(7 injection phrasings + 10 golden cases), explicitly labeled a small, stated sample, not a
statistically powered claim. **Risks:** confirmed as anticipated — false confidence from a
small adversarial test set; several `docs/guardrails.md` § 4 cases (conflicting policy
documents, duplicate-transaction detection, customer/account mismatch) are honestly reported as
not yet coverable rather than silently claimed, per this same risk note.

## Phase 9 — Reliability — `IMPLEMENTED` (see docs/project-status.md § Phase 9 detail)

**Objective:** the failure modes in `docs/architecture.md` § 10 are actually handled.
**Scope:** timeouts, bounded retries with backoff, fallback paths, circuit breakers where
useful, idempotency verification, the failure scenarios in `docs/demo-script.md`.
**Deliverables:** each row of `docs/architecture.md` § 10's failure-mode table has a test that
simulates the dependency failure and asserts the documented fallback occurs. **Delivered as:**
`src/orchestration/retry.py` (bounded retry + backoff for every LLM call) +
`src/orchestration/fallback.py` (the deterministic degraded path, Scenario E) +
`src/models/base.py`'s `connect_timeout` (Database unavailable) +
`src/policies/gateway.py`'s idempotency-key-aware `persist_decision()` + a new
`action_executions` table (Scenario J) — see `src/orchestration/README.md` § Reliability and
`src/policies/README.md` for exactly what was built and verified, including a real bug found
and fixed mid-implementation (a non-deferred foreign key that made the correct insert ordering
for idempotency impossible — caught by actually running it against a real database, not by
inspection). **Dependencies:** Phases 6–7. **Tests:** dependency-failure simulation tests
implemented (`tests/reliability/`: `test_retry.py`, `test_llm_fallback.py`,
`test_idempotency.py`, `test_db_timeout.py` — the last verified against a genuinely unreachable
address, not a mock) and passing. **Security:** a failure path never fails open for an
authorization-sensitive action — verified directly: a degraded case proposing an
Irreversible-risk action (a $100,000 transfer) still gets `requires_human_approval=True` through
the full fallback path (`test_degraded_result_still_goes_through_the_policy_engine`).
**Exit criteria:** Scenario E (LLM unavailable) in `docs/demo-script.md` completes via the
deterministic fallback path — met, and also verified against the actual
`evaluation/golden_cases/dependency_failure.json` fixture (previously inert documentation; its
`injected_fault` field now genuinely routes it through a failing LLM client and produces the
fixture's own expected outcome). **Risks:** confirmed as anticipated in one direction and closed
in another — reliability tests were built in full this phase, not skipped; the fraud-model
degradation half of Scenario F remains untestable because Phase 4's model was never wired into
orchestration at all (a pre-existing gap, honestly reported, not new here).

## Phase 10 — UI — `IMPLEMENTED` (see docs/project-status.md § Phase 10 detail)

**Objective:** customer, analyst, and (optionally) executive views exist. **Scope:** customer
chat view (no internal risk detail exposed), analyst view (case, evidence graph, both
explanations, audit trail, approval controls — `docs/human-oversight.md`), executive dashboard
(`OPEN QUESTION` whether to build, per `docs/product-requirements.md` § 14). Frontend
framework decided here (`docs/architecture.md` § 15, `OPEN QUESTION`). **Deliverables:**
working UI against the real API from Phases 1–9. **Delivered as:** `src/api/cases.py` (the
JSON API — `docs/api-contracts.md` § 1, previously only `/health` existed) and `src/api/ui.py` +
`templates/`/`static/` (server-rendered Jinja2 + vanilla JS, no separate framework — resolving
§ 15's `OPEN QUESTION`, see `docs/architecture.md` § 15 and `src/api/README.md` for the
reasoning). Executive dashboard: **not built**, per this phase's own risk note and the
`product-requirements.md` § 14 `OPEN QUESTION` — an explicit scope decision, not an oversight.
**Dependencies:** Phases 1–9 (needs a real API to render) — the API itself didn't exist before
this phase either (only `/health` did) and was built here as a prerequisite, wiring
`src/orchestration/live_case.py`'s `create_and_run_case()` and `src/policies/gateway.py`'s
`approve_pending_action()` to HTTP for the first time. **Tests:** `tests/unit/test_api_cases.py`
(18, offline, role-gating/validation/404s) plus manual verification in a real browser
(`.claude/rules/frontend.md`) — met. **Security:** role-shaped responses
(`CustomerCaseView`/`AnalystCaseView`) enforced server-side, verified live: a customer session
gets a real 403 on the review queue and the review endpoint, not just a hidden UI control.
**Exit criteria:** `docs/demo-script.md` Scenarios A, B, and D are drivable live through the UI,
verified in a real browser end-to-end (create case -> evidence graph with real contradictions
-> dual explanation -> approve -> status updates). **Scenario C (ask a clarifying question) is
NOT currently drivable live** — a real, honestly-reported gap found while verifying this exit
criterion: `src/orchestration/live_case.py` always sets `candidate_questions=[]` for a live
case, so `MockLLMClient.decide_next_question()` can never return `should_ask=True` for one;
`ask_question` only ever occurs for offline golden-case fixtures (which aren't wired into the
API), a pre-existing Phase 6 gap this phase's own UI testing is what surfaced, not something
Phase 10 was scoped to fix. **Risks:** confirmed as anticipated — prioritized the analyst
evidence-graph view over polish, per this phase's own risk note; a genuine persistence gap was
found and fixed along the way (`decisions.customer_explanation_es` didn't exist before this
phase — see `src/api/README.md`).

## Phase 11 — Evaluation — `IMPLEMENTED` (see docs/project-status.md § Phase 11 detail)

**Objective:** `python -m evaluation.run` produces real, non-fabricated numbers.
**Scope:** model benchmark, business benchmark, LLM evaluation, fairness evaluation, red-team
evaluation, reliability tests, baseline comparison (`docs/evaluation-plan.md` § 10).
**Deliverables:** a full evaluation report per `docs/evaluation-plan.md`, all numbers labeled
`MEASURED`/`SIMULATED`/`PROJECTED` per its § 1 rule. **Delivered as:** `evaluation/sample.py`
(the one common held-out sample — every in-window fraud transaction + a random legit sample,
an intentional, stated oversample), `baselines.py` (Rules only, Fraud ML only, LLM only,
Hybrid), `fairness.py`, `report.py`/`run.py` — see `evaluation/README.md` for the full,
live-verified result including a real, non-obvious finding (LLM-only and Hybrid produce
identical flagged sets on this sample by construction; the Policy Engine's actual, measured
effect — 19/152 cases, 12.5% — only shows up in a separate `policy_engine_override_rate`
metric). **Dependencies:** Phases 4–9. **Tests:** `tests/unit/test_evaluation.py` (20 tests,
offline) — the baseline decision functions, fairness aggregation, and binary-metrics helper,
including a fail-loudly test for a missing model artifact and a missing Phase 4 report (both
report `"not available"` with a reason, never fabricate). **Security:** none beyond not leaking
PII into the report — met; the report contains transaction/customer IDs and aggregate rates
only. **Exit criteria:** the baseline-vs-hybrid comparison has real numbers for all four
approaches, run live against the database — met (`data/reports/evaluation_report.json`).
**Risks:** confirmed and reported, not hidden — "Hybrid" here excludes the Fraud ML score (a
pre-existing gap since Phase 4), and this report says so at every place the row is mentioned,
not just once in a caveats list.

## Phase 12 — Demo

`IMPLEMENTED` (see `docs/project-status.md` § Phase 12 detail).

**Objective:** the scenarios in `docs/demo-script.md` are runnable on demand, deterministically.
**Scope:** seed data for Scenarios A–L, a `make demo` command, scripted walkthroughs.
**Dependencies:** Phases 1–11. **Tests:** each scenario has an automated assertion of its
expected outcome, run in CI. **Security:** demo data remains synthetic and clearly labeled.
**Exit criteria:** `make demo` reproduces every scenario's documented expected outcome.
**Risks:** demo scenarios drifting from actual system behavior over time — re-run them after
any Phase 4–9 change, not just before a presentation.

**Delivered as:** `demo/scenarios.py` (12 hand-written per-scenario assertions against the real
system, golden-case fixtures reused as inputs, not prose-matched — same reasoning Phase 6
already established for not auto-grading golden cases), `demo/run.py` (`make demo` /
`uv run python -m demo.run`, offline, exits non-zero only on a `FAIL` grade). **Tests:** 14
(`tests/unit/test_demo.py`), one per scenario plus two aggregate invariants. **Exit criteria
met, honestly, not by forcing a binary result:** 9/12 scenarios grade `PASS` outright, 3 grade
`PARTIAL` (each a real, already-documented, non-unsafe limitation — F's ML half, J's DB-only
proof, K's `ask_question`-not-`escalate`), 0 grade `FAIL`. Found and fixed two real bugs along
the way: a fixture (`missing_data.json`) that used a fabricated `confidence: 0.0` instead of
`null` for "Unknown," and a stale test assertion after adding the 11th golden case
(`policy_rejection.json`, Scenario L — closing a gap `evaluation/golden_cases/README.md` had
explicitly deferred). Full detail: `docs/project-status.md` § Phase 12 detail, `demo/README.md`.

## Phase 13 — Observability

`IMPLEMENTED` (see `docs/project-status.md` § Phase 13 detail).

**Objective:** `docs/observability.md` is implemented, not just described. **Scope:**
structured logs, metrics (system/ML/LLM/business), traces, dashboards, alerts.
**Dependencies:** Phases 1–9. **Tests:** a redaction test proving a raw card number/secret
never reaches a log sink. **Security:** this phase directly implements `docs/observability.md`
§ 2's redaction rule — treat any failure here as security-severity, not cosmetic.
**Exit criteria:** an incident can be reconstructed from traces + audit log alone
(`docs/observability.md` § 5), demonstrated on a seeded scenario. **Risks:** observability is
often built last and rushed — its redaction correctness is a hard security requirement, not
optional polish; do not compress this phase's test coverage under time pressure.

**Delivered as:** `src/monitoring/metrics.py` (real Prometheus counters/histograms at real call
sites) + `src/monitoring/tracing.py` (a small custom span recorder instead of the OpenTelemetry
SDK originally listed in `CLAUDE.md` § 5 — `docs/decisions/ADR-0001-tracing-without-opentelemetry.md`)
+ `GET /metrics` + `infrastructure/prometheus/`, `infrastructure/grafana/` (behind
docker-compose's optional `monitoring` profile). **Tests:** 15
(`tests/unit/test_metrics.py` 9, `tests/unit/test_tracing.py` 6 — including the required
redaction-proof test, extended to the new trace-span emission point). **Exit criteria met,
verified live against a real Postgres, not simulated:** a case created through the API with a
known `X-Correlation-ID` was reconstructed from its trace spans (grep by `trace_id` in the
container's log stream) plus one `audit_events` query by the same `correlation_id` — see
`src/monitoring/README.md` § Incident reconstruction for the exact commands and output. Also
fixed, in the same verification pass, the Phase 10-documented gap where
`AuditEvent.correlation_id` was always `None`. Two real bugs found and fixed while verifying
this phase (not merely anticipated): a database-unreachable timeout that `connect_timeout` alone
didn't actually bound (DNS resolution ahead of the TCP connect took as long as ~60s), and a
metrics-collector duplicate-registration bug that serialized that latency N times into one
scrape — both detailed in `src/monitoring/README.md`. Full detail:
`docs/project-status.md` § Phase 13 detail.

## Phase 14 — Deployment Readiness (documentation only for this competition)

`IMPLEMENTED` (see `docs/project-status.md` § Phase 14 detail).

**Objective:** an honest account of what remains before real deployment. **Scope:** document
(not build) container/infra requirements, rollback plan, operational readiness checklist,
capacity limits, monitoring plan, access-control plan, data-retention plan, remaining
deployment work. **Dependencies:** all prior phases, to have something real to assess.
**Deliverables:** an honest "what's left before production" section in the final report
(`prompt.md` § 64) — not a deployment. **Security:** no production action is taken in this
phase, ever, without explicit user authorization for that specific action
(`CLAUDE.md` § 7). **Exit criteria:** the final report can answer, for each item in
`prompt.md` § 58 ("What happens if...?"), either "implemented, see X" or "documented gap, see
Y" — never silence. **Risks:** none technical; the risk is skipping the honesty requirement
under demo-day pressure.

**Delivered as:** `docs/final-report.md` (the `prompt.md` § 64 report, all 13 required sections,
plus a "Production readiness" section answering every § 58 item — the exit criterion, met
explicitly, item by item, never silently) and `docs/deployment-readiness.md` (the detailed
infra/rollback/operational-readiness/capacity/monitoring/access-control/retention gap analysis
with a concrete, dependency-ordered remaining-work list). Documentation only, as scoped — no
production action was taken. While writing it, found and fixed one more narrow instance of a
correlation-ID gap Phase 13 had already fixed elsewhere (`src/evidence/persist.py`, the same
pattern as `src/policies/gateway.py`) and corrected two stale forward-looking docs
(`docs/api-contracts.md`'s `GET /metrics` status, `docs/architecture.md`'s pre-implementation
header). Full detail: `docs/project-status.md` § Phase 14 detail.

## Phase 15 — Fraud ML Score Wiring (beyond the original roadmap)

`IMPLEMENTED` (see `docs/project-status.md` § Phase 15 detail). Not one of the original 14
competition-roadmap phases — added at the user's explicit request after Phase 14 closed, having
identified it as the project's single most-referenced open gap and the highest-leverage next
step regardless of which tool eventually trains the model.

**Objective:** consult the trained fraud ML model's score (Phase 4) at live decision time,
closing the gap every one of Phases 4/6/7/9/11/13 had to honestly flag. **Scope:** a cached
live-scoring module (`src/ml/score.py`), carrying the score through `CaseInput`/`CaseResult`,
reading it in the Policy Engine's action-risk classification (`docs/decision-policy.md` § 5's
risk bands, finally wired to a real score), persisting `decisions.model_degraded` (a column
that has existed since Phase 9), and feeding the same score into the Phase 11 evaluation's
Hybrid baseline. **Dependencies:** Phase 4 (the trained artifact), Phase 7 (the Policy Engine),
Phase 9 (the `model_degraded` column), Phase 11 (the evaluation pipeline to re-run).
**Tests:** an allow/deny pair for the new fraud-score override (mirroring the existing
amount-based one), end-to-end propagation of `model_degraded` through every `CaseResult`
construction path, and a regression test that `None` (no live score) leaves today's behavior
unchanged. **Security:** none — no new trust boundary; the score can only ever escalate
action-risk, never downgrade it, same shape as every other override in
`src/policies/action_risk.py`. **Exit criteria:** a real transaction scores correctly and the
score changes an authorization outcome when manufactured high enough to (unit-tested); live
verification against a real database that both a real score and a model-unavailable path
persist correctly. **Risks:** a missing model artifact must degrade visibly
(`model_degraded=True`), never silently skip risk assessment — the same "never fail open" rule
every other dependency failure in this project already follows.

**Delivered as:** `src/ml/score.py` (new — cached scoring, documented one-process-lifetime
staleness tradeoff), `src/ml/model.py::predict_single`, `CaseInput.fraud_model_score`/
`.model_degraded`, `src/policies/action_risk.py::_fraud_score_override`,
`src/policies/config.py`'s two new thresholds (0.70/0.90 — the exact illustrative numbers
`docs/decision-policy.md` § 5 wrote before any model existed to feed them), wired through
`src/orchestration/live_case.py`, persisted by `src/policies/gateway.py`, metered by
`src/monitoring/metrics.py` (`FRAUD_MODEL_SCORE`, `CASES_MODEL_DEGRADED_TOTAL`), and fed into
`evaluation/sample.py`'s `EvalCase`s. **Exit criteria met, verified live against a real
Postgres, not simulated**: a real transaction scored `0.4898` (`model_degraded=False`,
confirmed persisted via direct `SELECT`); the same transaction with the model artifact
temporarily removed produced `model_degraded=True`. **A real, honestly-reported finding from
re-running the Phase 11 evaluation afterward**: the Hybrid row's numbers came back completely
unchanged (`policy_engine_override_rate` still 19/152) — not because the wiring is inert, but
because every `fraud_model_score` on the live 152-case sample falls in a narrow band
(~0.3997–0.5274) that never crosses either configured threshold, a direct, measured consequence
of the Phase 4 finding that this model performs near chance. Also upgraded `demo/scenarios.py`
Scenario F from `PARTIAL` to `PASS` (10/12 PASS, 2/12 PARTIAL, 0/12 FAIL overall) and corrected
a deviation found along the way: `docs/demo-script.md`'s original Scenario F spec described a
fallback to the logistic-regression baseline on model failure; the actual implementation
degrades straight to no live score at all — noted, not silently implemented differently.
16 new tests, 194 total. Full detail: `docs/project-status.md` § Phase 15 detail.

## Phase 16 — Device/IP-Novelty Features from `digital_events` (beyond the original roadmap)

`IMPLEMENTED` (see `docs/project-status.md` § Phase 16 detail). Not one of the original 14
competition-roadmap phases — added at the user's own request after their independent root-cause
analysis of the Phase 4 near-chance finding converged on the same hypothesis this project's own
`src/ml/features.py` had already documented (`NOT_IMPLEMENTED_FEATURES`).

**Objective:** test whether device/IP novelty signals from `digital_events` recover the fraud
signal the current 15 features don't carry. **Scope:** widen the `digital_events` ingestion
window (7 → 30 days, a deliberately smaller step than the full 90 days after a memory-risk
assessment), add leakage-safe device/IP-novelty/country-deviation features via `pd.merge_asof`,
retrain, and re-evaluate. **Dependencies:** Phase 4 (the training pipeline), Phase 5 (the device
fingerprint function, reused not reimplemented), Phase 15 (the live-scoring cache that
automatically picks up the retrained model). **Tests:** leakage safety (a session after the
transaction must never be used, even within the Evidence Engine's own wider window), novelty
correctness across repeat sessions, honest `NaN` defaults when no data/signal exists.
**Security:** none — no new trust boundary. **Exit criteria:** the retrained model's metrics
and feature importances are measured and compared against the Phase 4 baseline, honestly,
whichever way the comparison goes. **Risks:** the hypothesis might not pan out — stated in the
plan before implementation, not added after the fact to excuse a disappointing result.

**Delivered as:** `src/ml/dataset.py::load_digital_events`, `src/ml/features.py::
_digital_session_features` (four new columns: `has_digital_session`, `device_novelty`,
`ip_novelty`, `digital_country_deviation`), `MODEL_VERSION`/`FEATURE_VERSION` bumped to
`v0.2.0`, all 3 real call sites updated (`train.py`, `evaluation/sample.py`, `src/ml/score.py`).
**Exit criteria met — and the honest, measured result is negative:** re-ingesting
`digital_events` for 30 days (409,785 rows) and retraining found that only **99 of 370,998
transactions (0.027%)** matched a digital session within the leakage-safe ±2h backward window —
only ~29% of customers ever appear in `digital_events` at all, averaging ~9 events across the
whole window, far too sparse for the model to learn anything from (SHAP importance `0.0` for
all four new features; test ROC-AUC moved from 0.502 to 0.481, a small shift attributable to
retraining noise, not a real effect). Diagnosed as a structural sparsity issue, not a
window-size one — a wider 90-day window would not plausibly change this conclusion, verified by
checking the match rate *within* the already-overlapping window alone. Re-running the Phase 11
evaluation produced numbers identical to Phase 15's. **Conclusion, reported exactly as the user
asked:** the "signal lives in `digital_events`" hypothesis is not supported by this dataset via
this approach — a closed, honestly-reported negative result, the same rigor this project
already applied to the original 15 features in Phase 4. 8 new tests, 202 total. Full detail:
`docs/project-status.md` § Phase 16 detail.
