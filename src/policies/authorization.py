"""The deterministic tool-authorization chain — the Action Gateway's decision
logic (`docs/guardrails.md` § 3, `docs/architecture.md` § 6):

    authenticated? -> case eligible? -> sufficient evidence?
    -> classify action-risk -> does policy allow automation at this level?
    -> is human approval required? -> authorized (to execute or to queue)

Every "no" stops here with an auditable reason (`denied_step`,
`reason`) — never a silent failure or a retry loop (`docs/guardrails.md` § 3).
This is the highest-scrutiny code in the project
(`docs/implementation-roadmap.md` Phase 7): a bug here means an unauthorized
financial action, not just a wrong answer.

**`ActionProposal`/`ToolProposal.requires_human_approval` is a recommendation,
never authorization** (`docs/decision-policy.md` § 2). This module never lets
that recommendation *downgrade* what policy independently requires — it can
only ever push `requires_human_approval` from False to True, never the
reverse. `action_risk == "irreversible"` always forces human approval; that
branch reads no config value, so no environment variable can weaken it
(`docs/demo-script.md` Scenario D).
"""

import dataclasses
from typing import Literal

from src.policies.action_risk import ActionRisk, classify_action_risk
from src.policies.config import PolicyConfig
from src.tools.base import ToolProposal

DenialStep = Literal["not_authenticated", "case_not_eligible", "insufficient_evidence"]

# Case statuses that no longer accept a new action (docs/demo-script.md
# Scenario L — "a second dispute on an already-resolved transaction").
# `create_human_review` is exempt: a human can always be asked to look at a
# case regardless of its current status.
_INELIGIBLE_CASE_STATUSES = {"resolved", "closed", "rejected"}
_ALWAYS_ELIGIBLE_TOOLS = {"create_human_review"}


@dataclasses.dataclass
class AuthorizationResult:
    authorized: bool  # False = hard denial; nothing may proceed, not even queued
    # True (with authorized=True) = queued for a human, not yet executable.
    requires_human_approval: bool
    action_risk: ActionRisk
    policy_version: str
    reason: str
    denied_step: DenialStep | None
    audit_event_types: list[str]


def authorize(
    proposal: ToolProposal,
    *,
    case_status: str = "open",
    is_authenticated: bool = True,
    escalation_required: bool = False,
    transaction_type: str | None = None,
    requested_action: str | None = None,
    amount_usd: float | None = None,
    requested_amount_usd: float | None = None,
    config: PolicyConfig | None = None,
) -> AuthorizationResult:
    config = config or PolicyConfig()
    action_risk = classify_action_risk(
        proposal.tool_name,
        transaction_type=transaction_type,
        requested_action=requested_action,
        amount_usd=amount_usd,
        requested_amount_usd=requested_amount_usd,
        config=config,
    )

    # Step 1: authenticated? No real session/auth layer exists yet
    # (Phase 8) — `is_authenticated` defaults True so every current caller
    # passes, but the check is real code exercised by a deny-path test
    # (tests/unit/test_authorization.py), not a stub waiting for Phase 8.
    if not is_authenticated:
        return AuthorizationResult(
            authorized=False,
            requires_human_approval=True,
            action_risk=action_risk,
            policy_version=config.policy_version,
            reason="Session is not authenticated — no tool executes for an unauthenticated case.",
            denied_step="not_authenticated",
            audit_event_types=["risk.assessment.completed", "action.rejected"],
        )

    # Step 2: is the case eligible for a new action (docs/demo-script.md
    # Scenario L)?
    case_ineligible = case_status in _INELIGIBLE_CASE_STATUSES
    if case_ineligible and proposal.tool_name not in _ALWAYS_ELIGIBLE_TOOLS:
        return AuthorizationResult(
            authorized=False,
            requires_human_approval=False,
            action_risk=action_risk,
            policy_version=config.policy_version,
            reason=(
                f"Case status '{case_status}' does not accept a new '{proposal.tool_name}' "
                "action (docs/demo-script.md Scenario L)."
            ),
            denied_step="case_not_eligible",
            audit_event_types=["risk.assessment.completed", "action.rejected"],
        )

    # Step 3: sufficient evidence? Defense-in-depth: flow.py (Phase 6) already
    # routes a contradiction-flagged case to the `escalate` action upstream,
    # but this gateway re-checks independently rather than trusting that the
    # caller always did (docs/decision-policy.md § 4 — insufficient/
    # conflicting evidence must never reach a forced automatic decision).
    if escalation_required and proposal.tool_name not in _ALWAYS_ELIGIBLE_TOOLS:
        return AuthorizationResult(
            authorized=False,
            requires_human_approval=True,
            action_risk=action_risk,
            policy_version=config.policy_version,
            reason=(
                "Evidence graph has an unresolved contradiction — only escalation to a human "
                "may proceed, never an automated action (docs/decision-policy.md § 4)."
            ),
            denied_step="insufficient_evidence",
            audit_event_types=["risk.assessment.completed", "human.review.required"],
        )

    automation_allowed = {
        "low": config.automate_low_risk,
        "medium": config.automate_medium_risk,
        "high": config.automate_high_risk,
        "irreversible": False,  # never configurable — docs/demo-script.md Scenario D
    }[action_risk]

    requires_human_approval = (
        not automation_allowed or action_risk == "irreversible" or proposal.requires_human_approval
    )

    audit_event_types = ["risk.assessment.completed"]
    audit_event_types.append(
        "human.review.required" if requires_human_approval else "action.approved"
    )
    if not requires_human_approval:
        audit_event_types.append("action.executed")

    return AuthorizationResult(
        authorized=True,
        requires_human_approval=requires_human_approval,
        action_risk=action_risk,
        policy_version=config.policy_version,
        reason=(
            f"action_risk={action_risk}, automation_allowed={automation_allowed}, "
            f"proposal.requires_human_approval={proposal.requires_human_approval}"
        ),
        denied_step=None,
        audit_event_types=audit_event_types,
    )
