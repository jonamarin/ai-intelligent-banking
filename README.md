# AI Fraud & Dispute Investigator

An AI-first banking customer-service system focused on one deep workflow: **transaction-
dispute intake and fraud investigation** for a synthetic LATAM retail bank. Built for the
Factored Datathon 2026 (`project_presentation.txt`), following the technical vision in
`prompt.md`.

> **Status: Phase 10 (UI) complete.** This repository contains the project's Claude Code
> operating system — architecture, domain model, security model, guardrails, evaluation plan,
> and a phased implementation roadmap — a working application foundation, a complete, migrated
> PostgreSQL schema, a verified ingestion pipeline, a trained, evaluated fraud model with an
> honestly-reported result (**it performs near chance on the currently loaded sample** — a real
> finding, see `src/ml/README.md`, not a bug), a working Evidence Engine that has built and
> persisted real evidence graphs — **including genuinely detected contradictions**, a case
> orchestration state machine, a real deterministic **Policy Engine** where
> **Irreversible/Critical actions require human approval unconditionally, provably** (a test
> that tries to bypass this exists and fails), a centralized **PII/secret redaction layer** plus
> an automated **red-team test suite** (**0/17 unsafe actions, measured**), real handling for
> LLM/database/RAG failure and a real **idempotency mechanism**, and now a real **JSON API**
> (`docs/api-contracts.md`) plus a server-rendered **customer/analyst UI** on top of it — the
> first live, browser-reachable consumer of everything the earlier phases built. Verified live,
> end-to-end, in a real browser: create a case → the evidence graph renders with real data,
> including genuine contradictions, four visually distinct states → both customer and analyst
> explanations shown → approve a pending case → status updates. A customer session gets a real
> 403 on analyst-only actions, not just a hidden button. See `src/api/README.md`.
> **A bounded recent-date sample is loaded, not the full ~19M-row dataset** (the dev machine has
> too little free RAM for that right now — see `src/ingestion/README.md`). **Genuine remaining
> gaps, honestly reported:** a real authentication/session layer is explicitly out of scope for
> this prototype (`docs/security-model.md` § 3) — the UI's role switcher is a trusted-test
> stand-in, not real login; risk-band fraud-probability thresholds aren't wired in because
> Phase 4's model score was never plumbed into orchestration; one of the four core demo
> scenarios (asking the customer a clarifying question) isn't reachable live yet — a live case
> can never trigger it, a pre-existing gap this phase's own testing surfaced. The Evidence
> Engine's device fingerprint is a documented heuristic proxy, and its direction/confidence
> values are illustrative, never approved policy. See `docs/project-status.md` for the
> authoritative, up-to-date state. Every claim in this README is labeled `Implemented`,
> `Planned`, `Partial`, or `Mocked` — treat anything unlabeled as aspirational.

## 1. Problem

Banks receive high volumes of unauthorized-transaction and dispute reports. Rules-heavy fraud
systems over-alert, creating unnecessary card blocks, customer friction, and human-agent
workload. The goal, borrowed directly from the project brief, is **"Catch More. Flag Less."**
— detect genuine fraud while minimizing unnecessary intervention on legitimate customers. Full
detail: `docs/product-requirements.md`.

## 2. Solution

A hybrid system where an LLM understands the customer, a traditional ML model scores fraud
risk, a deterministic policy engine decides what's authorized, and a human approves anything
irreversible or high-value — regardless of how confident the AI is:

> **AI proposes. Evidence supports. Policy constrains. Humans control high-impact decisions.**

See `docs/architecture.md` for the full component diagram and data flow.

## 3. Why AI, why ML, why rules, why human oversight

- **AI (LLM):** understands free-text Spanish customer reports, extracts entities, generates
  explanations and targeted clarifying questions — never executes anything directly.
- **ML:** produces a calibrated, versioned fraud/risk score from tabular transaction features
  — a prediction, not a decision.
- **Deterministic rules/policy:** authentication, authorization, monetary limits, action-risk
  classification, and human-approval requirements are enforced in code, never left to a
  prompt.
- **Human oversight:** irreversible or high-value actions (account closure, large transfer,
  card freeze) require human approval unconditionally — see the approval matrix in
  `docs/human-oversight.md`.

Rationale for each stack/architecture choice: `docs/architecture.md` § 15. Comparison against
rules-only, ML-only, and LLM-only baselines is a *required* evaluation step, not a rhetorical
claim: `docs/evaluation-plan.md` § 10.

## 4. Dataset

**LATAM Bank Dataset**, Factored Datathon 2026, v1.0.0 — entirely **synthetic**, ~19M rows
across 13 tables, covering Mexico, Colombia, and Argentina, Spanish-language, June 2023–June
2026. Full documentation: `LATAM_Bank_Complete_Data_Dictionary.pdf` /
`LATAM_Bank_Dataset_Summary.pdf` (repository root) and a greppable translation at
`docs/data-dictionary.md`. **The raw files are downloaded locally at `data/raw/`** (~5.0 GB,
git-ignored — never committed) from the organizer-provided read-only S3 bucket; see
`docs/data-lineage.md` § 1 for the exact layout and provenance.

`docs/product-requirements.md` § 13: the competition brief asks for Spanish *and* Portuguese
coverage, but the supplied dataset has no Portuguese/Brazil content. Decision: **Spanish
only**, matching the dataset — the gap is reported honestly (here and in § 13) rather than
fabricated.

## 5. Repository structure

```
CLAUDE.md                    Persistent Claude Code operating contract (start here)
docs/                         Architecture, domain model, security, evaluation, roadmap, status
.claude/                      Rules, skills, agents, hooks, settings for Claude Code sessions
evaluation/golden_cases/      Synthetic scenario fixtures (schema + 10 cases)
src/                           FastAPI app + JSON API + server-rendered UI, config/logging,
                                domain models, ingestion pipeline, fraud ML, evidence engine,
                                AI agent + orchestration, policy engine, security/redaction
                                (implemented); other subpackages are future-phase skeletons
alembic/                       Migrations (implemented) — 17 tables + 1 link table
tests/unit/                   82 passing tests (includes 18 Phase 10 API tests)
tests/security/                24 passing tests (redaction + red-team/adversarial suite)
tests/reliability/             23 passing tests (retry/fallback, idempotency, DB-timeout)
data/raw/                      Raw LATAM Bank dataset (git-ignored, ~5.0 GB — not in git)
data/models/                   Trained model artifacts (git-ignored — binary, not committed)
data/reports/                  Ingestion + fraud-model reports (committed — small aggregate stats)
prompt.md                     Original master prompt (historical design input)
project_presentation.txt      Competition brief (constraints, judging criteria)
LATAM_Bank_*.pdf               Source dataset documentation
```

`tests/integration|security|end_to_end/` and `infrastructure/` don't exist yet — added when
the phase that needs them starts (`docs/implementation-roadmap.md`), not pre-created empty.

## 6. Setup, running locally, testing, evaluation

Verified working (`docs/project-status.md`):

```
git clone <repo> && cd ai-intelligent-banking
cp .env.example .env                  # fill in real values only if you need them; mock LLM mode needs none
uv sync                               # installs dependencies into .venv
uv run pytest                         # 129/129 passing (offline — model/ingestion/ML/evidence/orchestration/policy/security/reliability/API tests use in-memory SQLite / fixtures)
uv run ruff check . && uv run mypy src   # lint + typecheck, both clean
docker compose up -d                  # api on :8080, db (pgvector/pg16) on :5433
curl http://localhost:8080/api/v1/health

# apply the schema (17 tables + 1 link table) to the running db — see CLAUDE.md § 9 for why
# DATABASE_URL is overridden here (the .env default targets Docker's internal network)
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run alembic upgrade head

# load a bounded recent-date sample of the real dataset (src/ingestion/README.md)
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ingestion.run --sample-days 90 --skip-tables digital_events,call_transcripts

# train + evaluate the fraud model (src/ml/README.md) — writes data/reports/fraud_model_evaluation.json
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ml.train

# ingest digital_events too, then build + persist a real evidence graph (src/evidence/README.md)
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.ingestion.run --sample-days 7 --skip-tables call_center_interactions,call_transcripts,complaints
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.evidence.build_case --refresh-devices --pick-fraud

# run the case orchestrator — offline, no DB, no API key (src/orchestration/README.md)
uv run python -m src.orchestration.run_golden_cases
# or against a real transaction, with the Policy Engine persisting a real Decision (src/policies/README.md):
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run python -m src.orchestration.live_case --pick-fraud --persist

# red-team / adversarial test suite — offline, no DB, no API key (src/security/README.md)
uv run pytest tests/security/ -q

# reliability test suite — offline, no DB, no API key (src/orchestration/README.md § Reliability)
uv run pytest tests/reliability/ -q

# run the API + UI (src/api/README.md) — needs DB + migrations applied above:
DATABASE_URL="postgresql+psycopg://banking:banking@localhost:5433/banking_ai" uv run uvicorn src.api.main:app --reload --port 8080
# then open http://localhost:8080/ — role switcher top-right, "Create case" on the home page
uv run pytest tests/unit/test_api_cases.py -q   # offline, no DB, no API key

docker compose down
```

`make install|test|lint|typecheck|docker-up|docker-down|seed` wrap the same commands (`seed`
runs the ingestion command above), but **`make` itself was not installed on the machine this
was verified on** — install it if you want the shorter form, or just use the `uv`/`docker`
commands directly. Full system evaluation and the demo script are `Planned` — they need
Phase 11+ (Evaluation) first.

## 7. Demo scenarios — `Planned`

Twelve scenarios are fully specified and ready to implement against: legitimate transaction,
clear fraud, ambiguous transaction, critical/high-value transaction (mandatory human
approval), LLM unavailable, dependency unavailable, prompt injection, missing data, conflicting
evidence, duplicate action, human escalation, and policy rejection. Full detail:
`docs/demo-script.md`. Machine-readable fixtures for ten of them: `evaluation/golden_cases/`.

## 8. Security — `Partial` (designed, not yet enforced in code)

Threat model, trust boundaries, and mitigations: `docs/security-model.md`. Runtime enforcement
model (which layer actually enforces each guardrail — prompt, code validation, permission
check, or human approval): `docs/guardrails.md`. Two Claude-Code-level hooks are active today
(`Implemented`, dev-time only — see § 10): `.claude/hooks/README.md`.

## 9. Privacy and fairness — `Planned`

PII classification and minimization rules: `docs/data-governance.md`. Fairness evaluation
methodology (subgroup comparison across country/segment/dialect, never as decision inputs):
`docs/model-evaluation.md` § 13. No fairness claim is made until it's actually measured.

## 10. Reliability and scalability — `Planned`

Failure-mode table (what happens if the LLM, database, or fraud model is unavailable) and
scalability design targets: `docs/architecture.md` §§ 10, 12. These are design targets, not
measurements — see the labeling rule in `docs/evaluation-plan.md` § 1.

## 11. Claude Code operating system — `Implemented`

This repository is set up to be worked on by Claude Code sessions with persistent context:

- `CLAUDE.md` — the primary operating contract every session should read first.
- `.claude/rules/` — path/topic-scoped engineering rules (backend, frontend, security,
  database, AI agents, testing, infrastructure).
- `.claude/skills/` — task workflows (`implement-feature`, `review-security`,
  `investigate-fraud`, `create-migration`, `run-evaluations`, `verify-implementation`).
- `.claude/agents/` — specialized subagent roles (architect, backend/frontend/AI engineer,
  fraud analyst, security reviewer, QA engineer).
- `.claude/hooks/` — two tested, active `PreToolUse` hooks blocking access to secret-bearing
  files and a short list of obviously destructive shell commands. Documented limitations
  (pattern-based, not exhaustive; fail-open if `python` is unavailable): `.claude/hooks/
  README.md`.
- `.claude/settings.json` — the conservative, shared configuration wiring the hooks above; it
  grants no blanket permission for destructive, production, or financial actions.

## 12. Documentation map

| Question | Document |
|---|---|
| What does the product do? | `docs/product-requirements.md` |
| How is the system structured? | `docs/architecture.md` |
| What are the core entities? | `docs/domain-model.md` |
| How does a recommendation become an authorized action? | `docs/decision-policy.md` |
| What's the threat model? | `docs/security-model.md` |
| How are guardrails actually enforced? | `docs/guardrails.md` |
| Who approves what, and when? | `docs/human-oversight.md` |
| How is the system evaluated? | `docs/evaluation-plan.md`, `docs/model-evaluation.md` |
| What's logged, and what's redacted? | `docs/observability.md` |
| What are the API/event contracts? | `docs/api-contracts.md` |
| What data rules apply? | `docs/data-governance.md`, `docs/data-lineage.md` |
| What's the dataset schema? | `docs/data-dictionary.md` |
| What gets built, in what order? | `docs/implementation-roadmap.md` |
| What's actually done right now? | `docs/project-status.md` |
| What will the demo show? | `docs/demo-script.md` |
| How are significant decisions recorded? | `docs/decisions/README.md` |

## 13. Limitations

See `docs/project-status.md` § Known limitations for the current, maintained list (frontend
framework undecided, no business-approved thresholds exist anywhere in this project,
Portuguese-language gap, `make` not installed on the dev machine this was built on). This
project is a ten-day/hackathon-scale prototype
demonstrating production-readiness *thinking* — it is not, and does not claim to be, a
production banking system (`docs/product-requirements.md` § 10).

## 14. Future work

The full phased plan, with objectives, deliverables, tests, and exit criteria per phase, is
`docs/implementation-roadmap.md` (14 phases, foundation through deployment-readiness
documentation).
