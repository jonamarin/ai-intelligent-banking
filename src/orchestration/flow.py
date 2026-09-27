"""The case orchestration state machine (docs/architecture.md § 2, § 8).

    intent extraction -> (refuse if injection) -> next-question gate
    -> action proposal -> policy grounding (RAG) -> explanation

Every stage's output is a Pydantic-validated structured type
(src/agents/schemas.py) — never raw text threaded between stages. Nothing
this module produces is executed: `CaseResult.action` is a proposal
(docs/decision-policy.md § 2), and no action tool is called here at all —
see src/tools/base.py for why. This is intentional per
docs/implementation-roadmap.md Phase 6's own stated risk: building the
orchestrator before the policy engine (Phase 7) exists risks accidentally
wiring direct execution — this module doesn't import src.tools.action_tools
for that reason, only src.tools.read_tools where a live case needs context.
"""

from src.agents.llm_client import LLMClient
from src.agents.schemas import ActionProposal, IntentResult
from src.orchestration.case import CaseInput, CaseResult
from src.retrieval.policy_rag import PolicyRAG

_POLICY_QUERY_BY_ACTION = {
    "create_dispute": "política de disputas de transacciones",
    "protect_account": "bloqueo de tarjeta por fraude",
    "escalate": "procedimientos de escalamiento a humano",
    "ask_question": "política de disputas de transacciones",
    "auto_resolve": "política de disputas de transacciones",
    "refuse": "autenticación instrucciones del cliente",
}


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
    )


def run_case(case: CaseInput, llm_client: LLMClient, rag: PolicyRAG | None = None) -> CaseResult:
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
    )


def _ground_in_policy(rag: PolicyRAG | None, proposed_action: str) -> str | None:
    if rag is None:
        return None
    query = _POLICY_QUERY_BY_ACTION.get(proposed_action, proposed_action)
    result = rag.retrieve(query)
    return result.chunk.source_file if result else None
