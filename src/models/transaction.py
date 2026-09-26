"""Transaction entity (docs/domain-model.md § Transaction;
docs/data-dictionary.md § transactions — the primary table for this workflow).

is_fraud / fraud_score are SYNTHETIC dataset-generated labels, not this
system's own determination and not usable model features — see
docs/data-lineage.md § 5 (leakage) before touching either column in any
feature-engineering code.
"""

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    transaction_date: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    process_date: Mapped[dt.date] = mapped_column(nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("products.product_id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_category: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_usd: Mapped[float | None] = mapped_column(Numeric(15, 2))
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    # branches table is out of scope for this workflow — plain reference, no FK.
    branch_id: Mapped[str | None] = mapped_column(String(20))
    merchant_name: Mapped[str | None] = mapped_column(String(150), index=True)
    merchant_category: Mapped[str | None] = mapped_column(String(50))
    transaction_country: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_city: Mapped[str | None] = mapped_column(String(100))
    transaction_status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_code: Mapped[str | None] = mapped_column(String(10))

    # SYNTHETIC dataset labels — excluded from model features (docs/data-lineage.md § 5).
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fraud_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
