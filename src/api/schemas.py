"""Request/response bodies for the case endpoints (`docs/api-contracts.md`
§ 1). All Pydantic-validated, `extra="forbid"` — "no endpoint accepts
unvalidated input" (`docs/api-contracts.md` § 2).

Two response shapes for the same case on purpose: `CustomerCaseView` never
carries a risk score, evidence identifier, or internal reasoning
(`.claude/rules/frontend.md`: "The customer view never exposes internal
risk scores, model internals, or raw evidence identifiers"); `AnalystCaseView`
carries everything. Which one a request gets is decided server-side by role
(`src/api/deps.py`), never by a client-supplied flag.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str


class EvidenceItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    type: str
    value: str
    direction: str
    confidence: float | None
    provenance: str


class DecisionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    decision: str
    model_version: str | None
    policy_version: str
    confidence: float | None
    analyst_explanation: str | None
    customer_explanation_es: str | None
    llm_degraded: bool
    model_degraded: bool
    created_at: dt.datetime


class AuditEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    created_at: dt.datetime


class CaseCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    transaction_id: str
    decision_id: str | None
    was_duplicate: bool
    proposed_action: str
    requires_human_approval: bool | None
    authorized: bool | None
    llm_degraded: bool


class CustomerCaseView(BaseModel):
    """`.claude/rules/frontend.md`: no risk score, no model internals, no
    raw evidence identifiers — a plain-language status and explanation
    only."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    status: str
    customer_explanation_es: str | None


class AnalystCaseView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    customer_id: str
    transaction_id: str | None
    status: str
    decision: str | None
    decision_reason: str | None
    human_review_status: str | None
    escalation_required: bool
    evidence: list[EvidenceItemOut]
    contradictions: list[list[str]]
    latest_decision: DecisionOut | None
    audit_trail: list[AuditEventOut]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str
    action: Literal["approve", "reject"]
    rationale: str | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    was_duplicate: bool


class CaseListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    customer_id: str
    status: str
    decision: str | None
    human_review_status: str | None
    created_at: dt.datetime


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["customer", "analyst", "supervisor"]
