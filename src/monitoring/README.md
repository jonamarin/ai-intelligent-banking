# Observability (Phase 13)

```
uv run pytest tests/unit/test_metrics.py tests/unit/test_tracing.py -q   # offline
uv run uvicorn src.api.main:app --reload --port 8080   # then curl http://localhost:8080/metrics
make monitoring-up     # optional: Prometheus (:9090) + Grafana (:3000), local-only
make monitoring-down
```

Implements `docs/observability.md` (that document owns the *what*; this one is the *how* and
*what's actually wired*). See `docs/decisions/ADR-0001-tracing-without-opentelemetry.md` for why
tracing is a small custom recorder, not the OpenTelemetry SDK originally listed in `CLAUDE.md`
§ 5's confirmed stack.

## What's real

- **Structured logs** (Phase 1, `src/config/logging.py`) — JSON, redacted, correlation-ID
  aware. Unchanged this phase except one addition: a log record can now carry a structured
  `event_data` dict (used by `tracing.span`) that gets merged into the JSON payload, so trace
  spans and free-text logs share one schema.
- **Metrics** (`src/monitoring/metrics.py`) — real Prometheus counters/histograms, incremented
  at real call sites, not declared-and-unfed:
  - System: `http_requests_total`, `http_request_duration_seconds` (`src/api/main.py`'s request
    middleware), `db_query_duration_seconds` (a SQLAlchemy `before/after_cursor_execute` event
    hook, `src/monitoring/instrumentation.py`, wired into every engine `src/models/base.get_engine()`
    creates).
  - LLM: `llm_calls_total{stage,outcome}`, `llm_call_duration_seconds{stage}`,
    `cases_llm_degraded_total` (`src/orchestration/flow.py`'s `_traced_llm_call`/`_degraded_result`).
  - Security: `injection_attempts_detected_total`, `unsafe_actions_total` (same definition
    `tests/security/test_red_team.py::test_adversarial_suite_unsafe_action_rate_is_zero` proves
    offline — must always be 0).
  - Tools/policy: `tool_calls_total{tool_name,authorized,requires_human_approval}`.
  - Business: `business_fraud_cases_total`, `business_automation_rate`,
    `business_human_escalation_rate` — computed live from the database on every scrape
    (`BusinessMetricsCollector`), not accumulated counters, and bounded to 3 seconds
    (`_query_with_timeout`) so a slow/unreachable database degrades the scrape to "no business
    metrics" rather than hanging it (see the two real bugs below).
  - `GET /metrics` (`src/api/main.py`) renders them in Prometheus text format. No auth — a
    local-dev endpoint on a project with no production deployment (`CLAUDE.md` § 7); a real
    deployment would need to lock this down, noted as a gap, not solved here.
- **Traces** (`src/monitoring/tracing.py`) — one span per HTTP request
  (`src/api/main.py`), one root `case.run` span per `run_case()` call plus child spans for every
  LLM stage, RAG retrieval, and policy authorization (`src/orchestration/flow.py`). Spans are
  structured JSON log lines (`event: "trace.span"`), correlated by `trace_id` (seeded from the
  request's `X-Correlation-ID`, or a fresh UUID for a direct CLI/script call,
  `src/orchestration/live_case.py`) and redacted before they reach the log sink
  (`tests/unit/test_tracing.py::test_span_attributes_are_redacted_before_they_reach_the_log`).
- **Audit logs** (Phase 2/7/9) — unchanged in shape; this phase fixed a real, previously-honestly-
  documented gap (`docs/project-status.md` § Phase 10 detail): `src/policies/gateway.py`'s
  `AuditEvent.correlation_id` was always written as `None`. It now reads
  `tracing.current_trace_id()`, so a Decision/AuditEvent row and the request/trace that produced
  it share one identifier — see § Incident reconstruction below for this proven end-to-end.
- **Dashboards + alerts** — `infrastructure/prometheus/prometheus.yml` (scrapes the `api`
  service), `infrastructure/prometheus/alerts.yml` (real rules against real metrics —
  `UnsafeActionDetected`, `ElevatedHttpErrorRate`, `ElevatedLlmDegradedRate`,
  `HighRequestLatencyP99`), `infrastructure/grafana/` (auto-provisioned Prometheus datasource +
  one dashboard, `infrastructure/grafana/dashboards/fraud-investigator.json`, 10 panels covering
  every metric group above). All behind docker-compose's `monitoring` profile — never started by
  a plain `docker compose up`, since this project's dev machine has been memory-constrained
  throughout (`docs/project-status.md` § Known limitations) and most work doesn't need it running.

## Two real bugs found and fixed while verifying this phase

Both caught by the test suite genuinely, reproducibly slowing down — 133s instead of ~9s for the
full run — not by inspection.

1. **A DB timeout that wasn't actually bounded.** `Settings.db_connect_timeout_seconds` bounds
   the TCP connect step, but not DNS resolution ahead of it. Resolving the `.env` default's `db`
   hostname (correct only *inside* docker-compose's network) from the bare host took as long as
   ~60 seconds the first time in a process on this Windows development machine — far past
   Prometheus's own default 10s scrape timeout. Fixed by giving `BusinessMetricsCollector` its
   own explicit, independent 3-second wall-clock bound around the whole query
   (`_query_with_timeout`), rather than trusting `connect_timeout` alone.
2. **A duplicate-registration bug in the fix for bug 1's own safety net.** The first version of
   `register_business_metrics` relied on `CollectorRegistry.register()` raising `ValueError` on
   a duplicate collector name. That never actually triggered:
   `prometheus_client` only detects a name collision for collectors implementing `describe()`,
   which `BusinessMetricsCollector` doesn't — so every `create_app()` call (once per test
   building its own app in `tests/unit/test_api_cases.py`, 18 times) silently registered a *new*
   collector instance instead of being rejected. Each one independently queried the database on
   every `/metrics` scrape, serializing up to 18× the per-collector DNS-failure latency into one
   call. Fixed with an explicit module-level guard
   (`tests/unit/test_metrics.py::test_register_business_metrics_is_idempotent_per_process`).

## Incident reconstruction (Phase 13 exit criterion) — verified live

`docs/implementation-roadmap.md` Phase 13: "an incident can be reconstructed from traces + audit
log alone, demonstrated on a seeded scenario." Reproduced against a real, live Postgres (not
offline, not simulated): `docker compose up -d db api`, then

```
curl -X POST http://localhost:8080/api/v1/cases \
  -H "X-Correlation-ID: INCIDENT-DEMO-1790622208" \
  -d '{"transaction_id": "TRX-MXCWNPT6UVBUMBBVOPWM"}'
# -> {"case_id":"CASE-6CB4F4788AEF45B297B3", "decision_id":"0a3c3998-...",
#     "proposed_action":"auto_resolve", "requires_human_approval":true, "authorized":true, ...}
```

1. **Filtering the container's log stream for that `trace_id`** (`docker logs
   ai-intelligent-banking-api-1 | grep '"trace_id": "INCIDENT-DEMO-1790622208"'`) returned the
   full span tree for the request, each with a real measured duration:
   `http.request` (2696.69ms) → `case.run` (3.50ms, `case_id=CASE-6CB4F4788AEF45B297B3`) →
   `llm.extract_intent` (1.12ms) → `llm.decide_next_question` (0.08ms) →
   `llm.propose_action` (0.07ms) → `llm.explain` (0.06ms) →
   `rag.retrieve` (0.94ms, `proposed_action=auto_resolve`) →
   `policy.authorize` (0.50ms, `tool_name=close_case_no_action`).
2. **`SELECT event_type, case_id, decision_id, correlation_id, created_at FROM audit_events
   WHERE correlation_id = 'INCIDENT-DEMO-1790622208'`** returned exactly the two audit events
   that request produced — `risk.assessment.completed` and `human.review.required` — both
   carrying the same `case_id`/`decision_id` the API response and the trace spans above already
   named. This is the direct fix for the gap `docs/project-status.md` § Phase 10 detail
   documented (`AuditEvent.correlation_id` was always written as `None`).

Together: **what** happened (`human.review.required` — a real `Decision` exists, pending
approval, matching the API's own `requires_human_approval=true`), **why** (the trace's
`policy.authorize` span names the exact tool, `close_case_no_action`; the Decision row's own
`analyst_explanation` carries the reasoning), and **how long** each step took (every span's
`duration_ms`) — reconstructed entirely from the log stream + one SQL query, joined by one
correlation ID, without needing the raw customer message or any PII beyond what the
Decision/Evidence rows already carry (`docs/observability.md` § 5's own constraint).

Also verified in the same session: `docker compose --profile monitoring up -d prometheus
grafana` — Prometheus's `/api/v1/targets` showed the `api` scrape target `"health": "up"` within
one scrape interval; `/api/v1/rules` showed all four `alerts.yml` rules loaded
(`"health": "ok"`, all `inactive` as expected with no incident present); Grafana auto-provisioned
the Prometheus datasource and the `fraud-investigator` dashboard
(`GET /api/search`), and a direct query through Grafana's own datasource proxy for
`business_automation_rate` returned a real value (`0.2727...`, matching the live database's
`fraud_cases` table at the time). All containers torn down afterward
(`docker compose --profile monitoring down`) to conserve memory on this development machine,
per this project's established practice.

## What this phase does not do

- No log aggregation/retention backend (ELK, Loki, CloudWatch) — trace/log data lives only in
  each container's own stdout, same as every log line before this phase. `docs/observability.md`
  § 4 keeps this `PLANNED`.
- No PII-leakage detector or ML/feature-drift monitor — no live detector exists for either
  (drift needs the Fraud ML score to actually be wired into orchestration first, a pre-existing
  gap since Phase 4, `docs/project-status.md` § Known limitations), so no alert references them
  either; fabricating one would violate `CLAUDE.md` § 7's "never fabricate ... performance
  results."
- No cost tracking (`docs/observability.md` § 6) — `MockLLMClient` makes no real provider call,
  so there is no real token/cost figure to report; a `SIMULATED` estimate was considered and
  rejected as more likely to be misread as real than to be useful.
- `GET /metrics` has no authentication — acceptable for a local-only prototype
  (`CLAUDE.md` § 7: no production deployment), a real gap for an actual deployment.
