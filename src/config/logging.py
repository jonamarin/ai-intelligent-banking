"""Structured logging with mandatory redaction.

docs/observability.md § 2: raw payment credentials, secrets, and auth tokens must
never reach a log sink. This module enforces that at the logging-filter level —
applied before any line is emitted, not as a downstream cleanup step — so every
logger configured through `configure_logging` gets it automatically.

This redacts obvious card/account-number-shaped digit runs. It is a backstop, not
a complete DLP solution — do not log raw sensitive fields in application code
relying on this filter to save you; redact at the source when possible.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# 12-19 consecutive digits (optionally separated by spaces/dashes every 4), the
# shape of a card/account number — mask all but the last 4 digits.
_CARD_LIKE_RE = re.compile(r"\b(?:\d[ -]?){11,18}\d\b")


def _mask_card_like(text: str) -> str:
    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", match.group(0))
        return "*" * (len(digits) - 4) + digits[-4:]

    return _CARD_LIKE_RE.sub(_mask, text)


class RedactionFilter(logging.Filter):
    """Masks card/account-like digit runs in the formatted log message."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _mask_card_like(str(record.getMessage()))
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
