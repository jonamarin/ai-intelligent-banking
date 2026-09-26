"""Raw source table: complaints / PQR (docs/data-dictionary.md).

The dataset's dispute-history source — feeds `historical_dispute_rate` and
`is_repeat_complainer` fraud-model features (docs/model-evaluation.md § 4).
`related_branch_id`/`assigned_agent_id` are plain references, no FK
(branches/service_agents are out of this workflow's modeled scope,
docs/data-dictionary.md § Tables not used).
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Complaint(Base):
    __tablename__ = "complaints"

    complaint_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    creation_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    process_date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    case_type: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    reception_channel: Mapped[str] = mapped_column(String(30), nullable=False)
    affected_product_id: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("products.product_id"), index=True
    )
    related_branch_id: Mapped[str | None] = mapped_column(String(20))
    origin_interaction_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("call_center_interactions.interaction_id"), index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    claimed_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(20))
    assignment_date: Mapped[dt.datetime | None] = mapped_column(DateTime)
    first_response_date: Mapped[dt.datetime | None] = mapped_column(DateTime)
    resolution_date: Mapped[dt.datetime | None] = mapped_column(DateTime)
    closing_date: Mapped[dt.datetime | None] = mapped_column(DateTime)
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolution_days: Mapped[int | None] = mapped_column()
    resolution: Mapped[str | None] = mapped_column(Text)
    compensation_granted: Mapped[float | None] = mapped_column(Numeric(15, 2))
    resolution_satisfaction: Mapped[int | None] = mapped_column()
    is_repeat_complainer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
