"""Read-only tools (prompt.md § 16) — low action-risk, execute directly
against the database (docs/decision-policy.md § 6: "retrieve information...
can be automated"). Never expose raw SQLAlchemy/session objects to a
caller — always return plain dicts, so nothing upstream (including a future
LLM tool-result payload) can accidentally get write access through a
returned ORM object.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_customer(engine: Engine, customer_id: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT customer_id, country, segment, customer_status, registration_date "
                "FROM customers WHERE customer_id = :customer_id"
            ),
            {"customer_id": customer_id},
        ).fetchone()
    if row is None:
        return None
    return dict(row._mapping)


def get_transaction(engine: Engine, transaction_id: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT transaction_id, transaction_date, customer_id, amount, amount_usd, "
                "currency, channel, merchant_name, transaction_country, transaction_status, "
                "is_fraud FROM transactions WHERE transaction_id = :transaction_id"
            ),
            {"transaction_id": transaction_id},
        ).fetchone()
    if row is None:
        return None
    return dict(row._mapping)


def get_recent_transactions(
    engine: Engine, customer_id: str, *, before: str, limit: int = 5
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT transaction_id, transaction_date, amount_usd, merchant_name, "
                "transaction_status FROM transactions "
                "WHERE customer_id = :customer_id AND transaction_date < :before "
                "ORDER BY transaction_date DESC LIMIT :limit"
            ),
            {"customer_id": customer_id, "before": before, "limit": limit},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_merchant_profile(engine: Engine, merchant_category: str) -> dict[str, Any]:
    """No standalone merchant table (docs/data-dictionary.md) — a lightweight
    profile derived on the fly from transaction history, dataset-wide."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT count(*) AS transaction_count, "
                "avg(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END) AS fraud_rate "
                "FROM transactions WHERE merchant_category = :category"
            ),
            {"category": merchant_category},
        ).fetchone()
    return dict(row._mapping) if row else {"transaction_count": 0, "fraud_rate": None}
