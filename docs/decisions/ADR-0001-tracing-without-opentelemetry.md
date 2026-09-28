# ADR-0001: Trace with a custom span recorder, not the OpenTelemetry SDK

## Status
Accepted

## Context
`CLAUDE.md` § 5's confirmed technology stack lists "Observability: OpenTelemetry, Prometheus,
Grafana" for this project, decided during repository initialization before any observability
code existed. Phase 13 (`docs/implementation-roadmap.md`) is the phase that actually implements
`docs/observability.md`, including its § 1 "Traces: end-to-end span per case through the
pipeline ... including every LLM call and tool call as a child span" requirement.

This project is a ten-day/hackathon-scale prototype (`docs/product-requirements.md` § 10) on a
memory-constrained development machine (`docs/project-status.md` § Known limitations — background
ingestion runs were killed by out-of-memory conditions multiple times across Phases 4–5), with no
staging or production environment (`.claude/rules/infrastructure.md`). There is no trace
backend (Jaeger, Tempo, an OTLP collector) anywhere in this project's scope, and standing this one
up is not something a real judge/reviewer of this submission would be able to use anyway without
running extra infrastructure alongside `docker compose up`.

## Problem
How should Phase 13 implement distributed tracing: adopt the OpenTelemetry SDK as originally
listed, or a smaller custom mechanism?

## Decision
Trace with a small, dependency-free custom span recorder (`src/monitoring/tracing.py`) that
emits each span as one structured JSON log line (`event: "trace.span"`) through the same
redacted logger every other application log line already uses
(`src/config/logging.py`) — correlated by `trace_id` (seeded from the request's own
`X-Correlation-ID`, `src/api/main.py`) and `case_id`. No OpenTelemetry SDK dependency was added.

## Alternatives considered
- **Full OpenTelemetry SDK + an OTLP exporter to a real collector (Jaeger/Tempo).** Rejected:
  requires standing up and documenting an entirely new service this project has no other use
  for, on a machine already documented as memory-constrained — real operational weight for a
  capability (a trace *viewer* UI) nothing in this project's own demo/evaluation flow
  (`docs/demo-script.md`, `demo/README.md`) currently needs, since the incident-reconstruction
  exit criterion (docs/observability.md § 5) only requires that trace data be
  *correlatable with the audit log*, not that it render in a dedicated trace UI.
- **OpenTelemetry SDK with a `ConsoleSpanExporter` or an in-memory exporter, no real backend.**
  Considered seriously — it would satisfy "use the named library" literally. Rejected because it
  adds a real dependency and a second logging/formatting pipeline (OTel's own span data model)
  running alongside this project's existing, working structured-JSON logger
  (`src/config/logging.py`, `RedactionFilter`) for no functional benefit over emitting the same
  span data through that existing pipeline directly — two ways to do the same thing is exactly
  the kind of unnecessary abstraction `CLAUDE.md`'s engineering conventions ask this project to
  avoid.
- **No tracing at all, only metrics + audit events.** Rejected: `docs/observability.md` § 1
  explicitly requires traces, and `docs/implementation-roadmap.md` Phase 13's exit criterion
  ("an incident can be reconstructed from traces + audit log alone") specifically depends on
  span data existing, not just Decision/AuditEvent rows.

## Consequences
**Easier:** one dependency-free module, no new service to run or document, spans reuse the
existing redaction guarantee (`src/security/redaction.py`) automatically rather than needing a
second, OTel-specific redaction/processor configuration. Spans are trivially readable in the
same log stream operators already watch. **Harder:** no trace-ID-indexed UI to click through a
waterfall view — reconstructing a trace means grep/jq-filtering the JSON log stream by
`trace_id`, which is real, working, but less pleasant than a dedicated viewer. If this project
ever needed a real multi-service distributed trace (multiple independent processes/services
correlating one request), this custom recorder would need real propagation-header support
(e.g. W3C Trace Context) it does not currently implement — `contextvars`-based propagation only
works within one process's call graph today.

## Security implications
None beyond what already applies to every other log line: span attributes are redacted via
`src/security/redaction.py` before they reach the log sink
(`tests/unit/test_tracing.py::test_span_attributes_are_redacted_before_they_reach_the_log`),
matching `docs/observability.md` § 2's existing rule. No new trust boundary is introduced.

## Operational implications
Trace data lives in the same stdout JSON log stream as everything else — no separate service to
deploy, monitor, or keep available. The known cost: nothing currently *indexes* or *retains*
this stream beyond whatever wraps `docker compose`'s own log output (`docker compose logs`) in
local development; a real deployment would still need a log-aggregation backend for either
approach (OTel-shipped spans or these JSON lines) to be queryable at scale — this ADR doesn't
change that follow-on requirement, documented as `PLANNED` in `docs/observability.md` § 4.

## Reversibility
Fully reversible. `tracing.span(name, **attributes)`'s call sites (`src/orchestration/flow.py`,
`src/api/main.py`, `src/policies/gateway.py`'s use of `tracing.current_trace_id()`) are a small,
enumerable set; swapping the recorder for a real OpenTelemetry `Tracer` later would mean
reimplementing `src/monitoring/tracing.py`'s internals behind the same `span()`/
`current_trace_id()`/`seed_trace_id()` call shape, not touching every call site. Cost to undo:
small — one module plus its call sites, versus standing up and learning a new backend service.

## Open questions
None blocking. If this project ever needs cross-process trace correlation (e.g., a real async
worker/queue consuming case-processing jobs), revisit this ADR then — `contextvars` propagation
stops being sufficient at that point.
