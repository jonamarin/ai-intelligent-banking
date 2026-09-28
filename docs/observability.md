# Observability

Owns: telemetry and operational visibility. See `docs/security-model.md` for the threats
redaction protects against, `docs/decision-policy.md` § 9 for the decision-provenance data this
document's audit log must carry, and `src/monitoring/README.md` for the runnable, verified
implementation (Phase 13, `docs/project-status.md` § Phase 13 detail) — this document stays the
design spec; that one is the "what's actually wired, with real numbers" record.

## 1. Categories

- **Application logs:** structured (JSON), one event per significant step, correlated by
  `case_id` / `interaction_id` / a request-correlation ID. `IMPLEMENTED` (Phase 1,
  `src/config/logging.py`).
- **Metrics — system:** request count, latency, error rate, throughput, tool latency, LLM
  latency, database latency, queue lag (if an event system is introduced). `IMPLEMENTED` (Phase
  13, `src/monitoring/metrics.py`) except queue lag — no event/message system exists in this
  project (`CLAUDE.md` § 5: introduced only if a phase actually needs one).
- **Metrics — ML:** precision, recall, FPR, FNR, calibration, drift, feature distribution
  (`docs/model-evaluation.md` owns methodology; this document owns how they're emitted).
  Precision/recall/FPR/FNR/calibration are `IMPLEMENTED` as one-off evaluation output (Phase 4,
  `src/ml/evaluate.py`; Phase 11, `evaluation/report.py`), not as a live, continuously-scraped
  metric — the Fraud ML model isn't wired into live orchestration at all (a pre-existing gap
  since Phase 4, `docs/project-status.md` § Known limitations), so there is no live score to
  emit a metric from. Drift/feature-distribution monitoring stays `PLANNED` for the same reason.
- **Metrics — LLM:** latency, token usage, tool-call accuracy, hallucination rate,
  groundedness, refusal rate, unsafe-action rate (should always be 0; alert if not). Latency and
  unsafe-action rate are `IMPLEMENTED` live (Phase 13: `llm_call_duration_seconds`,
  `unsafe_actions_total`, `injection_attempts_detected_total`). Groundedness is `IMPLEMENTED` as
  a one-off evaluation metric (Phase 11, `evaluation/report.py`'s `groundedness_rate`), not a
  live counter. Token usage/cost, tool-call accuracy, and hallucination rate stay `PLANNED` — see
  § 6 for why token usage specifically isn't fabricated.
- **Metrics — business:** fraud detected, false positives, human escalation rate, automation
  rate, resolution time, customer friction, estimated loss (`docs/evaluation-plan.md` § 3).
  Automation rate and human-escalation rate are `IMPLEMENTED` live, computed fresh from the
  database on every scrape (Phase 13, `BusinessMetricsCollector`). Estimated loss stays honestly
  `"not available"` everywhere it's reported (`docs/evaluation-plan.md` § 3: no
  business-approved cost coefficients exist) — never fabricated as a metric either. Resolution
  time and customer friction stay `PLANNED`.
- **Traces:** end-to-end span per case through the pipeline in `docs/architecture.md` § 2,
  including every LLM call and tool call as a child span. `IMPLEMENTED` (Phase 13,
  `src/monitoring/tracing.py`) — a small custom span recorder, not the OpenTelemetry SDK
  originally listed in `CLAUDE.md` § 5's stack; see
  `docs/decisions/ADR-0001-tracing-without-opentelemetry.md` for why.
- **Audit logs:** immutable-style record of every decision and action (§ 3 below) — distinct
  from application logs; retained per `docs/data-governance.md` § Retention. `IMPLEMENTED`
  (Phase 2/7/9); Phase 13 fixed the last documented gap in it (§ 3 below).

## 2. Redaction rules (never logged, anywhere)

Raw payment credentials (full card numbers), other secrets, authentication tokens/passwords,
unnecessary PII, and full sensitive customer context in any log, trace, or LLM prompt/response
capture. Card/account numbers that must appear for debugging are masked
(`4111111111111111` → `****1111`) before they reach any log sink. This is enforced by a
redaction layer applied before the write, not a downstream filter (`docs/security-model.md`
§ 7).

## 3. Audit log shape

```json
{
  "event": "decision.created",
  "case_id": "...",
  "decision": "human_review",
  "model_version": "...",
  "policy_version": "...",
  "evidence_ids": ["..."],
  "timestamp": "..."
}
```

(`prompt.md` § 55.) Every Decision, Human Review, and executed Action produces an audit event
carrying enough of `docs/decision-policy.md` § 9's provenance chain to answer, after the fact,
what happened and why — without needing to log the raw customer message or PII alongside it.
**`correlation_id` is now always populated** (Phase 13) — `src/policies/gateway.py` previously
wrote it as `None` unconditionally (an honestly-documented Phase 10 gap,
`docs/project-status.md` § Phase 10 detail); it now reads the live trace ID
(`src/monitoring/tracing.current_trace_id()`), verified live end-to-end in
`src/monitoring/README.md` § Incident reconstruction.

## 4. Alerts and dashboards

`IMPLEMENTED` (Phase 13) for every metric this project actually emits: `UnsafeActionDetected`
(`unsafe_actions_total`), `ElevatedHttpErrorRate`, `ElevatedLlmDegradedRate`,
`HighRequestLatencyP99` — `infrastructure/prometheus/alerts.yml`, verified loaded and evaluating
in a live Prometheus (`src/monitoring/README.md`). Prompt-injection *success* has no separate
alert — a successful injection that reached an unsafe action is exactly what
`UnsafeActionDetected` already fires on (`src/orchestration/flow.py`'s definition matches
`tests/security/test_red_team.py`'s offline proof). PII-leakage detection and model/feature
drift stay `PLANNED`: no live detector or ML-score wiring exists to alert on
(`docs/project-status.md` § Known limitations) — fabricating an alert for a metric that doesn't
exist would violate `CLAUDE.md` § 7. Dashboard composition (Grafana) is `IMPLEMENTED`:
`infrastructure/grafana/dashboards/fraud-investigator.json`, 10 panels, auto-provisioned and
verified rendering real data through a live Prometheus datasource
(`src/monitoring/README.md`) — both behind docker-compose's optional `monitoring` profile
(`make monitoring-up`/`make monitoring-down`), never started by a plain `docker compose up`.

## 5. Incident investigation

An incident must be reconstructable from traces + audit log + (redacted) application logs
without needing raw PII — this is a design constraint on what gets logged, not an afterthought
added during an actual incident. `IMPLEMENTED` and verified live end-to-end (Phase 13,
`src/monitoring/README.md` § Incident reconstruction): a real case created through the API,
reconstructed from its trace spans (grep by `trace_id` in the log stream) plus one
`audit_events` query by the same `correlation_id`, with no raw PII needed.

## 6. Cost tracking

Track estimated LLM cost per case (`prompt.md` § 40): provider/model used, token counts, and a
derived dollar estimate, emitted alongside the case's other metrics so `docs/evaluation-plan.md`
§ 8 "operating efficiency" numbers have a real cost input rather than a guess. Still `PLANNED`:
`MockLLMClient` (the only `LLMClient` this project runs, `CLAUDE.md` § 5) makes no real provider
call, so there is no real token count or dollar figure to report — a fabricated `SIMULATED`
estimate was considered for Phase 13 and rejected as more likely to be misread as a real cost
figure than to be useful (`CLAUDE.md` § 7: "never fabricate ... performance results").
