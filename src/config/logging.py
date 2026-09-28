"""Structured logging with mandatory redaction.

docs/observability.md § 2: raw payment credentials, secrets, and auth tokens must
never reach a log sink. This module enforces that at the logging-filter level —
applied before any line is emitted, not as a downstream cleanup step — so every
logger configured through `configure_logging` gets it automatically.

Masking itself lives in `src/security/redaction.py` (Phase 8) — the single
shared implementation, also used for `AuditEvent.payload` construction
(`src/evidence/persist.py`, `src/policies/gateway.py`) so redaction is a
structural guarantee at every write path, not just this log-line filter. It
is a backstop, not a complete DLP solution — do not log raw sensitive fields
in application code relying on this filter to save you; redact at the source
when possible.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from src.security.redaction import mask_card_like


class RedactionFilter(logging.Filter):
    """Masks card/account-like digit runs in the formatted log message."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_card_like(str(record.getMessage()))
        record.args = ()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        # A structured event (e.g. src/monitoring/tracing.py's `event_data`
        # for a `trace.span` line) gets merged in, overriding the generic
        # `message` placeholder with its own real fields -- one JSON schema
        # for both free-text logging and structured trace/event emission,
        # rather than a second logger/formatter for the latter.
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(event_data)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with JSON output and mandatory redaction.

    Idempotent — safe to call more than once (e.g. once in the app factory, once
    in a test fixture) without duplicating handlers.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
