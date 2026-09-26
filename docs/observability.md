# Observability

Owns: telemetry and operational visibility. See `docs/security-model.md` for the threats
redaction protects against, and `docs/decision-policy.md` § 9 for the decision-provenance data
this document's audit log must carry.

## 1. Categories

- **Application logs:** structured (JSON), one event per significant step, correlated by
  `case_id` / `interaction_id` / a request-correlation ID.
- **Metrics — system:** request count, latency, error rate, throughput, tool latency, LLM
  latency, database latency, queue lag (if an event system is introduced).
- **Metrics — ML:** precision, recall, FPR, FNR, calibration, drift, feature distribution
  (`docs/model-evaluation.md` owns methodology; this document owns how they're emitted).
- **Metrics — LLM:** latency, token usage, tool-call accuracy, hallucination rate,
  groundedness, refusal rate, unsafe-action rate (should always be 0; alert if not).
- **Metrics — business:** fraud detected, false positives, human escalation rate, automation
  rate, resolution time, customer friction, estimated loss (`docs/evaluation-plan.md` § 3).
- **Traces:** end-to-end span per case through the pipeline in `docs/architecture.md` § 2,
  including every LLM call and tool call as a child span.
- **Audit logs:** immutable-style record of every decision and action (§ 3 below) — distinct
  from application logs; retained per `docs/data-governance.md` § Retention.

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

## 4. Alerts and dashboards

`PLANNED`: alert on unsafe-action rate > 0, prompt-injection success > 0, PII-leakage
detection > 0, error-rate/latency SLO breach, and model/feature drift beyond a configured
bound. Dashboard composition (Grafana) is deferred to Phase 12 of
`docs/implementation-roadmap.md` — not designed yet.

## 5. Incident investigation

An incident must be reconstructable from traces + audit log + (redacted) application logs
without needing raw PII — this is a design constraint on what gets logged, not an afterthought
added during an actual incident.

## 6. Cost tracking

Track estimated LLM cost per case (`prompt.md` § 40): provider/model used, token counts, and a
derived dollar estimate, emitted alongside the case's other metrics so `docs/evaluation-plan.md`
§ 8 "operating efficiency" numbers have a real cost input rather than a guess.
