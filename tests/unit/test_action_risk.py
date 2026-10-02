"""Tests for src/policies/action_risk.py — the fixed action-risk
classification table (docs/decision-policy.md § 6). Fully offline."""

from src.policies.action_risk import classify_action_risk, max_risk
from src.policies.config import PolicyConfig

_CONFIG = PolicyConfig(large_amount_threshold_usd=10_000.0)


def test_known_tools_classify_at_their_documented_risk_level() -> None:
    assert classify_action_risk("get_customer", config=_CONFIG) == "low"
    assert classify_action_risk("create_dispute", config=_CONFIG) == "medium"
    assert classify_action_risk("freeze_card", config=_CONFIG) == "high"


def test_unknown_tool_defaults_to_high_never_low() -> None:
    """Secure default (.claude/rules/security.md): a tool this table has
    never seen must never be assumed safe to automate."""
    assert classify_action_risk("some_new_tool_nobody_reviewed", config=_CONFIG) == "high"


def test_transfer_transaction_type_is_always_irreversible_regardless_of_amount() -> None:
    assert (
        classify_action_risk(
            "create_dispute", transaction_type="Transfer", amount_usd=1.0, config=_CONFIG
        )
        == "irreversible"
    )


def test_large_amount_escalates_a_medium_risk_tool_to_irreversible() -> None:
    assert (
        classify_action_risk("create_dispute", amount_usd=50_000.0, config=_CONFIG)
        == "irreversible"
    )


def test_small_amount_does_not_escalate() -> None:
    assert classify_action_risk("create_dispute", amount_usd=100.0, config=_CONFIG) == "medium"


def test_requested_action_override_uses_requested_amount_not_transaction_amount() -> None:
    """evaluation/golden_cases/prompt_injection.json: a customer's own
    requested action/amount, distinct from the underlying transaction's
    facts, must independently be able to trigger the override."""
    assert (
        classify_action_risk(
            "create_human_review",
            requested_action="large_refund",
            requested_amount_usd=50_000.0,
            config=_CONFIG,
        )
        == "irreversible"
    )


def test_max_risk_orders_correctly() -> None:
    assert max_risk("low", "irreversible") == "irreversible"
    assert max_risk("high", "low") == "high"
    assert max_risk("medium", "medium") == "medium"


# docs/decision-policy.md § 5's risk bands, wired in via src/ml/score.py (Phase 15).
_SCORE_CONFIG = PolicyConfig(
    large_amount_threshold_usd=10_000.0,
    high_fraud_score_threshold=0.70,
    critical_fraud_score_threshold=0.90,
)


def test_critical_fraud_score_escalates_even_a_low_risk_tool_to_irreversible() -> None:
    assert (
        classify_action_risk("get_customer", fraud_model_score=0.95, config=_SCORE_CONFIG)
        == "irreversible"
    )


def test_high_fraud_score_escalates_a_low_risk_tool_to_at_least_high() -> None:
    assert (
        classify_action_risk("get_customer", fraud_model_score=0.75, config=_SCORE_CONFIG) == "high"
    )


def test_high_fraud_score_does_not_downgrade_an_already_higher_base_risk() -> None:
    assert (
        classify_action_risk("freeze_card", fraud_model_score=0.75, config=_SCORE_CONFIG) == "high"
    )


def test_fraud_score_below_high_threshold_does_not_escalate() -> None:
    assert (
        classify_action_risk("create_dispute", fraud_model_score=0.50, config=_SCORE_CONFIG)
        == "medium"
    )


def test_none_fraud_score_behaves_exactly_as_before_this_phase() -> None:
    """Regression safety: a missing score (golden cases; a live case
    before Phase 15) must change nothing about today's behavior."""
    assert (
        classify_action_risk("create_dispute", fraud_model_score=None, config=_SCORE_CONFIG)
        == "medium"
    )


def test_fraud_score_and_amount_overrides_combine_via_max_risk() -> None:
    """Both overrides are independent and additive (never pick one over the
    other) — a large amount alone already forces irreversible; a high (not
    critical) fraud score on top of a small amount still only forces
    'high', not 'irreversible'."""
    assert (
        classify_action_risk(
            "create_dispute",
            amount_usd=50_000.0,
            fraud_model_score=0.75,
            config=_SCORE_CONFIG,
        )
        == "irreversible"
    )
    assert (
        classify_action_risk(
            "create_dispute",
            amount_usd=100.0,
            fraud_model_score=0.75,
            config=_SCORE_CONFIG,
        )
        == "high"
    )
