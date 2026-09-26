"""Merchant entity (docs/domain-model.md § Merchant — [new], derived from
transactions.merchant_name/merchant_category; the dataset has no standalone
merchant dimension table)."""

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    merchant_category: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(50))
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    historical_chargeback_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
