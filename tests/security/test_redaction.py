"""Tests for src/security/redaction.py (Phase 8) — the shared PII/secret
redaction layer used by both the logging filter (src/config/logging.py) and
every AuditEvent.payload construction (src/evidence/persist.py,
src/policies/gateway.py). Offline, no DB.

Formerly tests/unit/test_logging_redaction.py — moved here and extended
when the mask format was fixed to match docs/observability.md § 2's example
exactly (`4111111111111111` -> `****1111`, not a length-preserving mask).
"""

import logging

from src.config.logging import RedactionFilter
from src.security.redaction import mask_card_like, redact_value


def test_masks_card_like_number() -> None:
    assert mask_card_like("Card 4111111111111111 was used") == "Card ****1111 was used"


def test_masks_card_like_number_with_dashes() -> None:
    assert mask_card_like("4111-1111-1111-1111") == "****1111"


def test_mask_matches_documented_example_exactly() -> None:
    """docs/observability.md § 2's own worked example."""
    assert mask_card_like("4111111111111111") == "****1111"


def test_leaves_normal_text_and_short_numbers_alone() -> None:
    assert mask_card_like("case CASE-SYN-0008, amount 850") == "case CASE-SYN-0008, amount 850"


def test_filter_redacts_log_record_message() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="card 4111111111111111 charged",
        args=(),
        exc_info=None,
    )
    RedactionFilter().filter(record)
    assert "4111111111111111" not in record.msg
    assert record.msg.endswith("1111 charged")


def test_redact_value_masks_strings_inside_a_nested_payload() -> None:
    """The shape an AuditEvent.payload actually has (src/policies/gateway.py's
    _decision_payload) — a dict of mixed types, some nested."""
    payload = {
        "customer_id": "CUST-1",
        "note": "card 4111111111111111 on file",
        "nested": {"card": "4111 1111 1111 1111"},
        "list_field": ["ok", "4111111111111111"],
        "amount": 850.0,
        "is_fraud": False,
        "missing": None,
    }
    redacted = redact_value(payload)
    assert redacted["note"] == "card ****1111 on file"
    assert redacted["nested"]["card"] == "****1111"
    assert redacted["list_field"] == ["ok", "****1111"]
    # Non-string values pass through untouched.
    assert redacted["amount"] == 850.0
    assert redacted["is_fraud"] is False
    assert redacted["missing"] is None
    assert redacted["customer_id"] == "CUST-1"


def test_redact_value_leaves_non_string_scalars_and_short_ids_alone() -> None:
    assert redact_value(42) == 42
    assert redact_value(3.14) == 3.14
    assert redact_value(None) is None
    assert redact_value("CASE-SYN-0008") == "CASE-SYN-0008"
