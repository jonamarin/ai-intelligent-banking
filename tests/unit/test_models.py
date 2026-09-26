import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from src.models import (
    Customer,
    Decision,
    Evidence,
    EvidenceDirection,
    FraudCase,
    HumanReview,
    Product,
    Transaction,
)


def _make_customer(customer_id: str = "CUST-1", document_number: str = "DOC-1") -> Customer:
    return Customer(
        customer_id=customer_id,
        document_number=document_number,
        document_type="CC",
        first_name="Ana",
        last_name="Gomez",
        date_of_birth=dt.date(1990, 1, 1),
        city="Bogota",
        state="Cundinamarca",
        country="Colombia",
        segment="Plus",
        registration_date=dt.datetime(2023, 1, 1),
        registration_branch_id="BR-1",
        customer_status="Active",
        last_updated=dt.datetime(2023, 1, 1),
    )


def test_customer_document_number_must_be_unique(db_session) -> None:
    db_session.add(_make_customer("CUST-1", "DOC-1"))
    db_session.commit()

    db_session.add(_make_customer("CUST-2", "DOC-1"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_product_requires_existing_customer(db_session) -> None:
    product = Product(
        product_id="PROD-1",
        customer_id="does-not-exist",
        product_type="Checking Account",
        product_number="ACC-1",
        currency="COP",
        current_balance=1000,
        opening_date=dt.date(2023, 1, 1),
        opening_branch_id="BR-1",
        product_status="Active",
        opening_channel="Branch",
        last_updated=dt.datetime(2023, 1, 1),
    )
    db_session.add(product)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_transaction_links_to_customer_and_product(db_session) -> None:
    customer = _make_customer()
    db_session.add(customer)
    db_session.flush()

    product = Product(
        product_id="PROD-1",
        customer_id=customer.customer_id,
        product_type="Checking Account",
        product_number="ACC-1",
        currency="COP",
        current_balance=1000,
        opening_date=dt.date(2023, 1, 1),
        opening_branch_id="BR-1",
        product_status="Active",
        opening_channel="Branch",
        last_updated=dt.datetime(2023, 1, 1),
    )
    db_session.add(product)
    db_session.flush()

    transaction = Transaction(
        transaction_id="TXN-1",
        transaction_date=dt.datetime(2024, 1, 1),
        process_date=dt.date(2024, 1, 1),
        product_id=product.product_id,
        customer_id=customer.customer_id,
        transaction_type="Purchase",
        amount=850,
        currency="COP",
        channel="POS",
        transaction_country="Colombia",
        transaction_status="Approved",
        is_fraud=False,
    )
    db_session.add(transaction)
    db_session.commit()

    stored = db_session.get(Transaction, "TXN-1")
    assert stored is not None
    assert stored.customer_id == customer.customer_id


def test_evidence_direction_rejects_invalid_value(db_session) -> None:
    customer = _make_customer()
    db_session.add(customer)
    case = FraudCase(
        case_id="CASE-1",
        customer_id=customer.customer_id,
        created_at=dt.datetime(2024, 1, 1),
        status="open",
    )
    db_session.add(case)
    db_session.flush()

    bad_evidence = Evidence(
        evidence_id="EVID-1",
        case_id=case.case_id,
        source="digital_events",
        type="device_history",
        direction="not_a_real_direction",  # type: ignore[arg-type]
        timestamp=dt.datetime(2024, 1, 1),
        provenance="test",
    )
    db_session.add(bad_evidence)
    # The Enum column type (validate_strings=True) validates on flush (when
    # it's actually bound to a DBAPI parameter), not at attribute-assignment
    # time — and raises a wrapped LookupError, not a bare one.
    with pytest.raises(StatementError, match="not among the defined enum values"):
        db_session.flush()


def test_evidence_accepts_valid_direction(db_session) -> None:
    customer = _make_customer()
    db_session.add(customer)
    case = FraudCase(
        case_id="CASE-1",
        customer_id=customer.customer_id,
        created_at=dt.datetime(2024, 1, 1),
        status="open",
    )
    db_session.add(case)
    db_session.flush()

    evidence = Evidence(
        evidence_id="EVID-1",
        case_id=case.case_id,
        source="digital_events",
        type="device_history",
        direction=EvidenceDirection.SUPPORTS_FRAUD,
        timestamp=dt.datetime(2024, 1, 1),
        provenance="test",
    )
    db_session.add(evidence)
    db_session.commit()

    stored = db_session.get(Evidence, "EVID-1")
    assert stored is not None
    assert stored.direction == EvidenceDirection.SUPPORTS_FRAUD


def test_decision_requires_policy_version(db_session) -> None:
    customer = _make_customer()
    db_session.add(customer)
    case = FraudCase(
        case_id="CASE-1",
        customer_id=customer.customer_id,
        created_at=dt.datetime(2024, 1, 1),
        status="open",
    )
    db_session.add(case)
    db_session.flush()

    decision = Decision(
        decision_id="DEC-1",
        case_id=case.case_id,
        decision="auto_resolved",
        policy_version=None,  # type: ignore[arg-type]
        created_at=dt.datetime(2024, 1, 1),
    )
    db_session.add(decision)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_human_review_is_distinct_from_decision(db_session) -> None:
    """docs/domain-model.md § Human Review: a human's decision must never be
    merged into the AI's Decision record."""
    customer = _make_customer()
    db_session.add(customer)
    case = FraudCase(
        case_id="CASE-1",
        customer_id=customer.customer_id,
        created_at=dt.datetime(2024, 1, 1),
        status="open",
    )
    db_session.add(case)
    db_session.flush()

    decision = Decision(
        decision_id="DEC-1",
        case_id=case.case_id,
        decision="escalate",
        policy_version="v1",
        created_at=dt.datetime(2024, 1, 1),
    )
    db_session.add(decision)
    db_session.flush()

    review = HumanReview(
        review_id="REV-1",
        case_id=case.case_id,
        decision_id=decision.decision_id,
        reviewer_id="AGENT-1",
        action="approve",
        created_at=dt.datetime(2024, 1, 2),
    )
    db_session.add(review)
    db_session.commit()

    assert db_session.get(Decision, "DEC-1") is not None
    assert db_session.get(HumanReview, "REV-1") is not None
