"""The case orchestration state machine (docs/architecture.md § 2, § 8).

    intent extraction -> (refuse if injection) -> next-question gate
    -> action proposal -> policy grounding (RAG) -> Policy Engine authorization
    -> explanation

Every stage's output is a Pydantic-validated structured type
(src/agents/schemas.py) — never raw text threaded between stages.
`CaseResult.action` is still only a **recommendation** (docs/decision-policy.md
§ 2) — what's now real is `CaseResult.authorization`
(src/policies/authorization.py, Phase 7): the deterministic chain that
decides whether a proposed tool call may execute, requires a human, or is
denied outright, computed from the case's own facts, never from the LLM's
`reason` text or its own claimed `requires_human_approval`. Nothing here
still *executes* a tool — `src/tools/action_tools.py` functions only ever
return a `ToolProposal`; only `src/policies/gateway.py` (used by
`live_case.py`) persists a real Decision/AuditEvent row for a live case.
"""

from src.agents.llm_client import LLMClient
from src.agents.schemas import ActionProposal, IntentResult
from src.orchestration.case import CaseInput, CaseResult
from src.policies.authorization import AuthorizationResult, authorize
from src.policies.config import PolicyConfig
from src.retrieval.policy_rag import PolicyRAG
from src.tools.action_tools import (
    propose_close_case_no_action,
    propose_create_dispute,
    propose_create_human_review,
    propose_freeze_card,
)
from src.tools.base import ToolProposal

_POLICY_QUERY_BY_ACTION = {
    "create_dispute": "política de disputas de transacciones",
    "protect_account": "bloqueo de tarjeta por fraude",
    "escalate": "procedimientos de escalamiento a humano",
    "ask_question": "política de disputas de transacciones",
    "auto_resolve": "política de disputas de transacciones",
    "refuse": "autenticación instrucciones del cliente",
}


def _tool_proposal_for_action(case: CaseInput, action: ActionProposal) -> ToolProposal | None:
    # "ask_question" and "refuse" are terminal, non-state-changing outcomes —
    # no tool call exists for either, so there's nothing for the Policy
    # Engine to authorize (docs/decision-policy.md § 6's Low-risk row already
    # covers "explain/show status" without a dedicated write path).
    if action.proposed_action == "create_dispute":
        return propose_create_dispute(case.case_id, case.transaction_id or "UNKNOWN", action.reason)
    if action.proposed_action == "protect_account":
        return propose_freeze_card(case.case_id, case.customer_id, action.reason)
    if action.proposed_action == "escalate":
        return propose_create_human_review(case.case_id, action.reason)
    if action.proposed_action == "auto_resolve":
        return propose_close_case_no_action(case.case_id, action.reason)
    return None


def _authorize_action(
    case: CaseInput, action: ActionProposal, config: PolicyConfig | None = None
) -> AuthorizationResult | None:
    proposal = _tool_proposal_for_action(case, action)
    if proposal is None:
        return None
    return authorize(
        proposal,
        case_status=case.case_status,
        escalation_required=case.escalation_required,
        transaction_type=case.transaction_type,
        requested_action=case.requested_action,
        amount_usd=case.amount_usd,
        requested_amount_usd=case.requested_amount_usd,
        config=config,
    )


def _summarize_evidence(case: CaseInput) -> str:
    counts: dict[str, int] = {}
    for item in case.evidence_items:
        counts[item.direction.value] = counts.get(item.direction.value, 0) + 1
    parts = [f"{count} {direction}" for direction, count in counts.items()]
    summary = ", ".join(parts) if parts else "no evidence available"
    if case.contradictions:
        summary += f"; {len(case.contradictions)} contradiction(s) detected"
    return summary


def _refusal(
    case: CaseInput, intent: IntentResult, llm_client: LLMClient, rag: PolicyRAG | None
) -> CaseResult:
    # Detecting an injection attempt never changes what the system does —
    # the request is refused regardless of what it asked for
    # (docs/guardrails.md § 4).
    action = ActionProposal(
        proposed_action="refuse",
        reason="Customer message attempted to override system instructions or claimed "
        "unearned authority — refused regardless of content, per docs/security-model.md § 2.",
        requires_human_approval=False,
    )
    explanation = llm_client.explain(_summarize_evidence(case), action)
    return CaseResult(
        case_id=case.case_id,
        intent=intent,
        next_question=None,
        action=action,
        explanation=explanation,
        policy_source=_ground_in_policy(rag, action.proposed_action),
        # No tool was ever proposed for an injection attempt (no
        # _tool_proposal_for_action mapping for "refuse") — there is nothing
        # for the Policy Engine to authorize. `intent.injection_attempt_detected`
        # is the auditable signal here, not an AuthorizationResult.
        authorization=None,
    )


def run_case(
    case: CaseInput,
    llm_client: LLMClient,
    rag: PolicyRAG | None = None,
    policy_config: PolicyConfig | None = None,
) -> CaseResult:
    intent = llm_client.extract_intent(case.customer_message)

    if intent.injection_attempt_detected:
        return _refusal(case, intent, llm_client, rag)

    evidence_summary = _summarize_evidence(case)
    next_question = llm_client.decide_next_question(evidence_summary, case.candidate_questions)

    if next_question.should_ask:
        action = ActionProposal(
            proposed_action="ask_question",
            reason=next_question.rationale,
            requires_human_approval=False,
        )
    else:
        action = llm_client.propose_action(
            evidence_summary,
            contradiction_count=len(case.contradictions),
            escalation_required=case.escalation_required,
        )

    explanation = llm_client.explain(evidence_summary, action)

    return CaseResult(
        case_id=case.case_id,
        intent=intent,
        next_question=next_question if next_question.should_ask else None,
        action=action,
        explanation=explanation,
        policy_source=_ground_in_policy(rag, action.proposed_action),
        authorization=_authorize_action(case, action, policy_config),
    )


def _ground_in_policy(rag: PolicyRAG | None, proposed_action: str) -> str | None:
    if rag is None:
        return None
    query = _POLICY_QUERY_BY_ACTION.get(proposed_action, proposed_action)
    result = rag.retrieve(query)
    return result.chunk.source_file if result else None
