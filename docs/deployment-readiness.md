# Deployment Readiness

Owns: an honest account of what remains before real deployment (`docs/implementation-roadmap.md`
Phase 14). This is a **documentation-only** deliverable — no production action, deployment,
credential, or infrastructure change is taken anywhere in this document or its production
(`.claude/rules/infrastructure.md`, `CLAUDE.md` § 7). Nothing here is executed; it is a
checklist for a future team that decides to actually deploy this project, written by the team
that built it while the context is fresh.

See `docs/final-report.md` for the concise summary this document backs up in detail, and
`docs/architecture.md` § 13 for the local-only deployment model actually in place today: `docker
compose up` running the API and PostgreSQL — no production target exists or is authorized in
this project.

## 1. Container/infrastructure requirements

**What exists today:** `Dockerfile` (API image, pinned dependencies via `uv.lock`),
`docker-compose.yml` (api + db, plus an optional `monitoring` profile — Prometheus + Grafana,
`infrastructure/`). Verified: `docker compose build`, `docker compose up -d`, migrations apply
cleanly against a fresh Postgres (`alembic upgrade head`).

**What a real deployment would need, not built here:**

- A container orchestrator (ECS/EKS/GKE/Cloud Run — `prompt.md` § 7's stated AWS-compatible
  target is a design intent, not something this repository deploys) with health-check-gated
  rolling deploys, not a single `docker compose up` host.
- A managed Postgres (RDS/Cloud SQL) with automated backups, point-in-time recovery, and a
  read replica for the analyst-view read load — the current single-container Postgres with a
  local `pgdata` volume has none of that.
- Secrets management (AWS Secrets Manager/Vault/equivalent) — today, `.env` (git-ignored) with
  `${VARIABLE}`-style placeholders in `.env.example` is the entire mechanism; adequate for local
  development, not for a real deployment's credential rotation/audit requirements.
- A load balancer / TLS termination in front of the API — the API currently serves plain HTTP on
  a host-mapped port with no TLS anywhere in this project.
- An image registry and a CI/CD pipeline stage that builds, scans, and promotes the Docker image
  — `.github/workflows/ci.yml` runs lint/typecheck/test/demo today; it does not build or push an
  image anywhere.
- Horizontal scaling for the API (stateless already — no in-process session state beyond the
  trusted-test-identity cookie, `src/api/deps.py`) behind the load balancer above.
  `docs/architecture.md` § 12's 10/100/1000 cases/sec figures are unvalidated design targets,
  not load-test results — no load test has been run against this project at any scale.

## 2. Rollback plan

**What exists today:** every migration is a reviewed, generated Alembic revision with a real
downgrade path (`alembic downgrade -1` verified reversible during Phase 2); every
model/prompt/policy referenced by a `Decision` carries an explicit version
(`model_version`/`prompt_version`/`policy_version` — `docs/decision-policy.md` § 9), so a past
decision is reconstructable and comparable against a rolled-back version once one exists.
`MockLLMClient` has no versioning concern (no live provider integration exists to roll back).

**What a real deployment would need, not built here:**

- A documented rollback procedure for the **application image** (redeploy the previous tagged
  image) — no deployment mechanism exists yet to roll back in the first place (§ 1).
- A documented rollback procedure for a **bad migration already applied in production** — this
  project's migrations are reversible in the schema sense (`alembic downgrade`), but no runbook
  exists for coordinating a schema rollback against already-written application-level data if a
  migration and a subsequent write are both bad.
- A rollback trigger/decision owner (who decides to roll back, and against what signal —
  presumably the alert rules in `infrastructure/prometheus/alerts.yml`, but no on-call/paging
  integration exists; those alerts are visible in Prometheus's own UI only, per
  `src/monitoring/README.md`).
- A prompt/policy-version rollback procedure once a real, versioned prompt template and a real,
  business-approved policy-threshold source exist (neither does yet — `docs/decision-policy.md`
  § 10, `docs/human-oversight.md` § 2).

## 3. Operational readiness checklist

| Item | Status |
|---|---|
| Structured logging | `IMPLEMENTED` (`src/config/logging.py`, JSON, redacted) |
| Metrics | `IMPLEMENTED` (`src/monitoring/metrics.py`, `GET /metrics`, Phase 13) |
| Tracing | `IMPLEMENTED` (`src/monitoring/tracing.py`, a custom recorder — `docs/decisions/ADR-0001-tracing-without-opentelemetry.md`) |
| Dashboards | `IMPLEMENTED`, local-only (`infrastructure/grafana/`, opt-in `monitoring` profile) |
| Alerting rules defined | `IMPLEMENTED` (`infrastructure/prometheus/alerts.yml`, 4 rules against real metrics) |
| Alerting rules actually paging someone | `NOT_IMPLEMENTED` — no Alertmanager/PagerDuty/on-call integration exists; alerts are visible in Prometheus's own UI only |
| Health check endpoint | `IMPLEMENTED` (`GET /api/v1/health`) |
| Readiness vs. liveness distinction | `NOT_IMPLEMENTED` — one health endpoint serves both purposes today; a real orchestrator deployment would want them split (e.g., readiness should fail while migrations are pending) |
| Runbooks (what to do when an alert fires) | `NOT_IMPLEMENTED` — no runbook exists for any of the 4 alert rules beyond the one-line `summary`/`description` in the rule itself |
| Incident reconstruction | `IMPLEMENTED`, verified live (`src/monitoring/README.md` § Incident reconstruction — trace spans + one `audit_events` query by a shared correlation ID) |
| On-call rotation / paging | `NOT_IMPLEMENTED` — no team/rotation exists; this is a hackathon submission, not a staffed service |
| Backup/restore drill | `NOT_IMPLEMENTED` — the local `pgdata` Docker volume has never been backed up or restored; no backup mechanism exists |
| Log retention configured | `NOT_IMPLEMENTED` — logs go to each container's own stdout only; no aggregation/retention backend exists (`src/monitoring/README.md` § What this phase does not do) |
| Dependency vulnerability scanning in CI | `NOT_IMPLEMENTED` (`docs/security-model.md` § 9, `PLANNED`) |
| Rate limiting | `NOT_IMPLEMENTED` (`docs/api-contracts.md` § 2, `PLANNED`) |
| TLS | `NOT_IMPLEMENTED` — plain HTTP only, local development target |

## 4. Capacity limits

Nothing in this project has been load-tested — every number below is either a documented design
target (labeled as such per `docs/evaluation-plan.md` § 1) or a known, verified constraint of
the actual development environment this was built on:

- **Design target, not measured:** 10/100/1000 cases/sec (`docs/architecture.md` § 12).
- **Verified constraint of the dev environment, not the architecture:** the development machine
  has repeatedly hit out-of-memory conditions during bounded ingestion runs (as little as ~1.5
  GB free observed at times, `docs/project-status.md` § Known limitations) — this reflects the
  laptop this was built on, not a limit inherent to the ingestion pipeline's design, which
  already batches inserts and streams CSV partitions rather than loading the whole dataset into
  memory at once (`src/ingestion/README.md`).
  a `--full` ingestion run (the entire ~19M-row dataset) has never been attempted end-to-end for
  exactly this reason.
- **Not measured, no target set:** database connection pool sizing, request queue depth,
  per-request memory footprint under concurrent load, LLM-call concurrency limits (moot today —
  `MockLLMClient` has no rate limit or real concurrency ceiling to characterize).
- **Known, current, single-process limitation:** `uv run uvicorn src.api.main:app --reload` runs
  one process; the Docker image's `Dockerfile` also runs a single worker — no multi-worker/
  multi-process configuration has been tested.

## 5. Monitoring plan

**Implemented, local-only** (`src/monitoring/README.md`, full detail): Prometheus scrapes
`GET /metrics` every 15s; 4 alert rules evaluate against real metrics
(`UnsafeActionDetected`, `ElevatedHttpErrorRate`, `ElevatedLlmDegradedRate`,
`HighRequestLatencyP99`); a 10-panel Grafana dashboard covers system/LLM/security/tool/business
metric groups. All behind docker-compose's opt-in `monitoring` profile.

**What a real deployment's monitoring plan would additionally need:**

- Alert routing to a real paging system (Alertmanager → PagerDuty/Opsgenie/Slack) — today an
  alert firing is only visible to someone actively looking at Prometheus's own `/alerts` page.
- SLO definitions with error budgets, not just point alert thresholds (the current
  `ElevatedHttpErrorRate`/`HighRequestLatencyP99` rules are reasonable starting thresholds, not
  SLO-derived).
- A drift-monitoring pipeline once the Fraud ML model is actually wired into live orchestration
  (§ Known limitations, `docs/final-report.md`) — nothing exists to monitor drift against today.
- Cost monitoring once a real LLM provider is used (`MockLLMClient` makes no billable call —
  `docs/observability.md` § 6 explains why a `SIMULATED` cost figure was deliberately not
  fabricated for Phase 13).
- Synthetic/canary monitoring (a scheduled probe running the golden-case suite or a fixed
  transaction against the live deployment) — the closest existing analog is `demo/run.py`, which
  is designed to run on demand/in CI, not as a scheduled production probe.

## 6. Access-control plan

**What exists today:** role-scoped authorization for the three internal roles this prototype
defines (customer, analyst, supervisor) via a trusted-test-identity cookie
(`src/api/deps.py`) — a customer session gets a real 403 on the review queue and review
endpoint, server-enforced, not just hidden in the UI (`.claude/rules/frontend.md`). This is
explicitly **not** a real identity system (`docs/security-model.md` § 3) — it stands in for one,
honestly labeled everywhere it's used.

**What a real deployment would need, not built here:**

- A real identity provider (SSO/OIDC) issuing verifiable tokens, replacing the trusted-test-
  identity cookie entirely.
- Per-customer case-ownership scoping ("a customer session can only read/act on their own
  cases") — there is no customer identity to scope by yet, only a role
  (`docs/api-contracts.md` § 2, honestly reported there as not yet implemented).
- Service-to-service authorization between the API, orchestrator, and database layers — every
  internal call currently shares one database credential; a compromised layer could reach
  further than it should (`docs/security-model.md` § 4, `PLANNED`).
- Secrets/credential access control (who can read the production `DATABASE_URL`, LLM API key
  once one is used, etc.) — moot today since no production credential exists, but the
  mechanism (§ 1's secrets manager) needs an access policy, not just storage.
- Audit of access-control changes themselves (who granted/revoked which role, when) — today,
  role assignment is a self-service cookie set via `POST /api/v1/cases/session`, appropriate
  only for a trusted-test-identity prototype.
- `GET /metrics` needs authentication or network-level restriction before any real deployment —
  it is currently open, local-dev-only (`src/monitoring/README.md`).

## 7. Data-retention plan

**Design position, not yet an approved policy** (`docs/data-governance.md` § 4, `TBD`/`OPEN
QUESTION`): implement retention as configurable from the start rather than hardcoding "keep
forever," since real deployment will need it, even though this prototype's synthetic-only data
makes retention risk low today. Concretely, not built here:

- No retention period is configured for any table — `fraud_cases`, `evidence`, `decisions`,
  `human_reviews`, and `audit_events` all accumulate indefinitely in the local database.
- Audit logs likely need longer retention than application logs for compliance purposes
  (`docs/data-governance.md` § 4) — no differential retention mechanism exists.
- No deletion/right-to-erasure mechanism exists for `customers` or related rows — not required
  for synthetic data, would be required before any real customer data is ever loaded.
- **Jurisdiction-specific compliance is an unresolved open question**: the dataset spans three
  jurisdictions (Mexico, Colombia, Argentina) with distinct data-protection regimes; no
  jurisdiction-specific legal analysis has been done (`docs/data-governance.md` § 11).
  `Requires legal/compliance validation.` before any real deployment, per that document's own
  § 12 — nothing in this repository constitutes a compliance determination.
- Evidence and audit records are append-only by design (no `UPDATE`/`DELETE` path exists at the
  schema or application level, enforced by a static test —
  `tests/security/test_evidence_table_has_no_delete_or_update_path`) — this is a deliberate
  integrity guarantee, and any future retention/deletion mechanism must be built as an explicit,
  audited exception to it, not a bypass.

## 8. Remaining deployment work (honest summary)

In rough dependency order, if this project were to move toward a real deployment:

1. Resolve the compliance/jurisdiction open question (§ 7) and obtain a business-approved policy
   for every threshold this repository currently marks `PROPOSED`/`TBD` (risk bands,
   action-risk-to-approval mapping, retention periods, cost coefficients) — a business/legal
   decision this engineering project does not make unilaterally.
2. Replace the trusted-test-identity abstraction with a real identity provider (§ 6) and add
   per-customer case-ownership scoping.
3. Wire the Fraud ML model's score into live orchestration (the single most-referenced
   pre-existing gap across Phases 4/6/7/9/11/13 — `docs/final-report.md` § Known limitations) —
   this also unblocks drift monitoring (§ 5) and closes demo Scenario F.
4. Stand up real infrastructure (§ 1): managed Postgres, secrets manager, container
   orchestrator, TLS, image registry/CI-CD promotion pipeline.
5. Add authentication/authorization hardening beyond the trusted-test-identity model: rate
   limiting, `GET /metrics` access control, service-to-service authorization, dependency
   vulnerability scanning in CI.
6. Add real alert routing/paging, runbooks per alert, an on-call rotation, and a backup/restore
   drill (§ 3, § 5) — this project is a hackathon submission, not a staffed service, and none of
   this exists today.
7. Load-test against the design targets in `docs/architecture.md` § 12 and revise them from
   design targets to measured capacity limits (§ 4).
8. Only then: a real, authorized production deployment — explicitly out of scope for this
   project and never taken here (`CLAUDE.md` § 7).

None of the above is started in this repository beyond the documentation you're reading — that
is a deliberate scope boundary for a ten-day/hackathon-scale prototype
(`docs/product-requirements.md` § 10), not an oversight.
