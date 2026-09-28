"""Lightweight, dependency-free distributed tracing.

`ADR-0001` (`docs/decisions/ADR-0001-tracing-without-opentelemetry.md`):
this project traces with a small custom span recorder instead of the
OpenTelemetry SDK originally listed in `CLAUDE.md` § 5's confirmed stack --
see that ADR for the full rationale (no external collector exists or is in
scope for a hackathon-scale prototype, and OTel's own value is mostly in
that collector/backend integration).

Spans are emitted as structured JSON log lines (`event: "trace.span"`)
through the same redacted logger every other application log line uses
(`src/config/logging.py`) -- correlated by `trace_id` (seeded from the
request's own `X-Correlation-ID`, `src/api/main.py`) and `case_id` when
one exists, so an incident can be reconstructed from the log stream +
`audit_events` table alone (`docs/observability.md` § 5), without a
separate trace backend to stand up.

    with tracing.span("case.run", case_id=case.case_id):
        with tracing.span("llm.extract_intent"):
            ...

Nesting is tracked via a `contextvars.ContextVar`, so it's correct across
`async`/sync boundaries within one request, but -- like any `contextvars`
state -- does not cross a thread/process boundary on its own.
"""

import contextvars
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from src.security.redaction import redact_value

logger = logging.getLogger("trace")

_current_span: contextvars.ContextVar["Span | None"] = contextvars.ContextVar(
    "_current_span", default=None
)
_current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_trace_id", default=None
)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start: float
    attributes: dict[str, Any] = field(default_factory=dict)


def current_trace_id() -> str | None:
    return _current_trace_id.get()


def seed_trace_id(trace_id: str) -> None:
    """Seed the trace ID for the current context from an external
    correlation ID (`src/api/main.py`'s request middleware; a CLI script's
    own generated ID) so a trace and its audit events share one identifier
    end to end -- the same fix this phase applies to
    `src/policies/gateway.py`'s previously-always-`None` `correlation_id`
    column."""
    _current_trace_id.set(trace_id)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Start a child span of whatever span is active in this context (or a
    new trace root if none is, and no trace ID was seeded). Emits one
    `trace.span` log line on exit with `duration_ms` and redacted
    attributes -- real span data, correlatable, no external collector
    (ADR-0001)."""
    parent = _current_span.get()
    trace_id = _current_trace_id.get() or (parent.trace_id if parent else str(uuid.uuid4()))
    current = Span(
        name=name,
        trace_id=trace_id,
        span_id=str(uuid.uuid4()),
        parent_span_id=parent.span_id if parent else None,
        start=time.perf_counter(),
        attributes=dict(attributes),
    )
    span_token = _current_span.set(current)
    trace_token = _current_trace_id.set(trace_id)
    status = "ok"
    try:
        yield current
    except Exception:
        status = "error"
        raise
    finally:
        duration_ms = (time.perf_counter() - current.start) * 1000
        logger.info(
            "span",
            extra={
                "event_data": {
                    "event": "trace.span",
                    "trace_id": current.trace_id,
                    "span_id": current.span_id,
                    "parent_span_id": current.parent_span_id,
                    "name": current.name,
                    "status": status,
                    "duration_ms": round(duration_ms, 3),
                    "attributes": redact_value(current.attributes),
                }
            },
        )
        _current_span.reset(span_token)
        _current_trace_id.reset(trace_token)
