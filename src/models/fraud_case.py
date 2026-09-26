"""Fraud/Dispute Case entity (docs/domain-model.md § Fraud/Dispute Case — [new]).

`risk_score` is a model prediction attached to the case for convenience, not
the case's authoritative outcome — the authoritative outcome is a Decision
record (src/models/decision.py), kept distinct on purpose
(docs/domain-model.md § 2, § 4).
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class FraudCase(Base):
    __tablename__ = "fraud_cases"

    case_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("transactions.transaction_id"), index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Model prediction — not the case's authoritative outcome; see docstring.
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    decision: Mapped[str | None] = mapped_column(String(30))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    escalation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_review_status: Mapped[str | None] = mapped_column(String(30))
