"""Evidence graph construction (docs/domain-model.md § Evidence Graph;
prompt.md § 10).

Builds a structured evidence graph for one transaction: what supports fraud,
what supports legitimacy, what's unknown, and what contradicts what — never
collapsing to a single score (docs/domain-model.md § 4). Every evidence item
carries `direction`/`confidence`/`provenance`, matching the `Evidence` model
(src/models/evidence.py) exactly, so the graph this module builds is what
gets persisted, not a separate shadow representation.

**The direction/confidence values below are illustrative heuristics, not
approved policy** (`docs/decision-policy.md` § 5, `CLAUDE.md` § 7) — this
module answers "what does the evidence suggest," never "what action is
authorized." That's the Policy Engine's job (Phase 7), which does not exist
yet; this module must never be wired to a tool that executes an action.
"""

import dataclasses
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from src.evidence.device import DeviceHistory, compute_device_fingerprint, get_device_history
from src.models.evidence import EvidenceDirection

# Confidence threshold above which two opposing-direction evidence items are
# flagged as a contradiction rather than just coexisting weak signals.
CONTRADICTION_CONFIDENCE_THRESHOLD = 0.4


@dataclasses.dataclass
class EvidenceItem:
    evidence_id: str
    source: str
    type: str
    value: str
    direction: EvidenceDirection
    confidence: float | None  # None = Unknown/uncomputable, not a fabricated 0.0
    timestamp: dt.datetime
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "type": self.type,
            "value": self.value,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "provenance": self.provenance,
        }


@dataclasses.dataclass
class EvidenceGraph:
    case_id: str
    customer_id: str
    transaction_id: str
    created_at: dt.datetime
    items: list[EvidenceItem]
    contradictions: list[tuple[str, str]]  # (evidence_id, evidence_id) pairs

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "customer_id": self.customer_id,
            "transaction_id": self.transaction_id,
            "created_at": self.created_at.isoformat(),
            "evidence": [item.to_dict() for item in self.items],
            "contradictions": self.contradictions,
        }


def _new_id() -> str:
    return str(uuid.uuid4())


def _new_case_id() -> str:
    # fraud_cases.case_id is VARCHAR(30) (src/models/fraud_case.py, matching
    # the dataset's own ID-string conventions) — a full UUID (36 chars,
    # exactly what Evidence.evidence_id's VARCHAR(36) expects) doesn't fit.
    return f"CASE-{uuid.uuid4().hex[:20].upper()}"


def _item(
    source: str,
    type_: str,
    value: Any,
    direction: EvidenceDirection,
    confidence: float | None,
    timestamp: dt.datetime,
    provenance: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=_new_id(),
        source=source,
        type=type_,
        value=str(value),
        direction=direction,
        confidence=confidence,
        timestamp=timestamp,
        provenance=provenance,
    )


def _device_evidence(conn: Connection, txn: Any, timestamp: dt.datetime) -> EvidenceItem:
    # Heuristic: the digital_events row closest in time to this transaction,
    # within a 2-hour window, is treated as "the session used for it" — the
    # dataset has no direct transaction<->session link. No match (common for
    # POS/ATM/Branch channels, which don't produce digital_events at all) is
    # Unknown, not fabricated.
    nearby = conn.execute(
        text(
            """
            SELECT ip_address, platform, browser, event_date
            FROM digital_events
            WHERE customer_id = :customer_id
              AND event_date BETWEEN :start AND :end
            ORDER BY abs(extract(epoch FROM (event_date - :ts)))
            LIMIT 1
            """
        ),
        {
            "customer_id": txn.customer_id,
            "start": timestamp - dt.timedelta(hours=2),
            "end": timestamp + dt.timedelta(hours=2),
            "ts": timestamp,
        },
    ).fetchone()

    if nearby is None:
        return _item(
            source="digital_events",
            type_="device_history",
            value="no_digital_session_found",
            direction=EvidenceDirection.NEUTRAL,
            confidence=None,
            timestamp=timestamp,
            provenance="No digital_events row within +/-2h of the transaction for this "
            "customer — channel may not produce digital events (e.g. POS/ATM/Branch), or "
            "no session was captured. Represented as Unknown, not assumed either way.",
        )

    device_id = compute_device_fingerprint(nearby.ip_address, nearby.platform, nearby.browser)
    history: DeviceHistory = get_device_history(
        conn, customer_id=txn.customer_id, device_id=device_id, before=timestamp
    )

    if history.device_id is None:
        return _item(
            source="digital_events",
            type_="device_history",
            value="no_fingerprint_signal",
            direction=EvidenceDirection.NEUTRAL,
            confidence=None,
            timestamp=timestamp,
            provenance=f"Nearby digital_events row at {nearby.event_date} had no ip_address "
            "to fingerprint on (src/evidence/device.py's documented limitation).",
        )

    if history.known_for_this_customer:
        return _item(
            source="devices",
            type_="device_history",
            value=f"known_device(customer_count={history.customer_count})",
            direction=EvidenceDirection.SUPPORTS_LEGITIMATE,
            confidence=0.6,
            timestamp=timestamp,
            provenance=f"Device {history.device_id[:12]}... seen for this customer before "
            f"{timestamp} (first seen {history.first_seen_for_customer}).",
        )

    shared_device = (history.customer_count or 0) > 3
    return _item(
        source="devices",
        type_="device_history",
        value=f"new_device(customer_count={history.customer_count})",
        direction=EvidenceDirection.SUPPORTS_FRAUD,
        confidence=0.75 if shared_device else 0.5,
        timestamp=timestamp,
        provenance=f"Device {history.device_id[:12]}... never seen for this customer before "
        f"{timestamp}"
        + (
            f"; also used by {history.customer_count} distinct customers total (shared/"
            "compromised-device signal)."
            if shared_device
            else "."
        ),
    )


def _country_evidence(
    txn: Any, customer_country: str | None, timestamp: dt.datetime
) -> EvidenceItem:
    if not customer_country:
        return _item(
            "customers",
            "country_deviation",
            "unknown_home_country",
            EvidenceDirection.NEUTRAL,
            None,
            timestamp,
            "customers.country is null for this customer — cannot assess deviation.",
        )
    if txn.transaction_country != customer_country:
        return _item(
            "transactions/customers",
            "country_deviation",
            f"{txn.transaction_country} != {customer_country}",
            EvidenceDirection.SUPPORTS_FRAUD,
            0.6,
            timestamp,
            f"transactions.transaction_country ({txn.transaction_country}) differs from "
            f"customers.country ({customer_country}).",
        )
    return _item(
        "transactions/customers",
        "country_deviation",
        f"{txn.transaction_country} == {customer_country}",
        EvidenceDirection.SUPPORTS_LEGITIMATE,
        0.4,
        timestamp,
        "transaction_country matches the customer's registered country.",
    )


def _amount_evidence(conn: Connection, txn: Any, timestamp: dt.datetime) -> EvidenceItem:
    prior = conn.execute(
        text(
            """
            SELECT amount_usd, amount, currency FROM transactions
            WHERE customer_id = :customer_id AND transaction_date < :ts
            """
        ),
        {"customer_id": txn.customer_id, "ts": timestamp},
    ).fetchall()
    prior_amounts = [
        float(r.amount_usd) if r.amount_usd is not None else float(r.amount) for r in prior
    ]

    if len(prior_amounts) < 2:
        return _item(
            "transactions",
            "amount_deviation",
            "insufficient_history",
            EvidenceDirection.NEUTRAL,
            None,
            timestamp,
            f"Only {len(prior_amounts)} prior transaction(s) for this customer — not enough "
            "history to assess a typical amount.",
        )

    mean = sum(prior_amounts) / len(prior_amounts)
    variance = sum((a - mean) ** 2 for a in prior_amounts) / len(prior_amounts)
    std = variance**0.5
    current = float(txn.amount_usd) if txn.amount_usd is not None else float(txn.amount)
    denom = max(std, mean * 0.01, 1.0)
    z = (current - mean) / denom

    if z > 3:
        return _item(
            "transactions",
            "amount_deviation",
            f"z={z:.2f}",
            EvidenceDirection.SUPPORTS_FRAUD,
            min(0.9, 0.3 + 0.1 * abs(z)),
            timestamp,
            f"Amount {current:.2f} USD is {z:.1f} standard deviations above this customer's "
            f"prior mean ({mean:.2f}, n={len(prior_amounts)}).",
        )
    if abs(z) <= 1:
        return _item(
            "transactions",
            "amount_deviation",
            f"z={z:.2f}",
            EvidenceDirection.SUPPORTS_LEGITIMATE,
            0.4,
            timestamp,
            f"Amount {current:.2f} USD is within 1 std of this customer's prior mean "
            f"({mean:.2f}, n={len(prior_amounts)}).",
        )
    return _item(
        "transactions",
        "amount_deviation",
        f"z={z:.2f}",
        EvidenceDirection.NEUTRAL,
        0.2,
        timestamp,
        f"Amount {current:.2f} USD is {z:.1f} std from this customer's prior mean "
        f"({mean:.2f}, n={len(prior_amounts)}) — not extreme enough to be conclusive.",
    )


def _auth_evidence(txn: Any, timestamp: dt.datetime) -> EvidenceItem:
    response_ok = (txn.response_code or "0") in ("0", "00")
    failed = txn.transaction_status == "Declined" or not response_ok
    if failed:
        return _item(
            "transactions",
            "auth_result",
            f"status={txn.transaction_status}, response_code={txn.response_code}",
            EvidenceDirection.SUPPORTS_FRAUD,
            0.7,
            timestamp,
            "Transaction was declined or returned a non-success response code.",
        )
    return _item(
        "transactions",
        "auth_result",
        f"status={txn.transaction_status}, response_code={txn.response_code}",
        EvidenceDirection.SUPPORTS_LEGITIMATE,
        0.3,
        timestamp,
        "Transaction authenticated/authorized successfully.",
    )


def _complaint_evidence(conn: Connection, txn: Any, timestamp: dt.datetime) -> EvidenceItem:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM complaints WHERE customer_id = :customer_id "
            "AND creation_date < :ts"
        ),
        {"customer_id": txn.customer_id, "ts": timestamp},
    ).scalar_one()
    if count > 0:
        return _item(
            "complaints",
            "historical_dispute_rate",
            f"prior_complaints={count}",
            EvidenceDirection.SUPPORTS_FRAUD,
            0.3,
            timestamp,
            f"{count} complaint(s) on record for this customer prior to this transaction.",
        )
    return _item(
        "complaints",
        "historical_dispute_rate",
        "prior_complaints=0",
        EvidenceDirection.NEUTRAL,
        0.1,
        timestamp,
        "No prior complaints on record for this customer.",
    )


def _velocity_evidence(conn: Connection, txn: Any, timestamp: dt.datetime) -> EvidenceItem:
    count: int = conn.execute(
        text(
            """
            SELECT count(*) FROM transactions
            WHERE customer_id = :customer_id
              AND transaction_date < :ts
              AND transaction_date >= :window_start
            """
        ),
        {
            "customer_id": txn.customer_id,
            "ts": timestamp,
            "window_start": timestamp - dt.timedelta(hours=24),
        },
    ).scalar_one()
    if count >= 3:
        return _item(
            "transactions",
            "velocity",
            f"txn_count_24h={count}",
            EvidenceDirection.SUPPORTS_FRAUD,
            0.5,
            timestamp,
            f"{count} other transactions by this customer in the prior 24 hours.",
        )
    return _item(
        "transactions",
        "velocity",
        f"txn_count_24h={count}",
        EvidenceDirection.NEUTRAL,
        0.1,
        timestamp,
        f"{count} other transaction(s) by this customer in the prior 24 hours — unremarkable.",
    )


def _detect_contradictions(items: list[EvidenceItem]) -> list[tuple[str, str]]:
    """Any two non-neutral evidence items whose directions disagree, both at
    or above CONTRADICTION_CONFIDENCE_THRESHOLD, are a contradiction — a
    blunt, explicit, testable heuristic (docs/implementation-roadmap.md
    Phase 5's own documented risk: easy to over/under-trigger; validate
    against evaluation/golden_cases/conflicting_evidence.json before
    trusting this in a real decision path — no such wiring exists yet)."""
    contradictions: list[tuple[str, str]] = []
    strong = [
        i
        for i in items
        if i.direction != EvidenceDirection.NEUTRAL
        and i.confidence is not None
        and i.confidence >= CONTRADICTION_CONFIDENCE_THRESHOLD
    ]
    for i, a in enumerate(strong):
        for b in strong[i + 1 :]:
            if a.direction != b.direction:
                contradictions.append((a.evidence_id, b.evidence_id))
    return contradictions


def build_evidence_graph(engine: Engine, transaction_id: str) -> EvidenceGraph:
    with engine.connect() as conn:
        txn = conn.execute(
            text(
                """
                SELECT transaction_id, transaction_date, customer_id, amount, amount_usd,
                       currency, transaction_country, transaction_status, response_code
                FROM transactions WHERE transaction_id = :transaction_id
                """
            ),
            {"transaction_id": transaction_id},
        ).fetchone()
        if txn is None:
            raise ValueError(f"transaction_id {transaction_id!r} not found")

        customer = conn.execute(
            text("SELECT country FROM customers WHERE customer_id = :customer_id"),
            {"customer_id": txn.customer_id},
        ).fetchone()
        customer_country = customer.country if customer else None

        timestamp = txn.transaction_date
        items = [
            _device_evidence(conn, txn, timestamp),
            _country_evidence(txn, customer_country, timestamp),
            _amount_evidence(conn, txn, timestamp),
            _auth_evidence(txn, timestamp),
            _complaint_evidence(conn, txn, timestamp),
            _velocity_evidence(conn, txn, timestamp),
        ]
        contradictions = _detect_contradictions(items)

        return EvidenceGraph(
            case_id=_new_case_id(),
            customer_id=txn.customer_id,
            transaction_id=txn.transaction_id,
            created_at=dt.datetime.now(dt.UTC),
            items=items,
            contradictions=contradictions,
        )
