"""Idempotency-key derivation (`docs/architecture.md` § 11,
`docs/demo-script.md` Scenario J) — offline, no DB.

The actual DB-level duplicate-detection round trip (`INSERT ... ON CONFLICT
DO NOTHING RETURNING`, the deferred FK on `action_executions.decision_id`)
is DB-only code, like `src/evidence/persist.py` before it — verified live
against the real database, not mocked here (`src/policies/README.md`).
What's tested offline is everything upstream of that: the key each tool
proposal carries, and that it survives into `AuthorizationResult` unchanged.
"""

from src.policies.authorization import authorize
from src.policies.config import PolicyConfig
from src.tools.action_tools import (
    propose_close_case_no_action,
    propose_create_dispute,
    propose_create_human_review,
    propose_freeze_card,
    propose_notify_customer,
)

_CONFIG = PolicyConfig(large_amount_threshold_usd=10_000.0)


def test_default_idempotency_key_is_derived_from_case_id_and_tool_name() -> None:
    assert propose_freeze_card("CASE-1", "CUST-1", "r").idempotency_key == "CASE-1-freeze_card"
    assert (
        propose_create_dispute("CASE-1", "TXN-1", "r").idempotency_key
        == "CASE-1-create_dispute"
    )
    assert (
        propose_create_human_review("CASE-1", "r").idempotency_key
        == "CASE-1-create_human_review"
    )
    assert (
        propose_close_case_no_action("CASE-1", "r").idempotency_key
        == "CASE-1-close_case_no_action"
    )
    assert (
        propose_notify_customer("CASE-1", "CUST-1", "msg").idempotency_key
        == "CASE-1-notify_customer"
    )


def test_explicit_idempotency_key_overrides_the_default() -> None:
    proposal = propose_freeze_card("CASE-1", "CUST-1", "r", idempotency_key="client-supplied-key")
    assert proposal.idempotency_key == "client-supplied-key"


def test_two_calls_for_the_same_case_and_tool_produce_the_same_default_key() -> None:
    """The property idempotency actually depends on: calling the same
    propose_* function twice for the same case must yield the same key, so
    the DB-level ON CONFLICT can recognize it as a duplicate."""
    first = propose_freeze_card("CASE-1", "CUST-1", "r")
    second = propose_freeze_card("CASE-1", "CUST-1", "r")
    assert first.idempotency_key == second.idempotency_key


def test_different_cases_never_collide_on_the_same_default_key() -> None:
    first = propose_freeze_card("CASE-1", "CUST-1", "r")
    second = propose_freeze_card("CASE-2", "CUST-1", "r")
    assert first.idempotency_key != second.idempotency_key


def test_authorization_result_carries_the_idempotency_key_and_tool_name_through() -> None:
    proposal = propose_freeze_card("CASE-1", "CUST-1", "r")
    result = authorize(proposal, config=_CONFIG)
    assert result.idempotency_key == "CASE-1-freeze_card"
    assert result.tool_name == "freeze_card"


def test_denied_authorization_still_carries_the_idempotency_key() -> None:
    """Even a hard-denied proposal (e.g. case not eligible) must still
    report its idempotency key/tool name — a caller comparing two denial
    results for the same retried request needs this too."""
    proposal = propose_create_dispute("CASE-1", "TXN-1", "r")
    result = authorize(proposal, case_status="resolved", config=_CONFIG)
    assert result.authorized is False
    assert result.idempotency_key == "CASE-1-create_dispute"
    assert result.tool_name == "create_dispute"
