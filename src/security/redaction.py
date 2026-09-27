"""The shared PII/secret redaction layer (`docs/observability.md` § 2,
`docs/security-model.md` § 7): "redaction happens before the write, not as a
downstream filter." Every place that constructs an `AuditEvent.payload`, a
log line, or anything else that could carry a raw card/account number must
route through this module — not re-implement its own masking.

This is a **backstop, not a complete DLP solution** (same caveat as before
this module existed) — redact at the source when a field is known sensitive;
this catches what source-level redaction misses, it doesn't replace it.
"""

import re
from typing import Any

# 12-19 consecutive digits (optionally separated by spaces/dashes every 4),
# the shape of a card/account number.
_CARD_LIKE_RE = re.compile(r"\b(?:\d[ -]?){11,18}\d\b")


def mask_card_like(text: str) -> str:
    """`4111111111111111` -> `****1111` — matches `docs/observability.md`
    § 2's example exactly: a fixed 4-character mask, not a length-preserving
    one, so the masked value never reveals the original digit count either."""

    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", match.group(0))
        return "****" + digits[-4:]

    return _CARD_LIKE_RE.sub(_mask, text)


def redact_value(value: Any) -> Any:
    """Recursively applies `mask_card_like` to every string found in `value`
    — dicts, lists, and tuples are walked; every other type (int, float,
    bool, None, datetime, ...) is returned unchanged. Use this on any
    payload heading to an `AuditEvent`, a log line, or LLM context."""
    if isinstance(value, str):
        return mask_card_like(value)
    if isinstance(value, dict):
        return {key: redact_value(v) for key, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value
