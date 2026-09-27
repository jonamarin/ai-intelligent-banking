"""The four approaches `docs/evaluation-plan.md` § 10 requires compared on
the same held-out workload (`sample.py`):

1. **Rules only** — a fixed threshold stack over the same engineered
   features the ML model trains on (`src/ml/features.py`). No fitting, no
   learned parameters — "Deterministic, cheap, auditable"
   (`docs/model-evaluation.md` § 12). Thresholds are illustrative
   (`PROPOSED`, `docs/decision-policy.md` § 10), not a business-approved
   rule set.
2. **Fraud ML only** — the trained XGBoost model (Phase 4,
   `data/models/xgboost-v0.1.0.joblib`) at a fixed probability threshold,
   with no evidence engine, no policy engine, no human in the loop.
3. **LLM only** — `MockLLMClient` called directly on the evidence summary,
   bypassing the Policy Engine entirely (`src/policies/authorization.py`
   never runs). This is deliberately unsafe in exactly the way the hybrid
   design exists to avoid (`docs/decision-policy.md` § 2) — measuring it is
   the point, not endorsing it as a deployment option.
4. **Hybrid** — the actual pipeline built in Phases 6-9
   (`src/orchestration/flow.py`'s `run_case()` + the Policy Engine).
   **Not the full hybrid `docs/model-evaluation.md` § 12 describes** — the
   Fraud ML model's score is not wired into orchestration at all (a
   pre-existing, already-documented gap: `docs/project-status.md` § Phase
   4/6/7/9 detail) — this measures Evidence + Policy Engine + LLM + Human,
   honestly labeled as such everywhere it's reported, not silently
   presented as the complete architecture.
"""

import dataclasses

import joblib
import pandas as pd

from src.agents.llm_client import MockLLMClient
from src.evidence.graph import EvidenceDirection
from src.ml.model import ModelArtifact
from src.ml.model import predict_proba as xgb_predict_proba
from src.orchestration.case import CaseInput
from src.orchestration.flow import run_case, summarize_evidence
from src.retrieval.policy_rag import PolicyRAG

# PROPOSED, illustrative — see module docstring. Mirrors the kind of signal
# the Evidence Engine (Phase 5) itself already computes (amount_deviation,
# country + failed-auth combination, historical dispute rate) but as a
# fixed rule instead of a graph of weighed, provenance-tracked evidence.
_AMOUNT_DEVIATION_THRESHOLD = 3.0
_COMPLAINT_COUNT_THRESHOLD = 3.0

_FLAGGED_ACTIONS = {"protect_account", "escalate", "create_dispute", "refuse"}


def rules_only_flag(features: dict[str, float]) -> bool:
    return (
        abs(features["amount_deviation"]) >= _AMOUNT_DEVIATION_THRESHOLD
        or (features["country_deviation"] >= 1.0 and features["auth_failed"] >= 1.0)
        or features["cust_complaint_count_prior"] >= _COMPLAINT_COUNT_THRESHOLD
    )


def load_xgboost_artifact(path: str) -> ModelArtifact:
    artifact: ModelArtifact = joblib.load(path)
    return artifact


def ml_only_flag(
    artifact: ModelArtifact, features: dict[str, float], *, threshold: float = 0.5
) -> bool:
    row = pd.DataFrame([features])[artifact.feature_columns]
    proba = xgb_predict_proba(artifact, row)[0]
    return bool(proba >= threshold)


@dataclasses.dataclass
class LLMOnlyOutcome:
    proposed_action: str
    flagged: bool
    # The LLM's own recommendation, trusted as-is here (this is the whole
    # point of "LLM only": no independent Policy Engine check overrides it —
    # docs/decision-policy.md § 2's "AI recommendation != authorization"
    # guarantee does not apply to this baseline by construction).
    requires_human_approval: bool


def llm_only_flag(case: CaseInput) -> LLMOnlyOutcome:
    llm = MockLLMClient()
    intent = llm.extract_intent(case.customer_message)
    if intent.injection_attempt_detected:
        return LLMOnlyOutcome("refuse", True, requires_human_approval=False)
    evidence_summary = summarize_evidence(case)
    next_question = llm.decide_next_question(evidence_summary, case.candidate_questions)
    if next_question.should_ask:
        return LLMOnlyOutcome("ask_question", False, requires_human_approval=False)
    action = llm.propose_action(
        evidence_summary,
        contradiction_count=len(case.contradictions),
        escalation_required=case.escalation_required,
    )
    return LLMOnlyOutcome(
        action.proposed_action,
        action.proposed_action in _FLAGGED_ACTIONS,
        requires_human_approval=action.requires_human_approval,
    )


@dataclasses.dataclass
class HybridOutcome:
    proposed_action: str
    flagged: bool
    policy_source: str | None
    authorized: bool | None
    requires_human_approval: bool | None


def hybrid_outcome(case: CaseInput, rag: PolicyRAG) -> HybridOutcome:
    result = run_case(case, MockLLMClient(), rag=rag)
    auth = result.authorization
    return HybridOutcome(
        proposed_action=result.action.proposed_action,
        flagged=result.action.proposed_action in _FLAGGED_ACTIONS,
        policy_source=result.policy_source,
        authorized=auth.authorized if auth else None,
        requires_human_approval=auth.requires_human_approval if auth else None,
    )


def evidence_supports_fraud_flag(case: CaseInput, *, confidence_threshold: float = 0.5) -> bool:
    """A fifth reference point, not one of the four required approaches:
    "would the Evidence Engine's own raw signals alone (no LLM, no policy,
    no rules threshold) have flagged this?" — any `supports_fraud` item at
    or above `confidence_threshold`. Useful context for interpreting the
    other four, not a substitute for any of them."""
    return any(
        item.direction == EvidenceDirection.SUPPORTS_FRAUD
        and item.confidence is not None
        and item.confidence >= confidence_threshold
        for item in case.evidence_items
    )
