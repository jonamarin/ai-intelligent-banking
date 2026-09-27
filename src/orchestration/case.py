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
        }
