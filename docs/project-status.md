# Project Status

Owns: verified current implementation state. This document must never represent planned
functionality as implemented. Update it whenever a meaningful implementation phase
(`docs/implementation-roadmap.md`) completes, changes, or blocks.

**Last meaningful update:** 2026-09-25 (Phase 3 — Ingestion implemented and verified).
**Last validation:** 2026-09-25 — actually run, not just inspected: `uv run ruff check .`
(clean), `uv run mypy src` (clean, 39 files), `uv run pytest` (20/20 passed), a full
`--sample-days 3` ingestion run against a live `docker compose` Postgres with the resulting
report's per-table counts cross-checked against `SELECT count(*)` on every one of the 8 loaded
tables — **exact match on every table** (`docs/data-lineage.md` § 7, § Phase 3 detail below),
plus `alembic check` (zero schema drift) after adding the 5 new source-table models.

## Current phase

Phase 3 (Ingestion) complete. This repository now contains: the original master prompt
(`prompt.md`), the competition brief (`project_presentation.txt`), the LATAM Bank dataset
documentation (two PDFs at the repository root), the raw LATAM Bank dataset itself
(`data/raw/`, git-ignored, ~5.0 GB — `docs/data-lineage.md` § 1), the Claude Code operating
system (`CLAUDE.md`, `docs/`, `.claude/`, `evaluation/golden_cases/`), a working application
foundation (Phase 1), a complete, migrated domain schema (Phase 2), and now a working,
verified ingestion pipeline that has actually loaded real (synthetic) data into that schema
(Phase 3).
**No fraud model, no orchestration, no policy engine — those are Phases 4+. Only a bounded
recent-date sample has been loaded, not the full ~19M-row dataset — see § Phase 3 detail.**

## Status by roadmap phase (`docs/implementation-roadmap.md`)

| Phase | State |
|---|---|
| 1 — Foundation | IMPLEMENTED — see § Phase 1 detail below |
| 2 — Domain | IMPLEMENTED — see § Phase 2 detail below |
| 3 — Synthetic Data / Ingestion | IMPLEMENTED — see § Phase 3 detail below (sample-mode verified; `--full` not yet run in this environment, see `src/ingestion/README.md`) |
| 4 — Fraud ML | NOT_IMPLEMENTED |
| 5 — Evidence Engine | NOT_IMPLEMENTED |
| 6 — AI Agent | NOT_IMPLEMENTED |
| 7 — Policy Engine | NOT_IMPLEMENTED |
| 8 — Security Hardening | NOT_IMPLEMENTED |
| 9 — Reliability | NOT_IMPLEMENTED |
| 10 — UI | NOT_IMPLEMENTED |
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
- **Phase 1 — Foundation** and **Phase 2 — Domain**, detailed below.

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
- Only a bounded recent-date sample of the dataset has been ingested (Phase 3,
  `--sample-days 3` verified) — the full ~19M-row dataset has not been loaded. The development
  machine has very little free RAM available; a `--full` ingestion run needs more headroom
  than was available here — see `src/ingestion/README.md` § Sample vs. full mode.
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
