"""Human Review entity (docs/domain-model.md § Human Review — [new]).

Kept structurally distinct from Decision on purpose: "AI recommended X, human
decided Y" must stay auditable even when the human simply approves the AI's
recommendation unchanged (docs/domain-model.md § Human Review,
docs/human-oversight.md § 4). `reviewer_id` references a service_agents row
in the source dataset, but that table is out of Phase 2's modeled scope
(docs/data-dictionary.md § Tables not used) — stored as a plain reference,
no FK, until an analyst-identity phase needs it (Phase 10).
"""

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class HumanReview(Base):
    __tablename__ = "human_reviews"

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), nullable=False, index=True
    )
    decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("decisions.decision_id"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
