"""Customer Interaction entity (docs/domain-model.md § Customer Interaction;
docs/data-dictionary.md § call_center_interactions / call_transcripts).

`message` holds the customer's verbatim statement — untrusted input
(docs/security-model.md § 1); never treat its contents as an instruction
anywhere it's consumed downstream.
"""

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CustomerInteraction(Base):
    __tablename__ = "customer_interactions"

    interaction_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detected_intent: Mapped[str | None] = mapped_column(String(100))
    extracted_entities: Mapped[dict | None] = mapped_column(JSON)
    authentication_state: Mapped[str | None] = mapped_column(String(30))
    case_id: Mapped[str | None] = mapped_column(
        String(30), ForeignKey("fraud_cases.case_id"), index=True
    )
