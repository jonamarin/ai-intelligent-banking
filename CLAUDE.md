# CLAUDE.md — Project Operating Contract

This file is the persistent instruction set for every Claude Code session working in this
repository. Read it before making changes. It is deliberately concise — details live in
`docs/`, `.claude/rules/`, `.claude/skills/`, and `.claude/agents/`, which this file links to
rather than duplicates.

## 1. What this project is

**AI Fraud & Dispute Investigator** — an AI-first banking customer-service system focused on
one workflow: **transaction-dispute intake and fraud investigation** (a customer reports an
unrecognized or suspicious transaction; the system investigates, gathers evidence, and either
resolves safely, asks a targeted question, or escalates to a human).

This is a submission for the Factored Datathon 2026 challenge (see `prompt.md` and
`project_presentation.txt`). It is a working prototype demonstrating production-oriented
thinking, not a production banking system. See `docs/product-requirements.md` for full scope
and non-goals.

Data source: the synthetic **LATAM Bank Dataset** (Mexico, Colombia, Argentina; Spanish
language; 13 tables, ~19M rows) — see `docs/data-dictionary.md`. No real customer or financial
data exists anywhere in this repository.

## 2. Core operating principle

> **AI proposes. Evidence supports. Policy constrains. Humans control high-impact decisions.**

Every component maps to one part of this sentence:

| Sentence part | Owning layer | Doc |
|---|---|---|
| AI proposes | LLM (intent, entities, hypotheses, explanations) + ML (risk scores) | `docs/architecture.md` |
| Evidence supports | Evidence engine, evidence graph, provenance | `docs/domain-model.md` |
| Policy constrains | Deterministic policy engine, tool authorization | `docs/decision-policy.md`, `docs/guardrails.md` |
| Humans control high-impact decisions | Escalation, approval matrix | `docs/human-oversight.md` |

A model prediction is not a policy decision. A policy decision is not necessarily a human
decision. AI confidence is never authorization. See `docs/decision-policy.md` for the full
decision flow and `docs/guardrails.md` for how each stage is actually enforced (not just
described in a prompt).

## 3. Architecture at a glance

```
Customer → Channel → API Gateway → Conversation Intelligence (LLM)
                                          ↓
                                   Case Orchestrator
                                    ↓            ↓
                          Data Retrieval    Policy Retrieval
                                    ↓            ↓
                                Evidence Engine
                                      ↓
                              Fraud/Risk Models (ML)
                                      ↓
                               Decision Engine (deterministic policy)
                            ↓          ↓            ↓
                      Auto-Resolve  Ask Customer  Human Review
                            ↓          ↓            ↓
                              Action Gateway (tool authorization)
                                      ↓
                              Audit + Monitoring
```

Full detail, failure modes, and AI/ML/deterministic responsibility boundaries:
`docs/architecture.md`.

## 4. Repository map

```
CLAUDE.md                   ← this file
README.md                   ← project overview, setup, status
prompt.md                   ← original master prompt (historical input, see docs/decisions/README.md precedence note)
project_presentation.txt    ← competition brief (constraints, judging criteria)
LATAM_Bank_*.pdf            ← source dataset documentation (do not duplicate — see docs/data-dictionary.md)

.claude/
  settings.json              ← shared, conservative Claude Code settings
  rules/                     ← path/topic-scoped engineering rules
  skills/                    ← task workflows (implement-feature, investigate-fraud, ...)
  agents/                    ← specialized subagent roles
  hooks/                     ← deterministic dev-safety checks (see hooks/README.md for limits)

docs/
  product-requirements.md    ← what the product must do (owns requirements)
  architecture.md             ← how the system is structured (owns architecture)
  domain-model.md             ← entities: fact vs evidence vs hypothesis vs decision
  decision-policy.md          ← how a recommendation becomes an authorized action
  security-model.md           ← threat model, trust boundaries
  guardrails.md               ← runtime enforcement mechanisms
  human-oversight.md          ← approval matrix, escalation, override
  evaluation-plan.md          ← system-level evaluation strategy
  model-evaluation.md         ← ML/LLM-specific evaluation methodology
  observability.md            ← logs, metrics, traces, redaction rules
  api-contracts.md            ← proposed API/event boundaries
  data-governance.md          ← data classification, retention, PII rules
  data-lineage.md             ← where data comes from and how it's transformed
  data-dictionary.md          ← greppable translation of the LATAM Bank schema
  implementation-roadmap.md   ← phased build plan for a future session
  project-status.md           ← what is actually implemented right now
  demo-script.md               ← deterministic demo scenarios
  final-report.md              ← Phase 14: the concise prompt.md § 64 engineering report
  deployment-readiness.md      ← Phase 14: honest "what's left before production" (docs only)
  decisions/                   ← ADRs

evaluation/                    ← system-level evaluation (implemented, Phase 11) — `python -m evaluation.run`
  golden_cases/                ← synthetic scenario fixtures + schema (11 fixtures, Scenarios A-L)
  sample.py, baselines.py, fairness.py, report.py, run.py
                               ← Rules/ML/LLM/Hybrid baseline comparison, fairness, full report

demo/                           ← scripted, graded demo-script.md walkthrough (implemented, Phase 12)
  scenarios.py, run.py          ← per-scenario PASS/PARTIAL/FAIL assertions; `python -m demo.run` / `make demo`

src/                           ← application code (Phase 1+, docs/project-status.md)
  config/                      ← settings + structured logging (implemented)
  api/                         ← FastAPI app, health check, error handling, case JSON API, server-rendered UI (implemented, Phase 1, 10)
  models/                      ← SQLAlchemy models + Pydantic schemas (implemented, Phase 2-3)
  ingestion/                    ← CSV -> Postgres loader + data-quality report (implemented, Phase 3)
  ml/                           ← fraud model: features, baseline, XGBoost, evaluation (implemented, Phase 4); score.py: cached live scoring (implemented, Phase 15)
  evidence/                     ← device derivation, evidence graph, contradiction detection (implemented, Phase 5)
  agents/                       ← structured LLM output schemas + LLMClient/MockLLMClient (implemented, Phase 6)
  retrieval/                    ← TF-IDF policy RAG + synthetic Spanish policy docs (implemented, Phase 6)
  tools/                        ← read tools (execute directly) + action tools (proposal-only) (implemented, Phase 6)
  orchestration/                ← case state machine, golden/live case loaders, retry/fallback (implemented, Phase 6-7, 9); live_case.py now scores every live case (Phase 15)
  policies/                     ← action-risk classification (now fraud-score-aware, Phase 15), config, tool-authorization chain, idempotency-aware Decision/AuditEvent/HumanReview gateway (implemented, Phase 7, 9)
  security/                     ← centralized PII/secret redaction layer (implemented, Phase 8)
  monitoring/                   ← Prometheus metrics + custom tracer + GET /metrics wiring (implemented, Phase 13)

alembic/                       ← migrations (implemented, Phase 2-3, 9) — env.py reads
                                  src.config.settings + src.models.Base.metadata
infrastructure/                 ← Prometheus scrape/alert config + Grafana provisioning (Phase 13) —
                                  optional docker-compose `monitoring` profile, `make monitoring-up`
tests/unit/                    ← 146 passing tests (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5 Phase 4 + 13 Phase 5 + 10 Phase 6 + 20 Phase 7 − 4 superseded, moved to tests/security/, + 18 Phase 10 API tests + 20 Phase 11 evaluation tests + 14 Phase 12 demo tests + 15 Phase 13 metrics/tracing tests + 15 Phase 15 fraud-score-wiring tests)
tests/security/                ← 24 passing tests (Phase 8: redaction + red-team/adversarial suite)
tests/reliability/             ← 24 passing tests (Phase 9: retry/fallback, idempotency, DB-timeout; + 1 Phase 15 model_degraded test)
data/models/                   ← trained model artifacts (git-ignored — binary)
pyproject.toml, uv.lock, Dockerfile, docker-compose.yml, Makefile,
.github/workflows/ci.yml, .pre-commit-config.yaml, .env.example
                               ← Phase 1 foundation tooling
```

Repository initialization, Phase 1 — Foundation, Phase 2 — Domain, Phase 3 — Ingestion
(sample mode), Phase 4 — Fraud ML, Phase 5 — Evidence Engine, Phase 6 — AI Agent /
Orchestration, Phase 7 — Policy Engine, Phase 8 — Security Hardening, Phase 9 — Reliability,
Phase 10 — UI, Phase 11 — Evaluation, Phase 12 — Demo, Phase 13 — Observability, and Phase 14 —
Deployment Readiness are all done (`docs/project-status.md`). Phase 14 is documentation only,
per its own scope (`docs/implementation-roadmap.md`) — `docs/final-report.md` (the concise
`prompt.md` § 64 report, including the § 58 "what happens if..." checklist) and
`docs/deployment-readiness.md` (the detailed infra/rollback/access-control/retention gap
analysis); no production infrastructure was created or touched. **Phase 15** (beyond the
original 14-phase roadmap, `docs/project-status.md` § Phase 15 detail) wired the trained fraud
ML model's score into live orchestration — `src/ml/score.py`.
`infrastructure/terraform/` and every deployment mechanism `docs/deployment-readiness.md`
describes as missing (§ 1–8 of that document) do not exist yet — do not create empty placeholder
directories for a phase before it actually starts; the existing `src/` subpackages that are
still just markers document this explicitly in their own docstrings. A `--full` ingestion run
(the entire ~19M-row dataset, not just the
verified recent-date sample) has also not been done — see `src/ingestion/README.md` § Sample vs.
full mode before attempting it. **The trained fraud model performs near chance on the currently
loaded sample — a real, verified finding, not a bug** (`docs/project-status.md` § Phase 4
detail, `src/ml/README.md`). **The Evidence Engine's `device_id` is a documented heuristic
proxy, not a true device fingerprint** — the dataset has no persistent device identifier
(`src/evidence/README.md`). Evidence Engine direction/confidence values are illustrative
heuristics, never approved policy. **Phase 7's Policy Engine (`src/policies/`) now makes every
tool call from Phase 6 pass through a real, deterministic authorization chain** — action-risk
is classified from fixed code + the case's own transaction facts, never from the LLM;
Irreversible/Critical actions require human approval unconditionally, with a test that tries to
bypass this and fails (`docs/demo-script.md` Scenario D, `src/policies/README.md`). **Phase 8's
`src/security/redaction.py` is the single shared PII/secret redaction implementation** — wired
into every `AuditEvent.payload` write (not just log lines) — and `tests/security/test_red_team.py`
automates every `docs/guardrails.md` § 4 red-team case this codebase can currently exercise
(0/17 unsafe actions, measured — `src/security/README.md`). **Phase 9 closed the last major
documented gap: real idempotency.** `src/tools/base.py`'s `ToolProposal.idempotency_key` flows
into `src/policies/gateway.py`'s `persist_decision()`, which reserves it in a new
`action_executions` table via `INSERT ... ON CONFLICT DO NOTHING RETURNING` — a database-level
race, verified live (two calls with the same key -> one `Decision` row, one `action.executed`
event). Phase 9 also wraps every LLM call in bounded retry-then-deterministic-fallback
(`src/orchestration/retry.py`/`fallback.py`, `CaseResult.llm_degraded`,
`docs/demo-script.md` Scenario E) and bounds the database-connect timeout so "DB unavailable"
fails clearly instead of hanging. **Genuine remaining gaps, honestly reported, not papered
over:** a real authentication/session layer is explicitly **out of scope for this prototype**
(`docs/security-model.md` § 3: "use a trusted test session/identity abstraction"); risk-band
fraud-probability thresholds (`docs/decision-policy.md` § 5) are now wired in (Phase 15,
`src/ml/score.py`) and `decisions.model_degraded` is finally set to real values — but on the
live evaluation sample this model's near-chance scores never cross either configured threshold,
so the wiring has zero measured effect there (honestly reported, not hidden —
`docs/project-status.md` § Phase 15 detail); `evaluation/golden_cases/duplicate_action.json` still
doesn't pass end-to-end (the idempotency mechanism is proven; the mock LLM's intent detection
doesn't map that fixture's message to a `freeze_card` call — a Phase 6 gap). `call_transcripts`
currently has **0 rows** in the live database (verified during Phase 6) despite earlier
documentation claiming a 3-day sample — see `docs/project-status.md` § Known limitations before
relying on it. **Phase 10 built the first real API (`src/api/cases.py`, previously only
`/health` existed) and a server-rendered customer/analyst UI on top of it
(`src/api/ui.py` + `templates/`/`static/` — Jinja2 + vanilla JS, no separate frontend
framework, resolving `docs/architecture.md` § 15's `OPEN QUESTION` — see `src/api/README.md`).**
Role-shaped responses are enforced server-side (a customer session gets a real 403 on the
review queue and review endpoint, verified live). `docs/demo-script.md` Scenarios A, B, and D
are drivable live through a real browser, verified end-to-end; **Scenario C (ask a clarifying
question) is not** — `src/orchestration/live_case.py` always sets `candidate_questions=[]`, so
a live case can never produce `ask_question`, a pre-existing Phase 6 gap this phase's own UI
testing surfaced. `CaseExplanation.customer_explanation_es` was never persisted before this
phase (only `analyst_explanation` was) — fixed via a migration that also backfills existing
rows rather than dropping them. **Phase 11's `python -m evaluation.run`
(`docs/evaluation-plan.md` § 9) compares Rules-only, Fraud-ML-only, LLM-only, and the Hybrid
pipeline on one common held-out sample** (`evaluation/sample.py`/`baselines.py`) — a real,
non-obvious finding from running it: "LLM only" and "Hybrid" produce identical flagged outcomes
on the sample (the Policy Engine never changes *which* action gets proposed, only *whether
human approval is independently required*), so its actual effect is a separate
`policy_engine_override_rate` metric (**measured: 19/152, 12.5%**), not visible in the
precision/recall comparison alone — see `evaluation/README.md`. Business metrics are honestly
`"not available"` (no approved cost coefficients exist), never a fabricated dollar figure.
**Phase 12's `python -m demo.run` (`make demo`) runs and grades all 12
`docs/demo-script.md` scenarios offline** — `demo/scenarios.py` holds one hand-written,
falsifiable assertion per scenario (not a prose-matching grader against the golden cases' own
`expected_*` fields — same reasoning Phase 6 already established). Result (updated by Phase 15's
Scenario F fix, below): 10/12 `PASS`, 2/12
`PARTIAL` (each a real, already-documented, non-unsafe limitation — see `demo/README.md`), 0
`FAIL`. Building it surfaced and fixed a real fixture bug (`missing_data.json` used a fabricated
`confidence: 0.0` instead of `null` for "Unknown," contradicting `src/evidence/graph.py`'s own
documented convention) and added the previously-deferred `policy_rejection.json` fixture
(Scenario L), extending `golden_case_loader.py` to read `case_status`/`transaction_type` from a
fixture so it can exercise the Policy Engine's case-eligibility denial path.
**Phase 13's `src/monitoring/` wires real Prometheus metrics (`GET /metrics`) and a lightweight
custom tracer** (`src/monitoring/tracing.py` — not the OpenTelemetry SDK this file used to list,
see § 5 and `docs/decisions/ADR-0001-tracing-without-opentelemetry.md`) into every LLM call, tool
authorization, and HTTP request, plus an optional Prometheus/Grafana docker-compose profile
(`make monitoring-up`). **Fixed, live-verified, the Phase 10-documented gap** where
`AuditEvent.correlation_id` was always `None` — a real case created through the API was fully
reconstructed from its trace spans (grep by `trace_id`) plus one `audit_events` query by the same
correlation ID, with no raw PII needed (`src/monitoring/README.md` § Incident reconstruction).
**Two real bugs found and fixed while verifying this phase**: a database-unreachable timeout
that `connect_timeout` alone didn't actually bound (DNS resolution ahead of the TCP connect took
as long as ~60s on this machine), and a metrics-collector duplicate-registration bug that
serialized that latency N times into one scrape — both in `src/monitoring/metrics.py`, detailed
in `src/monitoring/README.md`.
**Phase 14 (documentation only, `docs/implementation-roadmap.md`) wrote the two deliverables
that phase's own scope calls for**: `docs/final-report.md` (the concise `prompt.md` § 64
engineering report — Architecture through Demo, plus a section answering every `prompt.md` § 58
"what happens if..." item as "implemented, see X" or "documented gap, see Y", this phase's own
exit criterion) and `docs/deployment-readiness.md` (the detailed infra/rollback/operational-
readiness/capacity/monitoring/access-control/retention gap analysis, with a concrete, ordered
"remaining deployment work" list). No production action, deployment, or infrastructure change
was taken. While synthesizing the report, one more narrow instance of the same Phase 10 gap
Phase 13 had already fixed in `src/policies/gateway.py` was found and fixed the same way:
`src/evidence/persist.py`'s `AuditEvent.correlation_id` was still always `None` (evidence-graph
writes are outside the request/response cycle golden cases and background builds use, so
Phase 13's own live verification hadn't exercised that specific write path).
**Phase 15 (beyond the original 14-phase roadmap, `docs/project-status.md` § Phase 15 detail)
wired the trained fraud ML model's score into live orchestration** — `src/ml/score.py` scores
one transaction via a cached, once-per-process feature build (the same `build_features` call
training uses — no duplicated feature logic); `CaseInput.fraud_model_score`/`.model_degraded`
carry it into `src/policies/action_risk.py`'s new fraud-score override (the exact risk-band
thresholds `docs/decision-policy.md` § 5 always specified, 0.70/0.90, finally read by code).
Verified live, twice: a real transaction scored `0.4898` (`model_degraded=False`, persisted);
the same run with the model artifact temporarily removed correctly produced `model_degraded=True`.
**A real, honestly-reported finding from re-running the Phase 11 evaluation afterward**: the
Hybrid row's numbers came back completely unchanged — every `fraud_model_score` on the live
152-case sample falls in a narrow band (~0.40–0.53) that never crosses either threshold, a
direct, measured consequence of the Phase 4 near-chance finding. The mechanism is real and
unit-tested; it simply has zero measured effect here, reported as such rather than claimed as
an improvement. Also flipped `demo/scenarios.py` Scenario F from `PARTIAL` to `PASS` (its
model-unavailable half is no longer "not applicable" — it's tested directly) and corrected the
demo-script.md spec for a deviation found along the way: a missing model artifact degrades to
no live score at all, not a fallback to the logistic-regression baseline as originally
specified.

## 5. Confirmed technology stack (mostly implemented; a few pieces below remain planned)

Backend: Python 3.12+, FastAPI, Pydantic, SQLAlchemy, PostgreSQL.
AI: explicit-state-machine orchestration (hand-rolled, `src/orchestration/flow.py` — not
LangGraph; a framework was never actually needed), provider-agnostic
`LLMClient` (Claude / OpenAI-compatible / mock), structured outputs, tool calling, RAG with
pgvector. ML: scikit-learn, XGBoost/LightGBM, SHAP. Data tooling: pandas/polars, DuckDB for
local analytics over the LATAM Bank dataset. Observability: Prometheus + Grafana
(`IMPLEMENTED`, Phase 13, `src/monitoring/`); tracing is a small custom recorder, not the
OpenTelemetry SDK this line used to list — see
`docs/decisions/ADR-0001-tracing-without-opentelemetry.md`.
Testing: pytest, pytest-asyncio. Quality: Ruff, mypy, pre-commit. Messaging: Kafka-compatible
(Redpanda for local dev), introduced only if a phase actually needs asynchronous event
processing — do not add it speculatively.

Frontend: server-rendered Jinja2 templates + vanilla JS (`src/api/ui.py`), decided in Phase 10
— no separate framework/build step (`docs/architecture.md` § 15). Rationale for every stack
choice: `docs/architecture.md` § Technology Rationale.

Every session must run in **mock LLM mode** without any paid API key — this is mandatory, not
optional, and must remain true for the life of the project (`docs/model-evaluation.md`).

## 6. Development workflow

1. Inspect before modifying: read `docs/project-status.md` first to know what is real vs.
   planned; do not assume a document describes shipped code.
2. Plan before large, architectural, security-sensitive, financial-policy, database, or
   cross-cutting changes. Use the `implement-feature` skill for feature work.
3. Implement vertical slices per `docs/implementation-roadmap.md` phases — don't build
   disconnected layers.
4. After any meaningful implementation milestone, update `docs/project-status.md` with the
   correct state (`IMPLEMENTED` / `PARTIALLY_IMPLEMENTED` / `NOT_IMPLEMENTED` / `BLOCKED`).
   Never leave it describing aspirational state as fact.
5. Never silently resolve a conflict between `prompt.md`, a `docs/` file, and the actual code —
   see the precedence rule in `docs/decisions/README.md`.

## 7. Non-negotiable constraints

These apply to every session, every phase, forever — not just during this initialization task.

- Never let an LLM output authorize a financial transfer, large refund, account closure,
  beneficiary change, credential change, or other irreversible action. LLM output is a
  **proposal**; a deterministic policy engine and, where required, a human authorize it. See
  `docs/decision-policy.md` and `docs/guardrails.md`.
- AI confidence is not authorization. Fraud probability is not the final business decision.
- Customer-provided text and LLM output are both **untrusted input** — validate independently
  before any tool executes (`docs/security-model.md` § Prompt Injection).
- Represent uncertainty and insufficient evidence explicitly; never force a binary
  fraud/legitimate label when evidence doesn't support one (`docs/domain-model.md`).
- Preserve evidence provenance and decision reproducibility (model/prompt/policy version) on
  every recommendation (`docs/decision-policy.md` § Decision Provenance).
- Never fabricate business-approved thresholds, compliance status, performance results, or
  enterprise data. Label everything `SYNTHETIC`, `MOCK`, `PROPOSED`, or `TBD` as appropriate —
  the LATAM Bank dataset is synthetic; say so wherever it's used.
- Never use real customer data — there is none in this project; keep it that way.
- No production deployment, no real financial action, no destructive infrastructure/database
  operation, and no disabling of a security control to make a test pass — ever, without
  explicit user authorization for that specific action in that specific message.
- Rules, skills, prompts, and agent instructions are **not** deterministic security controls.
  Only code-level validation, permission checks, and (where implemented) hooks are.

## 8. Security and privacy quick reference

Full detail: `docs/security-model.md`, `docs/data-governance.md`, `.claude/rules/security.md`.

- Don't open `.env`, credential files, private keys, or other secret-bearing files.
- Don't commit secrets; use `${VARIABLE}` placeholders in examples.
- Minimize PII; tokenize/hash identifiers; never log full card numbers, secrets, or auth
  tokens (`docs/observability.md` § Redaction).

## 9. Verification commands

Real, verified commands as of Phase 1 (`docs/project-status.md`):

```
uv sync                 # install dependencies (creates .venv)
uv run ruff check .     # lint
uv run mypy src evaluation demo   # type check (evaluation/ added Phase 11, demo/ added Phase 12 — see CI workflow)
uv run pytest           # unit tests (fast, offline — model tests use in-memory SQLite)
docker compose build    # build the api image
docker compose up -d db # start db only (localhost:5433) — needed for the alembic commands below
docker compose up -d    # start api (localhost:8080) + db
docker compose down     # tear down

# Migrations (docs/project-status.md § Phase 2 detail) — run from the host, so
# override DATABASE_URL to the host-mapped port (the .env default targets the
# `db` service's internal Docker hostname, which only resolves from inside a
# container):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run alembic upgrade head
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run alembic revision --autogenerate -m "..."
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run alembic check   # fails if models drifted from the last migration

# Ingestion (docs/project-status.md § Phase 3 detail; src/ingestion/README.md) — same
# DATABASE_URL override, run after `alembic upgrade head`:
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ingestion.run --sample-days 90 --skip-tables digital_events,call_transcripts

# Fraud model training (docs/project-status.md § Phase 4 detail; src/ml/README.md) — same
# DATABASE_URL override, run after ingestion:
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ml.train

# Evidence Engine (docs/project-status.md § Phase 5 detail; src/evidence/README.md) — same
# DATABASE_URL override; also needs digital_events ingested (--skip-tables the others to save
# memory) before --refresh-devices has anything to derive from:
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ingestion.run --sample-days 7 --skip-tables call_center_interactions,call_transcripts,complaints
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.evidence.build_case --refresh-devices --pick-fraud

# Orchestration (docs/project-status.md § Phase 6 detail; src/orchestration/README.md) —
# fully offline, no DATABASE_URL, no API key:
uv run python -m src.orchestration.run_golden_cases

# Orchestration against a real transaction — same DATABASE_URL override, needs Phase 3-5 data.
# --persist also writes a real Decision/AuditEvent row (Phase 7, src/policies/gateway.py);
# --persist-twice demonstrates idempotency live (Phase 9):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.orchestration.live_case --pick-fraud --persist --persist-twice

# Policy Engine (docs/project-status.md § Phase 7 detail; src/policies/README.md) — fully
# offline, no DATABASE_URL, no API key:
uv run pytest tests/unit/test_action_risk.py tests/unit/test_authorization.py -q

# Security Hardening (docs/project-status.md § Phase 8 detail; src/security/README.md) —
# fully offline, no DATABASE_URL, no API key. -s prints the measured adversarial-suite result:
uv run pytest tests/security/ -q
uv run pytest tests/security/test_red_team.py::test_adversarial_suite_unsafe_action_rate_is_zero -q -s

# Reliability (docs/project-status.md § Phase 9 detail; src/orchestration/README.md § Reliability)
# — fully offline, no DATABASE_URL, no API key:
uv run pytest tests/reliability/ -q

# UI/API (docs/project-status.md § Phase 10 detail; src/api/README.md) — needs the DB (same
# DATABASE_URL override, run migrations first), then open http://localhost:8080/ in a browser:
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run uvicorn src.api.main:app --reload --port 8080
uv run pytest tests/unit/test_api_cases.py -q   # offline, no DATABASE_URL, no API key

# Evaluation (docs/project-status.md § Phase 11 detail; evaluation/README.md) — needs the DB
# (same DATABASE_URL override) and, for the Fraud ML row, a trained model (uv run python -m
# src.ml.train first):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m evaluation.run
uv run pytest tests/unit/test_evaluation.py -q   # offline, no DATABASE_URL, no API key

# Demo (docs/project-status.md § Phase 12 detail; demo/README.md) — fully offline, no
# DATABASE_URL, no API key:
uv run python -m demo.run
uv run pytest tests/unit/test_demo.py -q

# Observability (docs/project-status.md § Phase 13 detail; src/monitoring/README.md) — metrics/
# tracing unit tests are fully offline; /metrics needs the API running (same DATABASE_URL
# override as UI/API above); the monitoring profile needs Docker:
uv run pytest tests/unit/test_metrics.py tests/unit/test_tracing.py -q
curl http://localhost:8080/metrics
make monitoring-up      # Prometheus :9090, Grafana :3001 (admin/admin) — optional, local-only
make monitoring-down

# Fraud ML score wiring (docs/project-status.md § Phase 15 detail) — unit tests fully offline;
# score_transaction itself needs the DB + a trained model (uv run python -m src.ml.train first):
uv run pytest tests/unit/test_action_risk.py tests/unit/test_authorization.py tests/unit/test_ml_model.py -q
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.orchestration.live_case --pick-fraud --persist
```

`Makefile` mirrors these as `make install|lint|typecheck|test|docker-up|docker-down`, but
**`make` itself was not installed on the machine these were verified on** — the commands above
were run directly and are what's actually confirmed working; treat the `Makefile` as
convenience wrapping, not the source of truth, until someone verifies it with `make` present.
As later phases add real database/tool/security checks, extend this list — never invent a
command that isn't actually wired up. Use the `verify-implementation` skill to (re)discover and
run these correctly.

## 10. Definition of done (for any change)

A change is done when: it matches the responsible `docs/` owner (§ Document Ownership below),
it doesn't violate § 7, tests exist and pass for new logic, `docs/project-status.md` reflects
reality, and no destructive/production action was taken without explicit authorization.

## 11. Document ownership

To avoid duplication and contradictions, each file below is the single source of truth for its
subject — link to it, don't re-explain it elsewhere:

`docs/product-requirements.md` (what), `docs/architecture.md` (how the system is structured),
`docs/domain-model.md` (concepts/relationships), `docs/decision-policy.md` (recommendation →
authorized action), `docs/security-model.md` (threats/trust boundaries), `docs/guardrails.md`
(runtime enforcement), `docs/human-oversight.md` (review/approval/escalation),
`docs/evaluation-plan.md` (system-level evaluation), `docs/model-evaluation.md` (ML/LLM
evaluation), `docs/implementation-roadmap.md` (build sequence), `docs/project-status.md`
(verified current state), `docs/data-governance.md` (data-use rules), `docs/data-lineage.md`
(data movement/transformation), `docs/observability.md` (telemetry), `docs/api-contracts.md`
(API/event boundaries), `docs/demo-script.md` (demo scenarios), `docs/final-report.md` (the
concise, end-of-project engineering summary), `docs/deployment-readiness.md` (honest
production-readiness gap analysis), `docs/decisions/README.md` (ADR process and precedence
rules).
