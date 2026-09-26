"""Raw source table: daily_exchange_rates (docs/data-dictionary.md).

Used to reconcile transactions.amount vs. amount_usd when the latter is
missing or stale (docs/data-lineage.md § 3).
"""

import datetime as dt

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ExchangeRate(Base):
    __tablename__ = "daily_exchange_rates"

    date: Mapped[dt.date] = mapped_column(primary_key=True)
    source_currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    target_currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    buy_rate: Mapped[float | None] = mapped_column(Numeric(12, 6))
    sell_rate: Mapped[float | None] = mapped_column(Numeric(12, 6))
    source: Mapped[str | None] = mapped_column(String(50))
