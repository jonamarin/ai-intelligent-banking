"""Action Execution entity (Phase 9, docs/architecture.md § 11: "Actions
with financial or state-changing effects ... require an idempotency key
derived from the case and action type so a retried or duplicated request
cannot execute twice").

`idempotency_key` is the primary key, not just a unique-indexed column — a
retried/duplicated request attempting to insert the same key is a straight
INSERT ... ON CONFLICT DO NOTHING at the database level
(src/policies/gateway.py's `persist_decision`), making double-execution
structurally hard rather than only policy-forbidden (.claude/rules/database.md).

`decision_id`'s FK is `DEFERRABLE INITIALLY DEFERRED`: `persist_decision`
reserves the idempotency key (inserts this row) *before* inserting the
`Decision` row it references, within the same transaction — so the
referenced row doesn't exist yet at the moment of this INSERT, only by the
time the transaction commits. An immediate (default) FK would reject that
ordering even though it's the correct one: reserving the key first, and
only creating the Decision if the reservation actually succeeded, is what
avoids leaving an orphaned Decision behind on a detected duplicate.
"""

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ActionExecution(Base):
    __tablename__ = "action_executions"

    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("decisions.decision_id", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
