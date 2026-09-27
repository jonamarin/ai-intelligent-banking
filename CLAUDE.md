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
  decisions/                   ← ADRs

evaluation/
  golden_cases/                ← synthetic scenario fixtures + schema

src/                           ← application code (Phase 1+, docs/project-status.md)
  config/                      ← settings + structured logging (implemented)
  api/                         ← FastAPI app, health check, error handling (implemented)
  models/                      ← SQLAlchemy models + Pydantic schemas (implemented, Phase 2-3)
  ingestion/                    ← CSV -> Postgres loader + data-quality report (implemented, Phase 3)
  ml/                           ← fraud model: features, baseline, XGBoost, evaluation (implemented, Phase 4)
  evidence/                     ← device derivation, evidence graph, contradiction detection (implemented, Phase 5)
  agents/orchestration/policies/tools/retrieval/security/monitoring/
                               ← package skeletons only; each documents which phase fills it in

alembic/                       ← migrations (implemented, Phase 2-3) — env.py reads
                                  src.config.settings + src.models.Base.metadata
tests/unit/                    ← 38 passing tests (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5 Phase 4 + 13 Phase 5)
data/models/                   ← trained model artifacts (git-ignored — binary)
pyproject.toml, uv.lock, Dockerfile, docker-compose.yml, Makefile,
.github/workflows/ci.yml, .pre-commit-config.yaml, .env.example
                               ← Phase 1 foundation tooling
```

Repository initialization, Phase 1 — Foundation, Phase 2 — Domain, Phase 3 — Ingestion
(sample mode), Phase 4 — Fraud ML, and Phase 5 — Evidence Engine are all done
(`docs/project-status.md`). Orchestration, the policy engine, `infrastructure/terraform/`, and
everything else in `docs/implementation-roadmap.md` Phases 6+ do not exist yet — do not create
empty placeholder directories for a phase before it actually starts; the existing `src/`
subpackages that are still just markers document this explicitly in their own docstrings. A
`--full` ingestion run (the entire ~19M-row dataset, not just the verified recent-date sample)
has also not been done — see `src/ingestion/README.md` § Sample vs. full mode before
attempting it. **The trained fraud model performs near chance on the currently loaded sample —
a real, verified finding, not a bug** (`docs/project-status.md` § Phase 4 detail,
`src/ml/README.md`). **The Evidence Engine's `device_id` is a documented heuristic proxy, not
a true device fingerprint** — the dataset has no persistent device identifier
(`src/evidence/README.md`). Evidence Engine direction/confidence values are illustrative
heuristics, never approved policy, and this module must never be wired to a tool that executes
an action (`docs/decision-policy.md` § 5).

## 5. Confirmed technology stack (planned, not yet implemented)

Backend: Python 3.12+, FastAPI, Pydantic, SQLAlchemy, PostgreSQL.
AI: explicit-state-machine orchestration (LangGraph or equivalent), provider-agnostic
`LLMClient` (Claude / OpenAI-compatible / mock), structured outputs, tool calling, RAG with
pgvector. ML: scikit-learn, XGBoost/LightGBM, SHAP. Data tooling: pandas/polars, DuckDB for
local analytics over the LATAM Bank dataset. Observability: OpenTelemetry, Prometheus, Grafana.
Testing: pytest, pytest-asyncio. Quality: Ruff, mypy, pre-commit. Messaging: Kafka-compatible
(Redpanda for local dev), introduced only if a phase actually needs asynchronous event
processing — do not add it speculatively.

Frontend framework is `OPEN QUESTION` — decide at the start of Phase 10 (`docs/
implementation-roadmap.md`). Rationale for every stack choice: `docs/architecture.md` §
Technology Rationale.

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
uv run mypy src         # type check
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
(API/event boundaries), `docs/demo-script.md` (demo scenarios), `docs/decisions/README.md`
(ADR process and precedence rules).
