"""Tests for src/policies/authorization.py — the tool-authorization chain
(docs/guardrails.md § 3). Fully offline. Each guardrail-relevant branch gets
both an allow path and a deny path, per docs/implementation-roadmap.md
Phase 7's stated test requirement.
"""

from src.policies.authorization import authorize
from src.policies.config import PolicyConfig
from src.tools.base import ToolProposal

_CONFIG = PolicyConfig(large_amount_threshold_usd=10_000.0)


def _proposal(
    tool_name: str = "create_dispute", requires_human_approval: bool = False
) -> ToolProposal:
    return ToolProposal(
        tool_name=tool_name,
        arguments={},
        rationale="test",
        action_risk="medium",
        requires_human_approval=requires_human_approval,
    )


def test_low_risk_action_auto_executes_when_authenticated_and_eligible() -> None:
    result = authorize(_proposal("get_customer"), config=_CONFIG)
    assert result.authorized is True
    assert result.requires_human_approval is False
    assert "action.executed" in result.audit_event_types


def test_unauthenticated_session_is_denied_outright() -> None:
    result = authorize(_proposal(), is_authenticated=False, config=_CONFIG)
    assert result.authorized is False
    assert result.denied_step == "not_authenticated"
    assert "action.executed" not in result.audit_event_types


def test_resolved_case_rejects_a_new_action() -> None:
    """docs/demo-script.md Scenario L — policy rejection."""
    result = authorize(_proposal("create_dispute"), case_status="resolved", config=_CONFIG)
    assert result.authorized is False
    assert result.denied_step == "case_not_eligible"


def test_resolved_case_still_allows_creating_a_human_review() -> None:
    """A human can always be asked to look at a case, regardless of status."""
    result = authorize(_proposal("create_human_review"), case_status="resolved", config=_CONFIG)
    assert result.authorized is True


def test_open_case_allows_a_new_action() -> None:
    result = authorize(_proposal("create_dispute"), case_status="open", config=_CONFIG)
    assert result.authorized is True


def test_unresolved_contradiction_blocks_every_tool_except_escalation() -> None:
    """docs/decision-policy.md § 4 — insufficient/conflicting evidence must
    never reach a forced automatic decision, defense-in-depth even if the
    caller forgot to route to `escalate` upstream."""
    result = authorize(_proposal("freeze_card"), escalation_required=True, config=_CONFIG)
    assert result.authorized is False
    assert result.denied_step == "insufficient_evidence"
    assert "human.review.required" in result.audit_event_types


def test_unresolved_contradiction_does_not_block_escalation_itself() -> None:
    result = authorize(_proposal("create_human_review"), escalation_required=True, config=_CONFIG)
    assert result.authorized is True


def test_high_risk_tool_requires_human_approval_by_default() -> None:
    result = authorize(_proposal("freeze_card"), config=_CONFIG)
    assert result.authorized is True
    assert result.requires_human_approval is True
    assert "human.review.required" in result.audit_event_types


def test_medium_risk_tool_can_auto_execute_under_default_policy() -> None:
    result = authorize(_proposal("create_dispute"), config=_CONFIG)
    assert result.authorized is True
    assert result.requires_human_approval is False


def test_irreversible_action_requires_human_approval_even_if_config_would_automate_high_risk() -> (
    None
):
    """docs/demo-script.md Scenario D exit criteria: this must hold
    regardless of policy configuration — irreversible has no `automate_*`
    config field to flip (see config.py's docstring)."""
    permissive_config = PolicyConfig(
        large_amount_threshold_usd=10_000.0,
        automate_low_risk=True,
        automate_medium_risk=True,
        automate_high_risk=True,
    )
    result = authorize(
        _proposal("create_dispute"),
        transaction_type="Transfer",
        amount_usd=100_000.0,
        config=permissive_config,
    )
    assert result.action_risk == "irreversible"
    assert result.requires_human_approval is True


def test_irreversible_action_requires_human_approval_even_with_manufactured_high_confidence() -> (
    None
):
    """docs/demo-script.md Scenario D: a manufactured high-confidence
    recommendation that itself claims no human approval is needed must not
    be able to bypass the gate — this is the test that tries to defeat the
    guarantee and fails, per the Phase 7 exit criteria."""
    manufactured_low_risk_proposal = ToolProposal(
        tool_name="create_dispute",
        arguments={},
        rationale="Manufactured high-confidence 'legitimate' recommendation.",
        action_risk="low",
        requires_human_approval=False,  # the (fake) AI recommendation says no human needed
    )
    result = authorize(
        manufactured_low_risk_proposal,
        transaction_type="Transfer",
        amount_usd=100_000.0,
        config=_CONFIG,
    )
    assert result.requires_human_approval is True
    assert result.action_risk == "irreversible"


def test_proposal_requires_human_approval_can_only_upgrade_never_downgrade() -> None:
    """docs/decision-policy.md § 2: AI recommendation != authorization. A
    proposal claiming requires_human_approval=True must never be silently
    downgraded to False by policy."""
    result = authorize(_proposal("get_customer", requires_human_approval=True), config=_CONFIG)
    assert result.requires_human_approval is True


def test_critical_fraud_score_requires_approval_even_if_config_would_automate_everything() -> None:
    """docs/decision-policy.md § 5's CRITICAL risk band, finally wired to a
    real score (src/ml/score.py, Phase 15) — same guarantee shape as the
    amount-based Scenario D test above: no policy config can automate past
    it."""
    permissive_config = PolicyConfig(
        large_amount_threshold_usd=10_000.0,
        automate_low_risk=True,
        automate_medium_risk=True,
        automate_high_risk=True,
    )
    result = authorize(
        _proposal("create_dispute"),
        fraud_model_score=0.95,
        config=permissive_config,
    )
    assert result.action_risk == "irreversible"
    assert result.requires_human_approval is True


def test_low_fraud_score_does_not_escalate_a_medium_risk_tool() -> None:
    result = authorize(_proposal("create_dispute"), fraud_model_score=0.10, config=_CONFIG)
    assert result.action_risk == "medium"
    assert result.requires_human_approval is False
