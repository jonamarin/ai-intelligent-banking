"""Evidence entity (docs/domain-model.md § Evidence, § Evidence Graph — [new]).

Evidence is append-only by design — there is no update/delete path for it at
the application or schema level (docs/guardrails.md § 4, the "delete the
fraud evidence" red-team case). Every row must be traceable to a Fact or a
specific model output via `provenance` — never to "the LLM said so"
(docs/domain-model.md § Evidence).
"""

import datetime as dt
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EvidenceDirection(enum.StrEnum):
    SUPPORTS_FRAUD = "supports_fraud"
    SUPPORTS_LEGITIMATE = "supports_legitimate"
    NEUTRAL = "neutral"


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[EvidenceDirection] = mapped_column(
        Enum(
            EvidenceDirection,
            native_enum=False,
            length=30,
            validate_strings=True,
            # Store the lowercase .value ("supports_fraud") to match
            # docs/domain-model.md's documented direction strings — without
            # this, SQLAlchemy stores the Python member NAME
            # ("SUPPORTS_FRAUD") instead, a real inconsistency caught when
            # inspecting the first real rows written by the Evidence Engine
            # (docs/project-status.md § Phase 5 detail).
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
