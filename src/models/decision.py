"""Decision entity (docs/domain-model.md § Decision — [new]).

Every field required for decision provenance (docs/decision-policy.md § 9) is
mandatory here on purpose — a Decision missing its model/policy version is a
data-integrity bug, not an acceptable partial record. `decision_evidence` is
a many-to-many link table rather than a JSON array of IDs so referential
integrity is enforced by the database, not just convention.

`llm_degraded`/`model_degraded` (Phase 9, docs/demo-script.md Scenarios E/F)
are real columns, not buried in `AuditEvent.payload` — "clearly flagged ...
in the decision record" per docs/demo-script.md Scenario E's own wording, and
queryable without parsing JSON.

`analyst_explanation`/`customer_explanation_es` (Phase 10, `prompt.md` § 22
"dual explanation") replace the original single `explanation` column: the
customer-facing text (`src/agents/schemas.py`'s `CaseExplanation.
customer_explanation_es`) was generated at case-creation time but never
persisted anywhere before this — a real gap only surfaced once Phase 10
needed to *read it back* for the customer view, not just generate it once
and discard it.
"""

import datetime as dt

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

decision_evidence = Table(
    "decision_evidence",
    Base.metadata,
    Column("decision_id", String(36), ForeignKey("decisions.decision_id"), primary_key=True),
    Column("evidence_id", String(36), ForeignKey("evidence.evidence_id"), primary_key=True),
)


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50))
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    analyst_explanation: Mapped[str | None] = mapped_column(Text)
    customer_explanation_es: Mapped[str | None] = mapped_column(Text)
    llm_degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
