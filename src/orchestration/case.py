"""Unified case input/output shapes for the orchestration flow (flow.py).

`CaseInput` decouples the orchestration logic from where the evidence came
from: a golden-case fixture (`golden_case_loader.py`, fully offline) or a
live evidence graph built against the real database (Phase 5,
`src/evidence/graph.py`). Both are converted to this same shape so flow.py
has exactly one code path, not two — see live_case.py for the live-data
conversion.
"""

import dataclasses

from src.agents.schemas import ActionProposal, CaseExplanation, IntentResult, NextQuestionDecision
from src.evidence.graph import EvidenceItem
from src.policies.authorization import AuthorizationResult


@dataclasses.dataclass
class CaseInput:
    case_id: str
    customer_id: str
    transaction_id: str | None
    customer_message: str
    evidence_items: list[EvidenceItem]
    contradictions: list[tuple[str, str]]
    escalation_required: bool
    candidate_questions: list[str] = dataclasses.field(default_factory=list)
    # Facts the Policy Engine (Phase 7, src/policies/) uses to classify
    # action-risk independently of anything the LLM recommends
    # (docs/decision-policy.md § 6) — never derived from customer_message.
    case_status: str = "open"
    transaction_type: str | None = None
    amount_usd: float | None = None
    # A customer's own explicit ask (e.g. "large_refund") distinct from the
    # transaction's own type — evaluation/golden_cases/prompt_injection.json's
    # scenario: the request itself, not the underlying transaction, is what
    # needs classifying.
    requested_action: str | None = None
    requested_amount_usd: float | None = None
    # The trained fraud model's score for this transaction (src/ml/score.py)
    # — None for a golden-case fixture (no live feature pipeline backs a
    # synthetic transaction; honestly "Unknown", never a fabricated score,
    # matching this project's confidence=None convention) or for a live
    # case where the model artifact itself is unavailable (see
    # model_degraded below). Read by src/policies/action_risk.py to
    # (only ever) escalate action-risk — docs/decision-policy.md § 5's
    # risk bands, finally wired in.
    fraud_model_score: float | None = None
    # True only when a live case expected a score and src/ml/score.py
    # returned None because the model artifact was unavailable — distinct
    # from a golden case's fraud_model_score=None, which is simply "not
    # applicable," never "degraded." Mirrors llm_degraded (Phase 9).
    model_degraded: bool = False


@dataclasses.dataclass
class CaseResult:
    case_id: str
    intent: IntentResult
    next_question: NextQuestionDecision | None
    action: ActionProposal
    explanation: CaseExplanation
    policy_source: str | None  # source_file of the RAG chunk grounding the explanation, if any
    # None for "ask_question"/"refuse" outcomes — no tool call is proposed for
    # either, so there is nothing for the Policy Engine (Phase 7) to
    # authorize (src/policies/authorization.py).
    authorization: AuthorizationResult | None = None
    # True when the configured LLMClient failed and this result came from
    # src/orchestration/fallback.py instead (Phase 9, docs/demo-script.md
    # Scenario E) — "the degradation itself is an audit event."
    llm_degraded: bool = False
    # Copied from CaseInput.model_degraded (never computed in here — flow.py
    # has no DB access and must stay fully offline-capable for golden
    # cases). docs/demo-script.md Scenario F.
    model_degraded: bool = False

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "intent": self.intent.model_dump(),
            "next_question": self.next_question.model_dump() if self.next_question else None,
            "action": self.action.model_dump(),
            "explanation": self.explanation.model_dump(),
            "policy_source": self.policy_source,
            "authorization": (
                dataclasses.asdict(self.authorization) if self.authorization else None
            ),
            "llm_degraded": self.llm_degraded,
            "model_degraded": self.model_degraded,
        }
