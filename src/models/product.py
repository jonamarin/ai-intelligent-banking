"""Account/Product entity (docs/domain-model.md § Account / Product;
docs/data-dictionary.md § products)."""

import datetime as dt

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    product_type: Mapped[str] = mapped_column(String(50), nullable=False)
    product_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    credit_limit: Mapped[float | None] = mapped_column(Numeric(15, 2))
    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    opening_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[dt.date | None] = mapped_column(Date)
    # branches table is out of scope for this workflow (docs/data-dictionary.md
    # § Tables not used) — stored as a plain reference, no FK constraint.
    opening_branch_id: Mapped[str] = mapped_column(String(20), nullable=False)
    product_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    opening_channel: Mapped[str] = mapped_column(String(30), nullable=False)
    has_linked_app: Mapped[bool] = mapped_column(nullable=False, default=False)
    days_past_due: Mapped[int | None] = mapped_column()
    last_transaction_date: Mapped[dt.datetime | None] = mapped_column(DateTime)
    last_updated: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
