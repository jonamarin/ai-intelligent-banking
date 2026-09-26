"""Raw source table: call_center_interactions (docs/data-dictionary.md).

This is a near-1:1 mirror of the LATAM Bank dataset table, populated directly
by ingestion (src/ingestion/). It is distinct from
src/models/customer_interaction.py's `CustomerInteraction` — that is this
system's own curated, channel-agnostic entity (docs/domain-model.md §
Customer Interaction), populated FROM rows like these (and from live chat)
by the conversation layer in later phases. Don't conflate the two.

`agent_id` references the dataset's service_agents table, which is out of
this workflow's modeled scope (docs/data-dictionary.md § Tables not used) —
stored as a plain reference, no FK.
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CallCenterInteraction(Base):
    __tablename__ = "call_center_interactions"

    interaction_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    interaction_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    process_date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(String(20))
    interaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    contact_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_category: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column()
    wait_time_seconds: Mapped[int | None] = mapped_column()
    was_resolved: Mapped[bool | None] = mapped_column(Boolean)
    requires_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detected_sentiment: Mapped[str | None] = mapped_column(String(20))
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    customer_detected_accent: Mapped[str | None] = mapped_column(String(50))
    agent_used_accent: Mapped[str | None] = mapped_column(String(50))
    was_escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mentioned_products: Mapped[str | None] = mapped_column(String(200))
    has_transcript: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_recording: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
