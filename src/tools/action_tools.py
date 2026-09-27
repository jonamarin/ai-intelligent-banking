"""Action (state-changing) tools (prompt.md § 16) — PROPOSAL ONLY.

None of these functions write to the database. Each returns a `ToolProposal`
describing what *would* happen — the authorization chain
(`src/policies/authorization.py`, Phase 7) validates it, and
`src/policies/gateway.py` (Phase 7/9) is the only thing that ever writes a
row for it, keyed by `idempotency_key` so a retried/duplicated request can't
execute twice (`docs/architecture.md` § 11, Phase 9). Calling one of these
functions is always safe — nothing here writes anything.
"""

from src.tools.base import ToolProposal


def _default_idempotency_key(case_id: str, tool_name: str) -> str:
    return f"{case_id}-{tool_name}"


def propose_create_dispute(
    case_id: str, transaction_id: str, rationale: str, idempotency_key: str | None = None
) -> ToolProposal:
    return ToolProposal(
        tool_name="create_dispute",
        arguments={"case_id": case_id, "transaction_id": transaction_id},
        rationale=rationale,
        action_risk="medium",
        requires_human_approval=False,  # policy-dependent; Phase 7 decides for real
        idempotency_key=idempotency_key or _default_idempotency_key(case_id, "create_dispute"),
    )


def propose_freeze_card(
    case_id: str, customer_id: str, rationale: str, idempotency_key: str | None = None
) -> ToolProposal:
    return ToolProposal(
        tool_name="freeze_card",
        arguments={"case_id": case_id, "customer_id": customer_id},
        rationale=rationale,
        action_risk="high",
        requires_human_approval=True,
        idempotency_key=idempotency_key or _default_idempotency_key(case_id, "freeze_card"),
    )


def propose_notify_customer(
    case_id: str, customer_id: str, message_es: str, idempotency_key: str | None = None
) -> ToolProposal:
    return ToolProposal(
        tool_name="notify_customer",
        arguments={"case_id": case_id, "customer_id": customer_id, "message_es": message_es},
        rationale="Inform the customer of the case outcome/status.",
        action_risk="medium",
        requires_human_approval=False,
        idempotency_key=idempotency_key or _default_idempotency_key(case_id, "notify_customer"),
    )


def propose_create_human_review(
    case_id: str, reason: str, idempotency_key: str | None = None
) -> ToolProposal:
    return ToolProposal(
        tool_name="create_human_review",
        arguments={"case_id": case_id, "reason": reason},
        rationale=reason,
        action_risk="low",
        requires_human_approval=False,
        idempotency_key=idempotency_key
        or _default_idempotency_key(case_id, "create_human_review"),
    )


def propose_close_case_no_action(
    case_id: str, rationale: str, idempotency_key: str | None = None
) -> ToolProposal:
    """For `auto_resolve`: no state-changing action taken on the customer's
    account or dispute — closing the case is itself Low action-risk
    (docs/decision-policy.md § 6: "explain transaction, show status"), never
    the Medium `notify_customer` classification `create_dispute`/
    `freeze_card` carry."""
    return ToolProposal(
        tool_name="close_case_no_action",
        arguments={"case_id": case_id},
        rationale=rationale,
        action_risk="low",
        requires_human_approval=False,
        idempotency_key=idempotency_key
        or _default_idempotency_key(case_id, "close_case_no_action"),
    )
