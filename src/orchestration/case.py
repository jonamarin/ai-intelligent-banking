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


@dataclasses.dataclass
class CaseResult:
    case_id: str
    intent: IntentResult
    next_question: NextQuestionDecision | None
    action: ActionProposal
    explanation: CaseExplanation
    policy_source: str | None  # source_file of the RAG chunk grounding the explanation, if any

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "intent": self.intent.model_dump(),
            "next_question": self.next_question.model_dump() if self.next_question else None,
            "action": self.action.model_dump(),
            "explanation": self.explanation.model_dump(),
            "policy_source": self.policy_source,
        }
