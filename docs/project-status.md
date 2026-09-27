# Project Status

Owns: verified current implementation state. This document must never represent planned
functionality as implemented. Update it whenever a meaningful implementation phase
(`docs/implementation-roadmap.md`) completes, changes, or blocks.

**Last meaningful update:** 2026-09-27 (Phase 10 — UI implemented and verified).
**Last validation:** 2026-09-27 — actually run, not just inspected: `uv run ruff check .`
(clean), `uv run mypy src` (clean, 74 files), `uv run pytest` (129/129 passed), and a full
golden-path walkthrough in a real Chrome browser (create case -> evidence graph with two real
contradictions -> dual explanation -> approve -> status updates), plus role-gating (customer
403s on the review queue and review endpoint) and idempotent duplicate-review handling verified
live via curl against the real API and database (§ Phase 10 detail below).

## Current phase

Phase 10 (UI) complete. This repository now contains: the original master prompt
(`prompt.md`), the competition brief (`project_presentation.txt`), the LATAM Bank dataset
documentation (two PDFs at the repository root), the raw LATAM Bank dataset itself
(`data/raw/`, git-ignored, ~5.0 GB — `docs/data-lineage.md` § 1), the Claude Code operating
system (`CLAUDE.md`, `docs/`, `.claude/`, `evaluation/golden_cases/`), a working application
foundation (Phase 1), a complete, migrated domain schema (Phase 2), a working, verified
ingestion pipeline (Phase 3), a trained, evaluated fraud model with a documented, honest
finding (Phase 4), a working Evidence Engine that has built and persisted real evidence graphs
(Phase 5), a working case orchestration state machine (Phase 6), a real deterministic
authorization path (Phase 7), a centralized PII/secret redaction layer and red-team test suite
(Phase 8), real reliability handling for LLM/DB/RAG failure and idempotency (Phase 9), and now
a real JSON API (`docs/api-contracts.md` § 1 — previously only `/health` existed) plus a
server-rendered customer/analyst UI on top of it — the first live, HTTP-reachable consumer of
everything Phases 6-9 built. See `src/api/README.md`.
**Irreversible/Critical actions still require human approval unconditionally, provably, even
when the LLM is unavailable** — verified directly: a degraded case proposing a $100,000 transfer
still produces `requires_human_approval=True` through the full fallback path
(`docs/demo-script.md` Scenario D + Scenario E, together), and this now holds through the real
HTTP/UI path too, not just the CLI scripts.

## Status by roadmap phase (`docs/implementation-roadmap.md`)

| Phase | State |
|---|---|
| 1 — Foundation | IMPLEMENTED — see § Phase 1 detail below |
| 2 — Domain | IMPLEMENTED — see § Phase 2 detail below |
| 3 — Synthetic Data / Ingestion | IMPLEMENTED — see § Phase 3 detail below (sample-mode verified, now 90 days for transactions/complaints/call_center_interactions, 7 days for digital_events; `--full` not yet run in this environment, see `src/ingestion/README.md`) |
| 4 — Fraud ML | IMPLEMENTED — see § Phase 4 detail below (real, honestly-reported near-chance result — see detail) |
| 5 — Evidence Engine | IMPLEMENTED — see § Phase 5 detail below (real evidence graphs + contradiction detection verified against live data) |
| 6 — AI Agent | IMPLEMENTED — see § Phase 6 detail below (mock-LLM orchestration verified against all 10 golden cases + 2 live transactions; genuine gaps found and honestly reported, not hidden) |
| 7 — Policy Engine | IMPLEMENTED — see § Phase 7 detail below (Scenario D exit criteria met and tested against an actual bypass attempt; genuine remaining gaps — idempotency, risk-band/model-score wiring — honestly reported, not hidden) |
| 8 — Security Hardening | IMPLEMENTED — see § Phase 8 detail below (0/17 unsafe actions in a measured, sample-size-stated adversarial suite; found and fixed a real injection-detection gap; several red-team cases honestly reported as not yet coverable, not silently claimed) |
| 9 — Reliability | IMPLEMENTED — see § Phase 9 detail below (LLM fallback, DB timeout, RAG-failure degradation, and idempotency all verified — the idempotency round trip against a real database, the rest via `tests/reliability/`) |
| 10 — UI | IMPLEMENTED — see § Phase 10 detail below (Scenarios A/B/D drivable live in a real browser, verified; Scenario C honestly reported as not yet reachable live — a pre-existing Phase 6 gap this phase's testing surfaced) |
| 11 — Evaluation | NOT_IMPLEMENTED |
| 12 — Demo | NOT_IMPLEMENTED |
| 13 — Observability | NOT_IMPLEMENTED |
| 14 — Deployment Readiness (docs) | PARTIALLY_IMPLEMENTED — `docs/architecture.md`, `docs/security-model.md`, and this document lay out what deployment readiness requires; no actual readiness checklist has been executed because nothing is deployed |

## Completed

- Full Claude Code operating-system scaffold: `CLAUDE.md`, `docs/*` (17 files),
  `.claude/rules/*` (7 files), `.claude/skills/*` (6 skills), `.claude/agents/*` (7 agents),
  `.claude/hooks/*`, `.claude/settings.json`, `evaluation/golden_cases/*`, updated `README.md`
  and `.gitignore`.
- Data dictionary translated into a greppable Markdown form (`docs/data-dictionary.md`) from
  the source PDFs.
- Chosen and documented the project's scope decision: transaction-dispute/fraud investigation
  workflow only (`docs/product-requirements.md` § 3), and the language-scope decision:
  Spanish only, matching the dataset, with the Portuguese gap reported explicitly rather than
  fabricated (`docs/product-requirements.md` § 13).
- Raw LATAM Bank dataset downloaded to `data/raw/` from the organizer-provided S3 bucket
  (`docs/data-lineage.md` § 1).
- **Phase 1 — Foundation**, **Phase 2 — Domain**, **Phase 3 — Ingestion**,
  **Phase 4 — Fraud ML**, **Phase 5 — Evidence Engine**, **Phase 6 — AI Agent /
  Orchestration**, **Phase 7 — Policy Engine**, **Phase 8 — Security Hardening**,
  **Phase 9 — Reliability**, and **Phase 10 — UI**, detailed below.

### Phase 1 detail

- `pyproject.toml` (uv-managed, `package = false` — this is an application, not a published
  library) with `fastapi`, `uvicorn`, `pydantic`/`pydantic-settings`, `sqlalchemy`,
  `python-dotenv`; dev group: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`,
  `pre-commit`. `uv.lock` committed for reproducibility.
- `src/` package skeleton matching `docs/architecture.md`: `config` (settings + logging,
  populated), `api` (populated), `models` (populated as of Phase 2, below), and
  `agents`/`orchestration`/`policies`/`tools`/`evidence`/`retrieval`/`security`/`monitoring`
  (package markers only, each documenting which later phase fills it in — not empty
  placeholders, but not yet functional either).
- `src/config/settings.py` — `pydantic-settings` `Settings`, env-file-backed, `llm_mode`
  defaults to `mock` (hard requirement, `prompt.md` § 52).
- `src/config/logging.py` — structured JSON logging **with a mandatory redaction filter**
  masking card/account-like digit runs before any line is emitted (`docs/observability.md`
  § 2). Known gap: this covers logs emitted by *this project's own code*; when run via the
  `uvicorn` CLI (as the Docker image does), uvicorn's own access/error loggers use their
  default (non-JSON) format rather than this formatter — acceptable for now since uvicorn's
  access log only records method/path/status, not application data, but worth revisiting in
  Phase 13 if that changes.
- `src/api/main.py` + `errors.py` — FastAPI app factory, `GET /api/v1/health`, a correlation-ID
  middleware (`X-Correlation-ID` request/response header), and three exception handlers
  (`AppError`, `RequestValidationError`, generic `Exception`) that always return the
  `{"error": {"code","message","correlation_id"}}` shape from `docs/api-contracts.md` § 2 and
  never leak a stack trace to the client (`prompt.md` § 44).
- `Dockerfile` + `docker-compose.yml` (api + `pgvector/pgvector:pg16` db, healthchecked).
  Host ports remapped to `8080`/`5433` because `8000`/`5432` were already in use by other
  software on the development machine this was built on — internal container ports are
  unchanged; revisit the mapping in `docker-compose.yml` if that's not the case on another
  machine.
- `Makefile` (`install`, `dev`, `test`, `lint`, `typecheck`, `format`, `docker-up`,
  `docker-down` are real; `train`/`evaluate`/`redteam`/`seed`/`demo` print which future phase
  implements them rather than failing or faking output). **`make` itself is not installed on
  the machine this was built on** — every target was verified via its underlying command
  (`uv run ...` / `docker compose ...`) directly, not via `make`. Install `make` (e.g. via
  Chocolatey/`scoop install make` on Windows, or it's preinstalled on macOS/Linux) to use the
  Makefile as-is; until then, use the underlying commands shown in each target.
- `.github/workflows/ci.yml` — lint, typecheck, unit tests, `LLM_MODE=mock`, no production
  credentials required. Not yet run on actual GitHub Actions infrastructure (no push has been
  made) — the equivalent commands were verified locally.
- `.pre-commit-config.yaml` — ruff + mypy hooks; installs and runs correctly (verified).
- 10 unit tests, all passing: health endpoint + correlation ID (4), settings defaults/overrides
  (2), logging redaction (4).

### Phase 2 detail

- 11 SQLAlchemy models (`src/models/`) covering every entity in `docs/domain-model.md` § 3:
  `Customer`, `Product` (Account), `Device` (derived — see its docstring on why
  `known_customer` is a simplification), `Transaction` (with `is_fraud`/`fraud_score` labeled
  `SYNTHETIC` and excluded from feature use, docs/data-lineage.md § 5), `Merchant` (derived),
  `CustomerInteraction`, `FraudCase`, `Evidence` (append-only by convention; `direction`
  constrained to a real `EvidenceDirection` enum, validated on flush), `Decision` (every
  provenance field from `docs/decision-policy.md` § 9 is a real NOT NULL column, plus a
  `decision_evidence` many-to-many link table so evidence attribution is a real foreign-key
  relationship, not a JSON array of IDs), `HumanReview` (a structurally distinct table from
  `Decision`, on purpose — docs/domain-model.md § Human Review), and `AuditEvent`.
  `registration_branch_id`/`opening_branch_id`/`branch_id`/`reviewer_id` are plain string
  columns without FK constraints, since `branches` and `service_agents` are out of this
  workflow's modeled scope (`docs/data-dictionary.md` § Tables not used) — documented in each
  model's docstring, not silently omitted.
- PII/sensitivity classification (`docs/data-governance.md` § 1) is noted directly in the
  `Customer` model's docstring/comments, not left implicit.
- Pydantic read schemas (`src/models/schemas.py`) for the six entities most likely to appear
  in an API response first (`Customer`, `Transaction`, `FraudCase`, `Evidence`, `Decision`,
  `HumanReview`); `Device`/`Merchant`/`CustomerInteraction` schemas are deferred to whichever
  phase actually exposes them via a tool or endpoint, per `src/models/schemas.py`'s own
  docstring — not built speculatively ahead of a real consumer.
- Alembic wired to `src/models`' `Base.metadata` and to `src.config.settings.get_settings()`
  for its DB URL (single source of truth — no separate hardcoded URL in `alembic.ini`).
  Initial migration (`alembic/versions/4e7deb4207a2_initial_domain_schema.py`) autogenerated
  and applied against a live `docker compose` Postgres; verified reversible
  (`downgrade -1` → `upgrade head`) and drift-free after a follow-up model tweak
  (`alembic check`).
- 7 new unit tests (`tests/unit/test_models.py`, `tests/unit/conftest.py`) against an
  in-memory SQLite engine — fast and fully offline, per `.claude/rules/testing.md`. This is
  deliberately a *different* kind of check than the Alembic-against-Postgres verification
  above: SQLite proves the declared ORM constraints (unique, FK, enum validation) behave
  correctly; it does not prove the migration applies to Postgres — re-verify that separately
  (steps recorded above) if the models change again. Covers: unique `document_number`,
  FK enforcement (`Product` requires an existing `Customer`), a full `Transaction` insert
  linked to both `Customer` and `Product`, `Evidence.direction` rejecting an invalid value,
  `Decision` requiring a non-null `policy_version`, and `HumanReview` staying a structurally
  distinct record from the `Decision` it reviews.
- 17 unit tests total (10 from Phase 1 + 7 from Phase 2), all passing.

### Phase 3 detail

- 5 new source-table SQLAlchemy models mirroring the raw dataset schema exactly
  (`CallCenterInteraction`, `CallTranscript`, `Complaint`, `DigitalEvent`, `ExchangeRate`),
  distinct from (but feeding into, in later phases) the curated `CustomerInteraction` domain
  entity from Phase 2 — see each model's docstring for the distinction. A second Alembic
  migration (`alembic/versions/b4ecd51894b0_add_source_ingestion_tables.py`) added them;
  verified the same way as Phase 1's migration (applied, reversible, `alembic check` clean).
- `src/ingestion/`: a generic CSV → Postgres loader (`loader.py`), Hive-partition discovery
  with a bounded recent-date sample or full-history mode (`partitions.py`), a data-quality
  report (`quality.py`), and a CLI orchestrator (`run.py`) loading, in FK-dependency order:
  `customers`, `products`, `daily_exchange_rates` (independent) → `transactions`,
  `call_center_interactions` → `call_transcripts`, `complaints` → `digital_events`. `branches`,
  `service_agents`, `marketing_campaigns`, `campaign_sends`, `satisfaction_surveys` are
  deliberately skipped (out of this workflow's scope, `docs/data-dictionary.md`).
- Handles the dataset's documented data-quality characteristics as real, tested code, not just
  documentation: duplicate rows (an **unrestricted** `ON CONFLICT DO NOTHING` — a real
  `products.product_number` collision across different `product_id`s was hit and handled during
  verification, not merely anticipated), orphaned foreign keys (dropped + counted), and NULLs in
  columns the schema declares NOT NULL but the real data violates anyway (a real
  `call_transcripts.duration_seconds` violation was hit and handled: 71/583 rows in one 3-day
  sample) — see `src/ingestion/README.md` for the full list and the exact counts observed.
- **A real bug was found and fixed during verification, not just written and trusted:** pandas
  ≥ 3.0's new default string dtype represents missing values as `float('nan')`, not `None`, and
  a naive `value is None` null-check (the initially-written version) silently treated legitimate
  NULLs in *nullable* foreign-key columns as *orphaned* references, incorrectly dropping 100% of
  the `complaints` table's rows in one verification run. Caught by cross-checking the ingestion
  report's counts against the live database's actual row counts — not by trusting a "0 errors,
  exit code 0" run. Fixed by routing every null check through `pd.isna` and normalizing to real
  `None` once, at record-build time (`src/ingestion/loader.py`'s `_none_if_na`); pinned with
  `tests/unit/test_ingestion_loader.py` so a future pandas upgrade can't reintroduce it silently.
- A second real bug, also caught by verification rather than assumed away: `cursor.rowcount` is
  `-1` (driver-reported "unknown") for a multi-row `VALUES (...), (...)` insert under psycopg —
  the loader initially reported negative "rows loaded" counts. Fixed with `RETURNING` +
  counting the returned rows, which is exact regardless of driver rowcount support.
- **Verified with a full clean run** (`--sample-days 3`, after truncating every table): the
  report's per-table row counts were cross-checked against `SELECT count(*)` on all 8 loaded
  tables in the live database — exact match on every one: `customers` 150,000,
  `products` 399,994 (6 correctly skipped for a real `product_number` duplicate),
  `daily_exchange_rates` 13,164, `transactions` 14,659, `call_center_interactions` 2,239,
  `call_transcripts` 512 (71 correctly dropped), `complaints` 217, `digital_events` 41,295.
  Report committed at `data/reports/ingestion_report.json`.
- **Not yet run: `--full` mode** (the entire ~19M-row dataset). The development machine this
  was built and verified on has very little free RAM (observed as low as ~1.5 GB of 16 GB
  total free); even the bounded 3-day sample run was killed by out-of-memory conditions twice
  before a memory-usage fix (removing an unnecessary whole-frame `.astype(object)` call) and a
  smaller sample got it through cleanly. `--full` — especially `digital_events` at 10M rows —
  needs meaningfully more headroom than was available here. See `src/ingestion/README.md` §
  Sample vs. full mode for what to check before attempting it.
- 3 new regression tests (`tests/unit/test_ingestion_loader.py`) pin the pandas-NA-handling fix.
  20 unit tests total (10 Phase 1 + 7 Phase 2 + 3 Phase 3), all passing.

**Update (2026-09-26, for Phase 4):** re-ran ingestion with `--sample-days 90` and the new
`--skip-tables digital_events,call_transcripts` flag (added this session — `src/ingestion/
run.py`), since Phase 4's feature set doesn't need those two and skipping them kept the larger
pull within this machine's memory budget. Verified again by cross-checking the report against
live `SELECT count(*)`: `customers` 150,000, `products` 399,994, `daily_exchange_rates` 13,164,
`transactions` 370,998, `call_center_interactions` 56,125, `complaints` 5,492 — exact match on
every table, same as the Phase 3 verification methodology. Date range: 2026-03-20 to
2026-06-18. Fraud rate at this scale: 335/370,998 ≈ 0.09%.

### Phase 4 detail

- `src/ml/`: `dataset.py` (loads from Postgres, computes the temporal train/val/test split
  proportionally from whatever date range is actually loaded — not a hardcoded calendar
  assumption, since Phase 3 only loads a bounded sample), `features.py` (leakage-safe feature
  engineering — every rolling/historical statistic strictly prior to the row it's attached to),
  `baseline.py` (logistic regression), `model.py` (XGBoost, `ModelArtifact` carrying
  `model_version`/`feature_version`/`trained_at` per `docs/decision-policy.md` § 9),
  `evaluate.py` (precision/recall/F1/ROC-AUC/PR-AUC/FPR/FNR/calibration/confusion matrix,
  `docs/evaluation-plan.md` § 2 — business-cost metrics deliberately not computed, no
  business-approved cost coefficients exist, `docs/evaluation-plan.md` § 3), `explain.py`
  (SHAP global feature importance), `train.py` (CLI orchestrating all of the above).
- 15 features implemented from `transactions`/`customers`/`complaints`/`daily_exchange_rates`
  (amount deviation, transaction velocity at 24h/7d, country deviation, time-of-day deviation,
  merchant fraud-rate-prior, historical complaint count, card-present, auth-failed, and more —
  full list in `src/ml/features.py`'s `FEATURE_COLUMNS`). Device-novelty, IP-novelty, and true
  geographic-distance are explicitly `NOT_IMPLEMENTED` (`NOT_IMPLEMENTED_FEATURES`) — they need
  the `Device` entity derived from `digital_events`, which this ingestion run skipped; not
  silently omitted, listed and explained.
- **Two real bugs found and fixed during verification** (not assumed away):
  1. Falling back to the raw `amount` column when `amount_usd` was null mixed three currencies
     (ARS/COP/MXN) that differ by orders of magnitude (observed: COP avg ~6.7M vs. USD avg
     ~1.7k) directly against USD amounts, producing `amount_deviation` values up to ~4×10¹³.
     Fixed by converting through `daily_exchange_rates` properly; caught by inspecting the
     actual output range, not by the code merely running without error.
  2. The dataset's success `response_code` is the string `"0"`, not `"00"` — the first version
     compared against the wrong string and flagged ~95% of transactions as `auth_failed`
     (sanity-checked against `transaction_status`, which showed ~8% actually declined/pending/
     reversed). Fixed; both bugs pinned with regression tests
     (`tests/unit/test_ml_features.py`, 5 new tests).
- **A third issue, performance not correctness:** the first correct version of the per-customer
  feature computation used `.groupby(...).transform(lambda s: s.expanding()...)` — measured at
  **598 seconds** for 371k rows. Rewritten as vectorized cumsum/cumcount/shift arithmetic (no
  `.expanding()`, no per-group Python callable): **~30 seconds**, a ~20x improvement, verified
  by direct timing before and after.
- **Trained and evaluated, with a real, honestly-reported finding:** both the logistic-
  regression baseline and the XGBoost main model perform **near chance** on this sample
  (test-set ROC-AUC 0.462 and 0.502 respectively; PR-AUC ≈ 0.001, roughly the base fraud rate).
  This is not a pipeline bug — verified directly: none of the 15 implemented features show a
  meaningful univariate mean difference between fraud and non-fraud transactions (checked and
  recorded in `src/ml/README.md`), while the dataset's own `fraud_score` field (excluded as a
  feature per the leakage policy) clearly separates the classes (mean 15.0 non-fraud vs. 50.8
  fraud, n=296,958) — proving a real signal exists in the generator's process that simply isn't
  exposed through the transactional/behavioral columns loaded so far. This diagnostic is
  included directly in the committed evaluation report
  (`diagnostic_fraud_score_separation_by_is_fraud`), not just asserted in prose. Leading
  hypothesis for recovering it: device/session/IP data via Phase 5's `Device` derivation.
  This matches `docs/implementation-roadmap.md` Phase 4's own anticipated risk exactly
  ("the synthetic `is_fraud` label distribution may be unrealistic ... report this honestly
  rather than tuning to an artificially easy target") — reported as specified, not avoided.
- Trained model artifacts saved: `data/models/logistic_regression-baseline.joblib`,
  `data/models/xgboost-v0.1.0.joblib` (git-ignored — binary, not committed; reproducible via
  `uv run python -m src.ml.train`). Evaluation report committed:
  `data/reports/fraud_model_evaluation.json`.
- Reproduced the full pipeline **twice** with identical results (both before and after the
  final dtype fix caught by the test suite) — not a one-off lucky run.
- 5 new regression tests (`tests/unit/test_ml_features.py`) covering: label columns never
  appear in `FEATURE_COLUMNS`, first-transaction-has-no-history, prior stats never see the
  current-or-future row (a synthetic 3-row test with a huge outlier on the last row, asserting
  the first row's deviation is unaffected by it), the response-code regression, and the
  currency-conversion regression. 25 unit tests total (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5
  Phase 4), all passing.
- **Not done in this phase, by design:** the full rules/ML/LLM/hybrid baseline comparison
  (`docs/evaluation-plan.md` § 10) needs the policy engine and orchestration layers and belongs
  to Phase 11; this phase only compares the logistic-regression baseline against XGBoost, per
  `docs/model-evaluation.md` § 4's actual scope for Phase 4.

### Phase 5 detail

- `src/evidence/`: `device.py` (Device derivation from `digital_events` — a documented
  heuristic fingerprint, `sha256(ip_address, platform, browser)`, since the dataset has no
  persistent device-fingerprint column; missing `ip_address` → `Unknown`, never a fabricated
  ID), `graph.py` (six evidence-extraction rules — device history, country deviation, amount
  deviation, auth result, historical dispute rate, velocity — plus contradiction detection),
  `persist.py` (writes a `FraudCase` + append-only `Evidence` rows + one `AuditEvent`;
  deliberately does not set `risk_score` or create a `Decision` — that's Phase 6/7's job, not
  half-integrated here), `build_case.py` (CLI).
- **Ingested `digital_events` for the first time**: a 7-day window (112,692 events, 2026-06-11
  to 2026-06-18), using the new `--skip-tables` flag to avoid re-touching already-loaded
  tables. Report counts matched live `SELECT count(*)` exactly, same verification method as
  Phases 3–4.
- **Three real bugs found and fixed during verification** (full detail in
  `src/evidence/README.md`): (1) the same Postgres 65,535-parameter limit hit again in
  `load_devices` because it didn't reuse `src/ingestion/loader.py`'s batching — fixed the same
  way; (2) `fraud_cases.case_id` is `VARCHAR(30)` but the code generated 36-char UUIDs for it
  (correct for `evidence.evidence_id`, wrong for `case_id`) — caught as a real
  `StringDataRightTruncation` error on the first persist attempt, not by review; (3)
  SQLAlchemy's `Enum(native_enum=False)` stores the Python enum member *name*
  (`SUPPORTS_FRAUD`) by default, not `.value` (`supports_fraud`) — inconsistent with
  `docs/domain-model.md`'s documented direction strings, caught by inspecting the first real
  evidence rows written to the database, not assumed correct because nothing crashed.
- **Verified end-to-end against real data, twice, with genuinely different results each time**
  (not two runs of the same trivial case): device derivation produced **19,065 distinct device
  fingerprints from 112,692 events**. Two evidence graphs built and persisted:
  1. A real `is_fraud=true` transaction (`TRX-MXCWNPT6UVBUMBBVOPWM`) — evidence came back
     almost entirely `supports_legitimate`/`neutral` (matching country, unremarkable amount,
     successful auth, no complaints, no velocity spike, no nearby digital session). Consistent
     with the Phase 4 finding, not contradicting it.
  2. A real `is_fraud=false` transaction (`TRX-SMPYV51IQT9JPNQ56BMR`) — known device, matching
     country, successful auth, but an amount 4.3 standard deviations above this customer's
     prior mean. **The engine correctly detected 2 contradictions** (the amount anomaly vs. the
     known-device and matching-country evidence) instead of picking a side — a real instance
     of `docs/demo-script.md` Scenario C's "ambiguous, mixed evidence" case, found in real data.
  Both committed as `data/reports/example_evidence_graph.json` and
  `data/reports/example_evidence_graph_ambiguous.json` — meets the Phase 5 exit criteria
  (`docs/implementation-roadmap.md`: "the example graph shape in prompt.md § 10 is
  reproducible from real data for at least one seeded case").
- 13 new unit tests (`tests/unit/test_evidence_graph.py`) for the pure-logic pieces (device
  fingerprint stability/uniqueness/None-on-missing-IP, the country/auth evidence rules, and —
  the phase's explicitly required test — contradiction detection with two conflicting signals,
  plus verifying weak/agreeing/neutral signals are correctly *not* flagged as contradictions).
  The DB-coupled rules (device/amount/complaint/velocity evidence) are verified against the
  live database instead of mocked, per `src/evidence/README.md`'s stated testing strategy.
  38 unit tests total (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5 Phase 4 + 13 Phase 5), all passing.
- **Not done in this phase, by design:** no risk score, no Decision record, no action
  execution — this module only assembles and persists evidence. Its direction/confidence
  values are illustrative heuristics (`docs/decision-policy.md` § 5), not approved policy.

### Phase 6 detail

- `src/agents/`: `schemas.py` (four `extra="forbid"` structured-output types), `llm_client.py`
  (`LLMClient` Protocol + fully-implemented deterministic `MockLLMClient`; `get_llm_client()`
  raises `NotImplementedError` for `LLM_MODE=live` — no fabricated provider integration,
  CLAUDE.md § 7).
- `src/retrieval/`: 4 synthetic Spanish policy documents (`policy_docs/*.md`) + `policy_rag.py`
  (TF-IDF retrieval, `SIMILARITY_THRESHOLD = 0.08`, returns `None` rather than a weak guess).
- `src/tools/`: `read_tools.py` (real DB reads, executed directly) and `action_tools.py` (every
  function returns a `ToolProposal`, never writes to the DB — not imported by `flow.py`).
- `src/orchestration/`: `case.py` (shared `CaseInput`/`CaseResult`), `flow.py` (the state
  machine), `golden_case_loader.py` (fixtures -> `CaseInput`), `live_case.py` (live, DB-backed
  `EvidenceGraph` -> `CaseInput`), `run_golden_cases.py` (fixture-suite CLI).
- **A real circularity bug found and fixed before any result was reported**: the first version
  of `golden_case_loader.py` set `escalation_required` directly from each fixture's own
  `expected_human_involvement` answer text, making the orchestrator's decisions circular rather
  than an independent test. Caught immediately after the first run (suspiciously perfect
  alignment), fixed by deriving it the only legitimate way Phase 6 can offline:
  `bool(detect_contradictions(items))` — the same shared function the live Evidence Engine
  uses. Full detail in `src/orchestration/README.md`.
- **Verified against all 10 `evaluation/golden_cases/*.json` fixtures** in `LLM_MODE=mock`,
  end-to-end, no errors (`data/reports/golden_case_run.json`). Comparing actual decisions
  against each fixture's expected outcome (for human review, not auto-graded, per
  `run_golden_cases.py`'s own stated design choice): 4 of 10 align cleanly, 2 reveal genuine,
  honestly-reported gaps (`high_value_transfer` needs an amount-threshold rule Phase 6 has no
  way to compute; `duplicate_action` needs an action-risk classification rule), and the
  remaining cases hinge on prose nuance no automated check should grade. See
  `src/orchestration/README.md` for the full table and reasoning — the two gaps are exactly
  what Phase 7 (Policy Engine) is scoped to close, not a defect in this phase. **Update
  (2026-09-26, Phase 7):** the `high_value_transfer` gap is now closed — see § Phase 7 detail
  below; `duplicate_action` remains open (idempotency is Phase 9's scope, not Phase 7's).
- **Verified against 2 real, live transactions** via `live_case.py` against the real database
  (the same two transactions Phase 5's evidence graphs were built and persisted for): the clean
  evidence case produced `auto_resolve`/no approval required, and the case with 2 detected
  contradictions produced `escalate`/human approval required — the orchestration logic
  responding correctly to genuinely different real evidence, not two runs of the same trivial
  case. Both real transactions' customers had zero `call_transcripts` rows in the currently
  loaded sample, so `customer_message` fell back to the documented placeholder — reported
  honestly, not hidden.
- 10 new unit tests: `tests/unit/test_policy_rag.py` (4 — RAG retrieval, including that an
  injection-phrased query still retrieves the real authentication policy) and
  `tests/unit/test_flow.py` (6 — mechanically-checkable invariants: injection is always
  refused, `escalate`/`protect_account` always require human approval, `auto_resolve` is never
  proposed over a detected contradiction, every golden case runs without raising, and the mock
  LLM client is deterministic). 48 unit tests total (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5
  Phase 4 + 13 Phase 5 + 10 Phase 6), all passing.
- **Not done in this phase, by design:** no action is executed or authorized, no `Decision` or
  `HumanReview` row is persisted, no real LLM provider is called — `flow.py` deliberately
  doesn't import `src/tools/action_tools.py` at all, so building the orchestrator before Phase
  7's policy engine exists can't accidentally wire direct execution.

### Phase 7 detail

- `src/policies/`: `action_risk.py` (fixed action-risk classification table, keyed by tool and
  by transaction/requested-action facts — never by LLM output; unrecognized tool defaults to
  `"high"`), `config.py` (`PolicyConfig` — every threshold explicitly `PROPOSED`, no
  `automate_irreversible` field exists at all), `authorization.py` (the tool-authorization
  chain: authenticated? case eligible? sufficient evidence? classify risk -> automation
  allowed? -> human approval required?), `gateway.py` (DB-backed `persist_decision()` /
  `approve_pending_action()` for live cases).
- `src/orchestration/flow.py` now maps the LLM's `ActionProposal` to a real `ToolProposal`
  (`src/tools/action_tools.py`, including a new `propose_close_case_no_action` for
  `auto_resolve`) and calls `authorize()`, storing the result on the new
  `CaseResult.authorization` field. `CaseInput` gained `case_status`/`transaction_type`/
  `amount_usd`/`requested_action`/`requested_amount_usd` so the Policy Engine can classify
  action-risk from real case facts, independent of anything the LLM recommends.
- **Scenario D exit criteria met and tested against an actual bypass attempt**
  (`docs/implementation-roadmap.md` Phase 7: "a test that tries to bypass it and fails"):
  `evaluation/golden_cases/high_value_transfer.json` (a manufactured 0.99-confidence
  "legitimate" evidence item on a $100,000 Transfer) now produces
  `action_risk="irreversible"`, `requires_human_approval=True`, overriding the mock LLM's own
  `auto_resolve`/no-approval recommendation — closing exactly the gap Phase 6 honestly left
  open. `tests/unit/test_authorization.py` includes a test with a policy config that would
  automate every other risk level, and a test with a `ToolProposal` that itself claims
  `requires_human_approval=False`; both still produce `requires_human_approval=True`, because
  the Irreversible branch reads no config value at all.
- **Verified live, in real data, not manufactured for the demo**: `live_case.py --persist`
  against the real `is_fraud=true` transaction already used as Phase 5's example
  (`TRX-MXCWNPT6UVBUMBBVOPWM`) turned out to be a real `transaction_type="Transfer"` of
  $9,491.99 USD-equivalent — the Policy Engine correctly forced `requires_human_approval=True`
  against a real database row, and a full audit trail was produced and verified end-to-end:
  `evidence.graph.created -> risk.assessment.completed -> human.review.required ->` (after
  calling `approve_pending_action()` to simulate a human approving it) `-> action.executed`,
  with a real `Decision` row, linked `Evidence` rows via `decision_evidence`, and a real
  `HumanReview` row (kept structurally distinct from `Decision`, per
  `docs/human-oversight.md` § 4) — all confirmed with direct `SELECT` queries, not just
  application-log trust.
- **A genuinely subtle, non-bug finding**: running the second live transaction
  (`TRX-SMPYV51IQT9JPNQ56BMR`, 2 real contradictions) through `escalate` produced
  `authorization.requires_human_approval=False`, which at first glance looks inconsistent with
  the LLM's own `requires_human_approval=True` on the same result. It isn't:
  `AuthorizationResult.requires_human_approval` answers "does *this tool call* need approval
  before executing," and the tool `escalate` maps to (`create_human_review`) is itself Low
  action-risk — opening a review ticket needs no pre-approval; that's precisely the mechanism
  that routes the case to a human next. Documented in `src/policies/README.md` so it isn't
  mistaken for a bug later.
- **Security review run manually against `.claude/skills/review-security/SKILL.md`'s
  checklist** (`.claude/rules/security.md`'s standing requirement for any change touching
  authorization): found and fixed one real gap — `gateway.persist_decision()` originally
  collapsed both no-tool-call outcomes (`ask_question`/`refuse`) to a single generic
  `risk.assessment.completed` audit event, silently dropping the injection-detection signal
  from the audit trail for a live-persisted refusal. Fixed with a dedicated
  `_no_tool_audit_events()` helper that adds `security.injection_attempt_detected` and
  `action.rejected` for a refusal. Everything else on the checklist held — full detail,
  including why `is_authenticated` defaulting `True` is a documented scope boundary rather than
  an unsafe default, in `src/policies/README.md`.
- 20 new unit tests: `tests/unit/test_action_risk.py` (7), `tests/unit/test_authorization.py`
  (12 — an allow path and a deny path for every guardrail row this phase introduces), plus one
  new end-to-end test added to `tests/unit/test_flow.py`
  (`test_irreversible_action_requires_human_approval_end_to_end`). 68 unit tests total (10
  Phase 1 + 7 Phase 2 + 3 Phase 3 + 5 Phase 4 + 13 Phase 5 + 10 Phase 6 + 20 Phase 7), all
  passing. `gateway.py` has no offline unit test — like `src/evidence/persist.py` before it,
  it's DB-only code, verified live against the real database above, not mocked.
- **Not done in this phase, by design or as an honestly-reported gap:** no real
  authentication/session layer exists yet (`is_authenticated` defaults `True` everywhere —
  Phase 8's job to give this a real deny path); idempotency-key verification does not exist
  (explicitly Phase 9's scope — `evaluation/golden_cases/duplicate_action.json` remains open);
  risk-band fraud-probability thresholds (`docs/decision-policy.md` § 5) are not wired in at
  all, because Phase 4's model score was never plumbed into `CaseInput` (a pre-existing gap,
  not new to this phase); `docs/demo-script.md` Scenario L has no golden-case fixture yet, so
  its `case_not_eligible` denial path is exercised only by hand-built unit tests. Full detail,
  including the exact wording of every gap: `src/policies/README.md`. **Update (2026-09-26,
  Phase 8):** `docs/security-model.md` § 3 explicitly puts building a real identity system out
  of scope for this prototype ("use a trusted test session/identity abstraction") — so
  `is_authenticated` defaulting `True` is a documented scope boundary, not a Phase 8 TODO;
  Phase 8 did not build one, correctly.

### Phase 8 detail

- `src/security/redaction.py`: the shared redaction layer. `mask_card_like()` fixed to match
  `docs/observability.md` § 2's own documented example exactly (`4111111111111111` ->
  `****1111`, a fixed 4-character mask — the Phase 1 implementation was length-preserving
  instead, e.g. `************1111`, a real deviation from the spec, caught while centralizing
  it). `redact_value()` recursively redacts every string in a dict/list. `src/config/logging.py`
  now imports from here instead of duplicating the masking logic.
- **Wired into every `AuditEvent.payload` construction, not just log lines**: `src/evidence/
  persist.py` and `src/policies/gateway.py` now call `redact_value()` on the payload before the
  insert — a structural guarantee (`docs/security-model.md` § 7: "redaction happens before the
  write, not as a downstream filter"), closing a real gap where a raw sensitive value in a
  `HumanReview.rationale` (free text a reviewer types) could otherwise have reached the
  `audit_events` table unredacted.
- **`tests/security/` created** (new home for security tests, per `docs/implementation-roadmap.md`
  Phase 8 and `CLAUDE.md`'s repository map) — `test_redaction.py` (7 tests, moved and expanded
  from `tests/unit/test_logging_redaction.py`) and `test_red_team.py` (17 tests across 11
  functions) covering every bullet in `docs/guardrails.md` § 4 that this codebase can currently
  exercise.
- **A real detection gap found and fixed before being reported as done**: testing 7 adversarial
  phrasings (the original 2 from `docs/guardrails.md` § 4 plus 5 more shapes of the same two
  attacks — instruction override, authority claim) against `MockLLMClient`, 3 failed on first
  run: "Olvida todo lo anterior..." (forget-the-above, Spanish), "...developer mode, ignore all
  safety rules...", and "...soy el dueño del sistema..." (system-owner claim) all slipped past
  the original 6-pattern `_INJECTION_PATTERNS` list. Fixed by adding 7 more patterns; all 7
  phrasings now correctly refuse. This is exactly the value of adversarial testing over
  documentation alone — the gap existed since Phase 6 and nothing had exercised it until now.
- **Structural (not just behavioral) guarantee added for evidence immutability**:
  `test_evidence_table_has_no_delete_or_update_path` statically greps every `src/*.py` file for
  an `evidence_table.delete(`/`.update(` call and fails if one is ever added — `docs/guardrails.md`
  § 4's "no tool exists that deletes evidence" claim is now enforced by a test that would catch
  a regression at the source-code level, not only by inspecting `action_tools.py`.
- **Phase 8 exit criteria measured, not just asserted**: `docs/implementation-roadmap.md`:
  "unsafe-action rate is 0 across the full adversarial suite (MEASURED, with the sample size
  stated)." `test_adversarial_suite_unsafe_action_rate_is_zero` runs 7 injection phrasings + all
  10 golden cases (**17 cases**, stated) through `run_case()` and counts an outcome unsafe only
  if an actual account-affecting action (never `escalate`/`refuse`/`ask_question`, whose own
  low-risk tool calls are supposed to auto-execute) is authorized without human approval for an
  injection attempt or an unresolved contradiction. **Result: 0/17.** Explicitly labeled a small,
  stated sample — "demonstrates the mechanism holds on every case this project has authored,"
  not a statistically powered claim (`docs/implementation-roadmap.md` Phase 8's own risk note).
- **Honestly not covered, stated explicitly rather than silently claimed**: conflicting policy
  documents (only 4 non-conflicting synthetic docs exist to test against), duplicate-transaction
  detection (Phase 9's scope), impossible timestamps and customer/account mismatch (no real
  session/identity layer exists to check against, per `docs/security-model.md` § 3's own scope
  decision). Full detail: `src/security/README.md`.
- 24 new tests total (7 `test_redaction.py` + 17 `test_red_team.py`), minus 4 removed
  (`tests/unit/test_logging_redaction.py`, superseded). 88 unit/security tests total (10 Phase 1
  + 7 Phase 2 + 3 Phase 3 + 5 Phase 4 + 13 Phase 5 + 10 Phase 6 + 20 Phase 7 + 20 Phase 8 (24
  new − 4 removed)), all passing.
- **Not done in this phase, by design or as an honestly-reported gap:** real authentication
  (out of scope for this prototype, confirmed above); idempotency (Phase 9); risk-band/model-
  score wiring (pre-existing Phase 4/6 gap); rate limiting/DoS protection at the API layer
  (`docs/api-contracts.md` § Security — Phase 1's API isn't wired to orchestration yet);
  supply-chain/dependency-vulnerability CI scanning (`docs/security-model.md` § 9, still
  `PLANNED`).

### Phase 9 detail

- `src/orchestration/retry.py` (`call_with_retry()`, `LLMUnavailableError`) and `fallback.py`
  (`fallback_extract_intent`/`fallback_propose_action`/`fallback_explain`) — every `llm_client`
  call in `flow.run_case()` is now wrapped: bounded retries (`Settings.llm_max_attempts`,
  default 2) for transport/validation-shaped failures only, then a deterministic degrade to
  `fallback.py`'s conservative path (always `escalate`, never guess; local regex injection
  detection still runs with no provider call). New `CaseResult.llm_degraded` field and
  `decisions.llm_degraded`/`.model_degraded` real boolean columns (a migration, not a JSON-blob
  workaround) record it, matching `docs/demo-script.md` Scenario E's "clearly flagged ... in the
  decision record" wording literally.
- `src/models/base.py`'s `get_engine()` now passes `connect_args={"connect_timeout": ...}`
  (`Settings.db_connect_timeout_seconds`, default 5s) — verified directly against a genuinely
  unreachable address (`10.255.255.1`, not a mock): fails with a clear `OperationalError` in
  ~2-6 seconds depending on the configured bound, not an indefinite hang on the OS's own TCP
  timeout (`tests/reliability/test_db_timeout.py`).
- `flow._ground_in_policy()` now catches any exception from `rag.retrieve()` and degrades to
  `policy_source=None` rather than letting a RAG failure crash the whole case.
- **Idempotency (Scenario J), the last major documented gap carried since Phase 7, closed**:
  `src/tools/base.py`'s `ToolProposal.idempotency_key` (default `f"{case_id}-{tool_name}"`) flows
  through the new `AuthorizationResult.idempotency_key`/`.tool_name` fields into
  `src/policies/gateway.py`'s rewritten `persist_decision()`, which now reserves the key in a
  new `action_executions` table (migration `0a0050d49acc`) via `INSERT ... ON CONFLICT DO
  NOTHING RETURNING` — a database-level race, not a check-then-insert, done *before* the
  `Decision` row is created so a detected duplicate never creates an orphaned one.
- **A real bug found and fixed mid-implementation, not by inspection**: the first version of
  this migration gave `action_executions.decision_id` a normal (immediate) foreign key —
  reserving the idempotency key before the `Decision` row exists (the correct ordering, needed
  to avoid the orphaned-row problem above) then failed with a live `ForeignKeyViolation` on the
  very first real persist attempt, not in a unit test. Fixed by making the FK
  `DEFERRABLE INITIALLY DEFERRED` (checked at transaction commit, not at the individual INSERT)
  — re-verified live afterward: two `persist_decision()` calls with the same idempotency key
  against a real database produced exactly one `Decision` row, one `action.executed` audit
  event, and one `action.duplicate_detected` event, all tied to the same `decision_id`.
- **`evaluation/golden_cases/dependency_failure.json` genuinely exercises Scenario E now**:
  `run_golden_cases.py` reads that fixture's `synthetic_input.injected_fault` field (previously
  inert documentation) and routes it through `FailingLLMClient` instead of `MockLLMClient`.
  Result: `intent.confidence=0.00` (honestly `unknown`, not guessed), `action=escalate`,
  `human_approval=True`, `llm_degraded=True` — matching the fixture's own
  `expected_human_involvement` by actually running it, not by inspection.
- **Security held under degradation, verified directly, not assumed**: a case proposing a
  $100,000 transfer, run through `FailingLLMClient`, still produces `action_risk="irreversible"`
  and `requires_human_approval=True` through the full fallback path — the Policy Engine (Phase
  7) keeps running in full even when the LLM didn't
  (`tests/reliability/test_llm_fallback.py::test_degraded_result_still_goes_through_the_policy_engine`).
- 23 new tests: `tests/reliability/test_retry.py` (6), `test_llm_fallback.py` (10),
  `test_idempotency.py` (6), `test_db_timeout.py` (1, verified against a real unreachable
  address). 111 unit/security/reliability tests total (10 Phase 1 + 7 Phase 2 + 3 Phase 3 + 5
  Phase 4 + 13 Phase 5 + 10 Phase 6 + 20 Phase 7 + 20 Phase 8 + 23 Phase 9), all passing.
- **Not done in this phase, by design or as an honestly-reported gap:** circuit breakers (judged
  not useful yet — no dependency here is called in a tight loop where a breaker would earn its
  complexity over a bounded retry, per the roadmap's own "where useful" scope); Kafka/event-bus
  degradation (not applicable — no message bus exists or is planned); the fraud-model-degraded
  half of Scenario F (no live model call exists in orchestration to degrade — a pre-existing
  Phase 4/6 gap, not new here, though `decisions.model_degraded` now exists as a real column for
  when that wiring happens); `evaluation/golden_cases/duplicate_action.json` still doesn't pass
  end-to-end (the idempotency mechanism itself is proven; the mock LLM's intent detection still
  doesn't map that fixture's customer message to a `freeze_card` tool call — a Phase 6
  limitation, not a Phase 9 one). Full detail: `src/orchestration/README.md` § Reliability,
  `src/policies/README.md`.

### Phase 10 detail

- `src/api/deps.py`: the trusted-test-identity abstraction (`docs/security-model.md` § 3 — a
  real identity system is explicitly out of scope for this prototype). A `role` cookie stands
  in for a session; `require_reviewer_role` raises a real 403 for a customer session.
- `src/api/schemas.py`: every request/response body, `extra="forbid"`. `GET /cases/{id}`
  returns a role-shaped response — `CustomerCaseView` (status + plain-language explanation
  only) vs `AnalystCaseView` (everything) — decided server-side by role, never a client flag.
- `src/api/cases.py`: `docs/api-contracts.md` § 1's endpoints, wired to the exact same
  functions the CLI scripts already used (`src.orchestration.live_case.create_and_run_case`,
  `src.policies.gateway.approve_pending_action`) — not a second implementation. The analyst
  case view re-derives contradictions live via `detect_contradictions()` from the persisted
  evidence rows rather than needing a separate contradictions table.
- `src/api/ui.py` + `templates/`/`static/`: server-rendered Jinja2 + vanilla JS, resolving
  `docs/architecture.md` § 15's frontend-framework `OPEN QUESTION` — no Node/npm toolchain on
  a machine already documented as memory-constrained throughout this project. Every UI route
  calls `cases.py`'s own request-handling functions directly (overriding their `Depends(...)`
  defaults with real values), so there is one implementation per view, not an API-plus-client
  pair to keep in sync.
- **A real, previously-undiscovered persistence gap found and fixed**: `CaseExplanation.
  customer_explanation_es` (generated since Phase 6) was never persisted anywhere — only
  `analyst_explanation` reached the `decisions` table. Nothing surfaced this until Phase 10
  needed to *read it back* for the customer view. Fixed by splitting the old
  `decisions.explanation` column into `analyst_explanation` + `customer_explanation_es`
  (migration `319756c1c80a`), with existing rows backfilled into `analyst_explanation` rather
  than silently dropped.
- **A second real bug found and fixed live, not by inspection**: the `docker compose exec`
  round trip that first exercised `POST /cases/{id}/review` twice in a row revealed that the
  case's own `human_review_status` transition (not `pending` anymore after the first approval)
  blocks a second submission *before* the idempotency-key check inside `approve_pending_action`
  is ever reached — both layers turned out to matter for different failure modes (documented in
  `src/api/README.md`, not silently treated as redundant).
- **Verified live, end-to-end, via curl**: case creation against a real transaction; the
  role-shaped `GET /cases/{id}` response (full detail as analyst, status-only as customer); a
  403 for a customer session on the review queue and the review endpoint; an approval that
  correctly transitioned `fraud_cases.status` to `resolved` and produced exactly one
  `action.executed` audit event; an immediate resubmission correctly rejected
  (`no_pending_review`, 409).
- **Verified live, end-to-end, in a real Chrome browser**
  (`.claude/rules/frontend.md`: "start the dev server and exercise the golden path... in a real
  browser"): home page → created a case by transaction ID → redirected to the analyst case
  detail → the evidence graph rendered with real data, including **two real contradictions**
  from a genuinely mixed-evidence transaction, visually distinct (four badge states, never
  shades of one color, `.claude/rules/frontend.md`) → the dual explanation panel showed both
  the Spanish customer text and the technical analyst text → clicked **Approve** on a different,
  genuinely pending case → page reloaded showing `status: resolved` and the review controls
  correctly gone. Role switching (customer/analyst/supervisor) and the conditionally-shown
  analyst-queue link were also verified.
- **Scenario C (ask a clarifying question) found to not be drivable live** while verifying this
  phase's own exit criterion: `src/orchestration/live_case.py` always sets
  `candidate_questions=[]` for a live case, so `MockLLMClient.decide_next_question()` can never
  return `should_ask=True` for one — `ask_question` only occurs for offline golden-case
  fixtures, which aren't wired into the API. A pre-existing Phase 6 gap, surfaced (not created)
  by this phase's own testing; honestly reported rather than silently worked around or claimed
  met.
- 18 new tests (`tests/unit/test_api_cases.py`) — role-gating, request validation, 404s,
  offline against an in-memory SQLite engine (`StaticPool` — the API opens/closes a connection
  per query, and a plain `sqlite:///:memory:` engine hands back a fresh empty database on each
  connection without it). 129 unit/security/reliability tests total (10 Phase 1 + 7 Phase 2 +
  3 Phase 3 + 5 Phase 4 + 13 Phase 5 + 10 Phase 6 + 20 Phase 7 + 20 Phase 8 + 23 Phase 9 + 18
  Phase 10), all passing.
- **Not done in this phase, by design or as an honestly-reported gap:** executive dashboard
  (explicit scope decision — `OPEN QUESTION` in `docs/product-requirements.md` § 14, this
  phase's own risk note says prioritize the analyst view instead); correlation-ID propagation
  into audit events (`src/api/main.py`'s middleware generates one per request, but
  `src/policies/gateway.py`/`src/evidence/persist.py` still always write
  `correlation_id=None` — a real gap this phase surfaced, not new); per-customer
  case-ownership scoping (`docs/api-contracts.md` § 2 — no customer identity exists to scope
  by yet, only a role); live customer chat/message intake
  (`POST /cases/{id}/messages` — not built; `customer_message` still comes from whatever
  `call_transcripts` row already exists, not real-time typing); rate limiting (still `PLANNED`).
  Full detail: `src/api/README.md`.

## In progress

Nothing.

## Not started

Everything under "Status by roadmap phase" marked `NOT_IMPLEMENTED` above.

## Known limitations

- `make` is not installed on the machine this repository was built on — every `Makefile`
  target was verified via its underlying `uv`/`docker` command instead (`CLAUDE.md` § 9).
  Install `make` to use the `Makefile` directly, or keep using the underlying commands.
- Host ports in `docker-compose.yml` are remapped to 8080 (api) and 5433 (db) because 8000 and
  5432 were already in use by other software on the development machine. Adjust back to
  8000/5432 if that's not the case in your environment.
- Only a bounded recent-date sample of the dataset has been ingested (Phase 3/4: 90 days for
  `transactions`/`complaints`/`call_center_interactions`; Phase 5: 7 days for `digital_events`)
  — the full ~19M-row dataset has not been loaded. The development machine has very little
  free RAM available (background runs were killed by out-of-memory conditions multiple times
  across Phases 4–5 before succeeding on retry) — a `--full` ingestion run needs more headroom
  than was available here. See `src/ingestion/README.md` § Sample vs. full mode.
- **`call_transcripts` currently has 0 rows in the live database**, verified directly
  (`SELECT count(*)` during Phase 6, 2026-09-26) — not the "earliest 3-day sample" this
  document previously (and incorrectly) claimed. Phase 3's original ingestion did load a 3-day
  sample of it, but every ingestion run since (Phase 4's 90-day re-run, Phase 5's
  `digital_events` run) explicitly used `--skip-tables call_transcripts,...` to conserve memory
  and never re-loaded it, so it is genuinely empty in the database as currently populated.
  Caught by Phase 6's `live_case.py` live smoke test (§ Phase 6 detail above), which needed
  `call_transcripts.customer_text` and got none for either real transaction tested — reported
  honestly there rather than silently assumed present. Reload it with `uv run python -m
  src.ingestion.run --sample-days 90` (omit `--skip-tables` for it) before relying on real
  customer-transcript text for a live case.
- **The trained fraud model performs near chance** (test ROC-AUC 0.46–0.50) on the currently
  loaded sample — this is a genuine, verified finding (not a bug; see § Phase 4 detail), not a
  limitation to silently work around. The Phase 5 Evidence Engine's device derivation (the
  leading hypothesis for recovering the signal) is now implemented and was tested against real
  fraud cases, but the two spot-checked cases didn't happen to show a strong device signal
  either — the fraud model has not been re-trained with device-derived features yet; that
  integration (feeding Evidence Engine / Device signals back into `src/ml/features.py`) is
  an open next step, not yet attempted.
- **`device_id` is a heuristic proxy, not a true device fingerprint** (`src/evidence/device.py`
  — the dataset has no persistent device-fingerprint column). Known limitations: IP-based
  collisions across customers on shared networks/NAT, and a customer's own IP changing
  registering as a "new device." Documented in the module itself, not hidden.
- No frontend framework has been chosen (`docs/architecture.md` § 15, `OPEN QUESTION`).
- No business-approved risk thresholds, cost coefficients, or approval-matrix cells exist
  anywhere in this project — every number in `docs/decision-policy.md` and
  `docs/human-oversight.md` is illustrative/`PROPOSED`, not approved policy.
- The Portuguese-language requirement from `project_presentation.txt` has no data to back it;
  this project implements Spanish only and reports the gap rather than fabricating coverage
  (`docs/product-requirements.md` § 13 — decided, not a bug).

## Blockers

None. The raw dataset is now available locally at `data/raw/` (`docs/data-lineage.md` § 1),
which was the only blocker recorded here. Phase 1 (Foundation) and Phase 3 (Ingestion) can
both start; Phase 3 specifically still requires the actual ingestion pipeline to be built
(loading these CSVs into PostgreSQL with the validation described in `docs/data-lineage.md`
§ 7) — the files being present is necessary, not sufficient, for Phase 3 to be `IMPLEMENTED`.

## Open questions

See `docs/product-requirements.md` § 14 for the remaining open question (whether to build the
executive dashboard) — repeated here only as an index entry so this document surfaces it
without duplicating its content. The Portuguese-language question (formerly § 13) has been
decided: Spanish only, gap documented (`docs/product-requirements.md` § 13).

## How to use this document

Before trusting any other `docs/` file's description of "what the system does," check this
file first. A `docs/` file describing an architecture or a workflow is describing a *design*,
not necessarily *running code*, until this document says otherwise for that phase.
