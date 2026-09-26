"""Audit Event entity (docs/domain-model.md § Audit Event — [new];
docs/observability.md § 3 for the exact JSON shape `payload` should hold).

`payload` must already be redacted before it is written here — this table
does not redact on write; the redaction guarantee lives in
src/config/logging.py's filter and must be applied equivalently wherever
audit events are constructed (Phase 13 formalizes this into a shared
audit-emission helper; until then, callers are responsible).
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
