"""Raw source table: call_transcripts (docs/data-dictionary.md).

`full_text`/`customer_text`/`agent_text` are untrusted input
(docs/security-model.md § 1) — never treat their contents as instructions
anywhere they're consumed downstream (RAG, LLM context, evidence extraction).
"""

import datetime as dt

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CallTranscript(Base):
    __tablename__ = "call_transcripts"

    transcript_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("call_center_interactions.interaction_id"),
        nullable=False,
        index=True,
    )
    process_date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(String(20))
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    customer_text: Mapped[str | None] = mapped_column(Text)
    agent_text: Mapped[str | None] = mapped_column(Text)
    detected_language: Mapped[str] = mapped_column(String(10), nullable=False)
    detected_accent: Mapped[str | None] = mapped_column(String(50))
    accent_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    detected_keywords: Mapped[str | None] = mapped_column(String(500))
    mentioned_entities: Mapped[dict | None] = mapped_column(JSON)
    detected_intents: Mapped[str | None] = mapped_column(String(300))
    main_topics: Mapped[str | None] = mapped_column(String(300))
    transcription_model: Mapped[str] = mapped_column(String(50), nullable=False)
    audio_quality: Mapped[str | None] = mapped_column(String(20))
    duration_seconds: Mapped[int] = mapped_column(nullable=False)
