"""Raw source table: digital_events (docs/data-dictionary.md).

This is the source data the Evidence Engine (Phase 5) derives the `Device`
entity from (src/models/device.py) — there is no standalone device table in
the dataset. At ~10,000,000 rows this is the largest table in the dataset;
see src/ingestion/README.md for why local ingestion defaults to a bounded
recent-date sample rather than the full history.
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DigitalEvent(Base):
    __tablename__ = "digital_events"

    event_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    event_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    process_date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_category: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(30))
    browser: Mapped[str | None] = mapped_column(String(50))
    app_version: Mapped[str | None] = mapped_column(String(20))
    page_url: Mapped[str | None] = mapped_column(String(300))
    page_title: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str | None] = mapped_column(String(100))
    element_id: Mapped[str | None] = mapped_column(String(100))
    product_id: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("products.product_id"), index=True
    )
    event_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    duration_seconds: Mapped[int | None] = mapped_column()
    ip_address: Mapped[str | None] = mapped_column(String(45))
    ip_country: Mapped[str | None] = mapped_column(String(50))
    ip_city: Mapped[str | None] = mapped_column(String(100))
    is_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    referrer: Mapped[str | None] = mapped_column(String(300))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(100))
