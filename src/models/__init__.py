"""SQLAlchemy models + session management for the entities in
docs/domain-model.md § 3.

Every model must be imported here so Base.metadata is complete for Alembic
autogeneration and for Base.metadata.create_all(...) in tests — a model
defined but not imported anywhere is invisible to both.
"""

from src.models.audit_event import AuditEvent
from src.models.base import Base
from src.models.customer import Customer
from src.models.customer_interaction import CustomerInteraction
from src.models.decision import Decision, decision_evidence
from src.models.device import Device
from src.models.evidence import Evidence, EvidenceDirection
from src.models.fraud_case import FraudCase
from src.models.human_review import HumanReview
from src.models.merchant import Merchant
from src.models.product import Product
from src.models.transaction import Transaction

__all__ = [
    "AuditEvent",
    "Base",
    "Customer",
    "CustomerInteraction",
    "Decision",
    "Device",
    "Evidence",
    "EvidenceDirection",
    "FraudCase",
    "HumanReview",
    "Merchant",
    "Product",
    "Transaction",
    "decision_evidence",
]
