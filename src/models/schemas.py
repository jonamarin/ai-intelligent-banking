"""Pydantic schemas mirroring the SQLAlchemy models in this package.

Read schemas for the entities most likely to appear in an API response
first (docs/api-contracts.md § 1's proposed endpoints center on cases,
evidence, and decisions). Device, Merchant, and CustomerInteraction schemas
are added when the endpoints/tools that expose them land (Phase 6+) rather
than pre-built now with no consumer to validate their shape against.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict

from src.models.evidence import EvidenceDirection


class CustomerRead(BaseModel):
    """Minimized projection — see src/models/customer.py's docstring: routine
    risk-scoring code should request this, not the full ORM row."""

    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    segment: str
    country: str
    customer_status: str
    registration_date: dt.datetime


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    transaction_date: dt.datetime
    customer_id: str
    product_id: str
    transaction_type: str
    amount: float
    currency: str
    channel: str
    merchant_name: str | None
    transaction_country: str
    transaction_status: str


class FraudCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    customer_id: str
    transaction_id: str | None
    created_at: dt.datetime
    status: str
    risk_score: float | None
    decision: str | None
    escalation_required: bool
    human_review_status: str | None


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    case_id: str
    source: str
    type: str
    value: str | None
    direction: EvidenceDirection
    confidence: float | None
    timestamp: dt.datetime
    provenance: str


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    case_id: str
    decision: str
    model_version: str | None
    policy_version: str
    prompt_version: str | None
    confidence: float | None
    explanation: str | None
    created_at: dt.datetime


class HumanReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    case_id: str
    decision_id: str | None
    reviewer_id: str
    action: str
    rationale: str | None
    created_at: dt.datetime
