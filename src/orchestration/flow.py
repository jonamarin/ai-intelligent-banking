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

Every `llm_client` call is wrapped in `retry.call_with_retry` (Phase 9,
docs/architecture.md § 10) — bounded retries, then `LLMUnavailableError`,
caught once here to switch to `fallback.py`'s deterministic path
(`CaseResult.llm_degraded=True`, `docs/demo-script.md` Scenario E) instead
of raising out of `run_case()` and leaving the caller with nothing.
"""

from src.agents.llm_client import LLMClient
from src.agents.schemas import ActionProposal, IntentResult
from src.config.settings import get_settings
from src.orchestration.case import CaseInput, CaseResult
from src.orchestration.fallback import (
    fallback_explain,
    fallback_extract_intent,
    fallback_propose_action,
)
from src.orchestration.retry import LLMUnavailableError, call_with_retry
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


def summarize_evidence(case: CaseInput) -> str:
    """Public (not `_`-prefixed): reused by `evaluation/baselines.py`'s
    "LLM only" baseline (Phase 11, docs/evaluation-plan.md § 10), which
    calls `MockLLMClient` directly with the same evidence summary this
    pipeline itself would compute — single source of truth, not a copy."""
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
    explanation = llm_client.explain(summarize_evidence(case), action)
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


def _degraded_result(
    case: CaseInput,
    rag: PolicyRAG | None,
    policy_config: PolicyConfig | None,
    intent: IntentResult | None = None,
) -> CaseResult:
    """Scenario E (`docs/demo-script.md`): the LLM is unavailable. Intent
    detection still runs locally (`fallback_extract_intent` — pure regex, no
    provider call); everything downstream degrades to
    `src/orchestration/fallback.py`'s conservative, escalate-by-default path.
    """
    if intent is None:
        intent = fallback_extract_intent(case.customer_message)
    action = fallback_propose_action(intent.injection_attempt_detected)
    explanation = fallback_explain(action)
    return CaseResult(
        case_id=case.case_id,
        intent=intent,
        next_question=None,
        action=action,
        explanation=explanation,
        policy_source=_ground_in_policy(rag, action.proposed_action),
        authorization=(
            None
            if action.proposed_action == "refuse"
            else _authorize_action(case, action, policy_config)
        ),
        llm_degraded=True,
    )


def run_case(
    case: CaseInput,
    llm_client: LLMClient,
    rag: PolicyRAG | None = None,
    policy_config: PolicyConfig | None = None,
    max_attempts: int | None = None,
) -> CaseResult:
    attempts = max_attempts if max_attempts is not None else get_settings().llm_max_attempts

    try:
        intent = call_with_retry(
            llm_client.extract_intent, case.customer_message, max_attempts=attempts
        )
    except LLMUnavailableError:
        return _degraded_result(case, rag, policy_config)

    if intent.injection_attempt_detected:
        return _refusal(case, intent, llm_client, rag)

    evidence_summary = summarize_evidence(case)

    try:
        next_question = call_with_retry(
            llm_client.decide_next_question,
            evidence_summary,
            case.candidate_questions,
            max_attempts=attempts,
        )
        if next_question.should_ask:
            action = ActionProposal(
                proposed_action="ask_question",
                reason=next_question.rationale,
                requires_human_approval=False,
            )
        else:
            action = call_with_retry(
                llm_client.propose_action,
                evidence_summary,
                contradiction_count=len(case.contradictions),
                escalation_required=case.escalation_required,
                max_attempts=attempts,
            )
        explanation = call_with_retry(
            llm_client.explain, evidence_summary, action, max_attempts=attempts
        )
    except LLMUnavailableError:
        return _degraded_result(case, rag, policy_config, intent=intent)

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
    # Vector DB / RAG unavailable (docs/architecture.md § 10): answer only
    # with retrieved, verifiable facts — if retrieval itself is broken,
    # degrade to "policy could not be verified" (None) rather than letting a
    # RAG exception crash the whole case.
    if rag is None:
        return None
    query = _POLICY_QUERY_BY_ACTION.get(proposed_action, proposed_action)
    try:
        result = rag.retrieve(query)
    except Exception:
        return None
    return result.chunk.source_file if result else None
