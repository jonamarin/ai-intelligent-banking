"""Tests for src/monitoring/tracing.py — offline, no DB, no API key.

docs/implementation-roadmap.md Phase 13's own required test: "a redaction
test proving a raw card number/secret never reaches a log sink" — extended
here to the new trace-span log line specifically (tests/security/
test_redaction.py already covers the pre-existing log/AuditEvent paths;
this file is the Phase 13-specific one for the new emission point).
"""

import logging

import pytest

from src.monitoring import tracing


@pytest.fixture(autouse=True)
def _capture_trace_logger(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="trace")


@pytest.fixture(autouse=True)
def _reset_trace_context() -> None:
    """`tracing.seed_trace_id` sets a module-level `contextvars.ContextVar`
    directly (not through the `span()` context manager's own token/reset),
    which is deliberate -- it's meant to outlive the call that set it, for
    the rest of one request/CLI invocation. In a synchronous pytest run
    (no per-test asyncio-task boundary), that same persistence would leak
    a seeded trace ID from one test into the next -- reset explicitly."""
    tracing._current_trace_id.set(None)
    tracing._current_span.set(None)


def _span_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [
        record.event_data  # type: ignore[attr-defined]
        for record in caplog.records
        if record.name == "trace" and hasattr(record, "event_data")
    ]


def test_span_emits_one_trace_span_event(caplog: pytest.LogCaptureFixture) -> None:
    with tracing.span("do_thing", foo="bar"):
        pass
    events = _span_events(caplog)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "trace.span"
    assert event["name"] == "do_thing"
    assert event["status"] == "ok"
    assert event["attributes"] == {"foo": "bar"}
    assert isinstance(event["duration_ms"], float)


def test_nested_spans_share_one_trace_id_and_record_parent_child(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with tracing.span("parent") as parent, tracing.span("child") as child:
        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id
    events = {e["name"]: e for e in _span_events(caplog)}
    assert events["child"]["parent_span_id"] == events["parent"]["span_id"]
    assert events["child"]["trace_id"] == events["parent"]["trace_id"]
    assert events["parent"]["parent_span_id"] is None


def test_span_exiting_after_an_exception_records_error_status_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError), tracing.span("failing"):
        raise ValueError("boom")
    events = _span_events(caplog)
    assert events[0]["status"] == "error"


def test_span_attributes_are_redacted_before_they_reach_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """docs/observability.md § 2: raw payment credentials must never reach
    a log sink, redaction applied before the write -- the same guarantee
    src/security/redaction.py already gives AuditEvent payloads, proven
    here for this new trace-span emission point."""
    with tracing.span("query_customer", note="card 4111111111111111 on file"):
        pass
    event = _span_events(caplog)[0]
    assert "4111111111111111" not in str(event["attributes"])
    assert event["attributes"]["note"] == "card ****1111 on file"


def test_seed_trace_id_is_reused_by_a_subsequent_span(caplog: pytest.LogCaptureFixture) -> None:
    tracing.seed_trace_id("REQUEST-TRACE-ID")
    assert tracing.current_trace_id() == "REQUEST-TRACE-ID"
    with tracing.span("handler"):
        pass
    event = _span_events(caplog)[0]
    assert event["trace_id"] == "REQUEST-TRACE-ID"


def test_two_independent_spans_get_different_trace_ids_when_none_is_seeded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with tracing.span("first"):
        pass
    with tracing.span("second"):
        pass
    events = _span_events(caplog)
    assert events[0]["trace_id"] != events[1]["trace_id"]
