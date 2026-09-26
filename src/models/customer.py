"""Customer entity (docs/domain-model.md § Customer; docs/data-dictionary.md § customers).

PII classification (docs/data-governance.md § 1) is noted per field. Direct
identifiers (document_number, email, phone, address) are stored here because
they exist in the source dataset and some workflows (e.g. human review) need
them, but application code retrieving a Customer for routine risk scoring
should project only the minimized field set documented in
docs/domain-model.md § Customer — this model does not enforce that
projection itself; the retrieval layer (Phase 6) does.
"""

import datetime as dt

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)

    # --- Direct identifiers (docs/data-governance.md § 1: minimize exposure) ---
    document_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(10), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100))
    mobile_phone: Mapped[str | None] = mapped_column(String(20))
    landline_phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(200))

    # --- Quasi-identifiers ---
    date_of_birth: Mapped[dt.date] = mapped_column(Date, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(10))

    gender: Mapped[str | None] = mapped_column(String(1))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # --- Sensitive derived signals — evaluation-slicing only, never a decision
    # input (docs/data-governance.md § 5, docs/model-evaluation.md § 13) ---
    detected_accent: Mapped[str | None] = mapped_column(String(50))
    segment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    credit_score: Mapped[int | None] = mapped_column()
    estimated_monthly_income: Mapped[float | None] = mapped_column()
    occupation: Mapped[str | None] = mapped_column(String(100))
    marital_status: Mapped[str | None] = mapped_column(String(20))
    education_level: Mapped[str | None] = mapped_column(String(50))

    registration_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    # branches table is out of scope for this workflow (docs/data-dictionary.md
    # § Tables not used) — stored as a plain reference, no FK constraint.
    registration_branch_id: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    last_updated: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    accepts_marketing: Mapped[bool] = mapped_column(nullable=False, default=False)
