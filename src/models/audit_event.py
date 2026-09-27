"""Audit Event entity (docs/domain-model.md § Audit Event — [new];
docs/observability.md § 3 for the exact JSON shape `payload` should hold).

`payload` must already be redacted before it is written here — this table
does not redact on write; the redaction guarantee is `src/security/
redaction.py`'s `redact_value()` (Phase 8), called by every current writer
(`src/evidence/persist.py`, `src/policies/gateway.py`) before the insert —
apply it equivalently wherever a new audit-event writer is added.
"""

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), index=True
    )
    decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("decisions.decision_id"), index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
