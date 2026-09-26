# Project Status

Owns: verified current implementation state. This document must never represent planned
functionality as implemented. Update it whenever a meaningful implementation phase
(`docs/implementation-roadmap.md`) completes, changes, or blocks.

**Last meaningful update:** 2026-09-25 (Phase 1 — Foundation implemented and verified).
**Last validation:** 2026-09-25 — actually run, not just inspected: `uv sync`, `uv run ruff
check .` (clean), `uv run mypy src` (clean, 16 files), `uv run pytest` (10/10 passed),
`docker compose build` + `docker compose up -d` (both containers healthy, `GET /api/v1/health`
returned `200 {"status":"ok",...}` with a `X-Correlation-ID` header), `docker compose down`
(clean teardown), `uv run pre-commit run --all-files` (config valid; hooks reported "no files
to check" only because nothing is committed to git yet — expected, not a failure).

## Current phase

Phase 1 (Foundation) complete. This repository now contains: the original master prompt
(`prompt.md`), the competition brief (`project_presentation.txt`), the LATAM Bank dataset
documentation (two PDFs at the repository root), the raw LATAM Bank dataset itself
(`data/raw/`, git-ignored, ~5.0 GB — `docs/data-lineage.md` § 1), the Claude Code operating
system (`CLAUDE.md`, `docs/`, `.claude/`, `evaluation/golden_cases/`), and a working
application foundation: `src/` package skeleton, a FastAPI health-check service, structured
JSON logging with mandatory redaction, environment-based config, Docker/Docker Compose, a
Makefile, CI, pre-commit, and 10 passing unit tests.
**No domain models, no database schema, no fraud model, no orchestration, no policy engine —
those are Phases 2+.**

## Status by roadmap phase (`docs/implementation-roadmap.md`)

| Phase | State |
|---|---|
| 1 — Foundation | IMPLEMENTED — see § Phase 1 detail below |
| 2 — Domain | NOT_IMPLEMENTED |
| 3 — Synthetic Data / Ingestion | NOT_IMPLEMENTED (raw dataset files now present locally at `data/raw/` — see `docs/data-lineage.md` § 1 — but no ingestion pipeline/code exists yet) |
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
- **Phase 1 — Foundation**, detailed below.

### Phase 1 detail

- `pyproject.toml` (uv-managed, `package = false` — this is an application, not a published
  library) with `fastapi`, `uvicorn`, `pydantic`/`pydantic-settings`, `sqlalchemy`,
  `python-dotenv`; dev group: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`,
  `pre-commit`. `uv.lock` committed for reproducibility.
- `src/` package skeleton matching `docs/architecture.md`: `config` (settings + logging,
  populated), `api` (populated), and `agents`/`orchestration`/`models`/`policies`/`tools`/
  `evidence`/`retrieval`/`security`/`monitoring` (package markers only, each documenting which
  later phase fills it in — not empty placeholders, but not yet functional either).
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
