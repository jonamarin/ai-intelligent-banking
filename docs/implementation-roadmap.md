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

## Phase 3 — Synthetic Data / Ingestion

**Objective:** the LATAM Bank dataset is loaded and usable. **Scope:** ingestion pipeline for
the tables listed in `docs/data-dictionary.md` § Tables not used excluded initially;
data-quality validation per `docs/data-lineage.md` § 7; a data-quality report. **Deliverables:**
`customers`, `products`, `branches`, `service_agents`, `transactions`,
`call_center_interactions`, `call_transcripts`, `digital_events`, `complaints`,
`daily_exchange_rates` loaded into PostgreSQL; data-quality report generated.
**Dependencies:** Phase 2; the raw dataset files must be obtained (not present in this
repository as of this writing). **Tests:** schema validation, duplicate/null-rate checks
against the documented baselines (`docs/data-lineage.md` § 2). **Security:** confirm no real
data snuck into the "synthetic" dataset before loading (sanity check, not expected to find
anything). **Exit criteria:** the fraud model (Phase 4) can query real feature inputs from the
loaded tables. **Risks:** the ~19M-row scale may be too large for a laptop-only Postgres for
local dev — consider a sampled subset for local development, full set for any batch
evaluation; document the choice if made.

## Phase 4 — Fraud ML

**Objective:** a working, evaluated fraud/risk model. **Scope:** baseline
(logistic regression/rules) + main model (XGBoost/LightGBM) per
`docs/model-evaluation.md` §§ 2–4; SHAP explainability; model versioning. **Deliverables:**
trained model artifact + evaluation report (`docs/evaluation-plan.md` § 2 metrics, `MEASURED`
and labeled with the actual temporal split used). **Dependencies:** Phase 3. **Tests:**
feature unit tests, leakage checks (`fraud_score`/`is_fraud` never used as an input),
calibration check. **Security:** none beyond standard data handling. **Exit criteria:** a
documented, reproducible evaluation report exists with real numbers, not placeholders.
**Risks:** the synthetic `is_fraud` label distribution may be unrealistic (e.g., too easy or
too hard to predict) — report this honestly rather than tuning to an artificially easy target.

## Phase 5 — Evidence Engine

**Objective:** the evidence graph is real. **Scope:** evidence extraction from retrieved data,
graph construction (`docs/domain-model.md` § Evidence Graph), provenance stamping,
contradiction detection, uncertainty representation. **Deliverables:** given a case, produce a
structured evidence graph with `direction`/`confidence`/`provenance` on every node/edge.
**Dependencies:** Phases 2–4. **Tests:** unit tests per evidence-extraction rule; a
contradiction-detection test using two conflicting signals. **Security:** evidence records are
append-only — no update/delete tool exists (`docs/guardrails.md` § 4, "delete the fraud
evidence" red-team case). **Exit criteria:** the example graph shape in `prompt.md` § 10 is
reproducible from real data for at least one seeded case. **Risks:** contradiction detection
is easy to over- or under-trigger; validate against hand-authored golden cases
(`evaluation/golden_cases/conflicting_evidence.json`) before trusting it.

## Phase 6 — AI Agent (Conversation + Orchestration)

**Objective:** the LLM-driven parts work, in both mock and real-provider mode. **Scope:**
intent detection, entity extraction, orchestration state machine, structured outputs, tool
definitions (`prompt.md` § 16), RAG over policy documents, Next-Best-Question gate
(`docs/architecture.md` § 8). **Deliverables:** a case can be driven end-to-end by a scripted
mock-mode conversation without any external API key. **Dependencies:** Phases 2, 5.
**Tests:** structured-output schema tests; tool-call-shape tests; RAG groundedness spot-check.
**Security:** tool calls are proposals only at this phase — the Action Gateway (Phase 7) is
what authorizes them; do not let this phase's orchestrator execute anything directly.
**Exit criteria:** `LLM_MODE=mock` produces deterministic, reproducible output for each
`evaluation/golden_cases/` scenario. **Risks:** building the orchestrator before the policy
engine (Phase 7) exists risks accidentally wiring direct execution — sequence matters here;
don't skip ahead.

## Phase 7 — Policy Engine

**Objective:** the deterministic authorization path is real. **Scope:** action classification
(`docs/decision-policy.md` § 6), configurable risk-band thresholds, tool authorization chain
(`docs/architecture.md` § 6), human-escalation triggers, critical-action restrictions.
**Deliverables:** every tool call from Phase 6 now passes through real authorization code, not
a stub. **Dependencies:** Phases 4–6. **Tests:** every guardrail row in `docs/guardrails.md`
§ 2 has a corresponding test; the tool-authorization chain (`docs/guardrails.md` § 3) is
tested with both allow and deny paths for each stage. **Security:** this phase is the one
that actually makes § 7 of `CLAUDE.md` true — treat it as the highest-scrutiny code in the
project; review it explicitly with the `review-security` skill before considering it done.
**Exit criteria:** Scenario D (critical/irreversible action) in `docs/demo-script.md` requires
human approval regardless of a manufactured high-confidence AI recommendation, provably (a
test that tries to bypass it and fails). **Risks:** the single highest-risk phase to get wrong
— a bug here means an unauthorized financial action, not just a wrong answer.

## Phase 8 — Security Hardening

**Objective:** the threats in `docs/security-model.md` § 2 have real mitigations, not just
documentation. **Scope:** PII redaction layer, prompt-injection defenses, tool-authorization
tests (red-team cases from `docs/guardrails.md` § 4), audit logging, security test suite.
**Deliverables:** every red-team case has an automated test that proves it fails safely.
**Dependencies:** Phase 7. **Tests:** `evaluation/golden_cases/prompt_injection.json` and
related adversarial cases all pass. **Security:** this phase's own deliverable is security —
use the `review-security` skill and the `security-reviewer` agent before marking it done.
**Exit criteria:** unsafe-action rate is 0 across the full adversarial suite (`MEASURED`, with
the sample size stated). **Risks:** false confidence from a small adversarial test set — state
sample size and limitations explicitly (`docs/evaluation-plan.md` § 1).

## Phase 9 — Reliability

**Objective:** the failure modes in `docs/architecture.md` § 10 are actually handled.
**Scope:** timeouts, bounded retries with backoff, fallback paths, circuit breakers where
useful, idempotency verification, the failure scenarios in `docs/demo-script.md`.
**Deliverables:** each row of `docs/architecture.md` § 10's failure-mode table has a test that
simulates the dependency failure and asserts the documented fallback occurs.
**Dependencies:** Phases 6–7. **Tests:** dependency-failure simulation tests (LLM timeout,
DB down, malformed model output, etc.). **Security:** a failure path must never fail open for
an authorization-sensitive action (`docs/architecture.md` § 10). **Exit criteria:** Scenario E
(LLM unavailable) in `docs/demo-script.md` completes via the deterministic fallback path.
**Risks:** reliability tests are easy to skip under time pressure — don't; they're part of the
project's actual differentiator per the competition brief ("Build For Failure").

## Phase 10 — UI

**Objective:** customer, analyst, and (optionally) executive views exist. **Scope:** customer
chat view (no internal risk detail exposed), analyst view (case, evidence graph, both
explanations, audit trail, approval controls — `docs/human-oversight.md`), executive dashboard
(`OPEN QUESTION` whether to build, per `docs/product-requirements.md` § 14). Frontend
framework decided here (`docs/architecture.md` § 15, `OPEN QUESTION`). **Deliverables:**
working UI against the real API from Phases 1–9. **Dependencies:** Phases 1–9 (needs a real
API to render). **Tests:** basic UI smoke tests; manual verification per the "test the golden
path in a browser" standard. **Security:** UI never renders more certainty than the backend
evidence supports (`docs/domain-model.md` § 4); customer view never leaks internal risk
scores/evidence. **Exit criteria:** all four demo scenarios (`docs/demo-script.md`
Scenarios A–D) are drivable through the UI, not just the API. **Risks:** UI work can balloon
past the time budget — prioritize the analyst evidence-graph view (the project's visual
centerpiece, `prompt.md` § 36) over polish elsewhere.

## Phase 11 — Evaluation

**Objective:** `python -m evaluation.run` produces real, non-fabricated numbers.
**Scope:** model benchmark, business benchmark, LLM evaluation, fairness evaluation, red-team
evaluation, reliability tests, baseline comparison (`docs/evaluation-plan.md` § 10).
**Deliverables:** a full evaluation report per `docs/evaluation-plan.md`, all numbers labeled
`MEASURED`/`SIMULATED`/`PROJECTED` per its § 1 rule. **Dependencies:** Phases 4–9.
**Tests:** the evaluation run itself, plus a test that it fails loudly (not silently) when a
required input is missing. **Security:** none beyond not leaking PII into the report.
**Exit criteria:** the baseline-vs-hybrid comparison (`docs/evaluation-plan.md` § 10) has real
numbers for all four approaches. **Risks:** temptation to round up or omit unfavorable
numbers — don't; `docs/evaluation-plan.md` § 1 requires honest labeling including failures.

## Phase 12 — Demo

**Objective:** the scenarios in `docs/demo-script.md` are runnable on demand, deterministically.
**Scope:** seed data for Scenarios A–L, a `make demo` command, scripted walkthroughs.
**Dependencies:** Phases 1–11. **Tests:** each scenario has an automated assertion of its
expected outcome, run in CI. **Security:** demo data remains synthetic and clearly labeled.
**Exit criteria:** `make demo` reproduces every scenario's documented expected outcome.
**Risks:** demo scenarios drifting from actual system behavior over time — re-run them after
any Phase 4–9 change, not just before a presentation.

## Phase 13 — Observability

**Objective:** `docs/observability.md` is implemented, not just described. **Scope:**
structured logs, metrics (system/ML/LLM/business), traces, dashboards, alerts.
**Dependencies:** Phases 1–9. **Tests:** a redaction test proving a raw card number/secret
never reaches a log sink. **Security:** this phase directly implements `docs/observability.md`
§ 2's redaction rule — treat any failure here as security-severity, not cosmetic.
**Exit criteria:** an incident can be reconstructed from traces + audit log alone
(`docs/observability.md` § 5), demonstrated on a seeded scenario. **Risks:** observability is
often built last and rushed — its redaction correctness is a hard security requirement, not
optional polish; do not compress this phase's test coverage under time pressure.

## Phase 14 — Deployment Readiness (documentation only for this competition)

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
