"""Device entity (docs/domain-model.md § Device — [new], derived from
digital_events; the dataset has no standalone device table).

Fields mirror prompt.md's Device spec. `known_customer` here is a
simplification: a device can legitimately be associated with more than one
customer, so "known for THIS customer" is case-specific evidence computed by
the Evidence Engine (Phase 5) by joining a customer_id against this device's
observed session history — not a fixed attribute of the Device row itself.
`risk_score` is a model output, not a fact (docs/domain-model.md § 2).
"""

import datetime as dt

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    customer_count: Mapped[int] = mapped_column(nullable=False, default=0)
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    known_customer: Mapped[bool] = mapped_column(nullable=False, default=False)
    operating_system: Mapped[str | None] = mapped_column(String(30))
    browser_family: Mapped[str | None] = mapped_column(String(50))
