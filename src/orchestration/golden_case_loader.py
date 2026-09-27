"""Loads evaluation/golden_cases/*.json into CaseInput (case.py) — fully
offline, no database, matching those fixtures' own purpose (fast, versioned,
hand-authored scenarios; see evaluation/golden_cases/README.md).

Golden-case evidence entries (type/direction/confidence/source) are
converted to real `EvidenceItem`s, then run through the same
`detect_contradictions` function the live Evidence Engine uses
(src/evidence/graph.py) — rather than trusting each fixture's own
`contradictory_evidence` prose description, which has no fixed shape a
program can consume. This also means a golden case's *expected* behavior is
cross-checked against what the shared detection logic actually finds, not
hand-simulated per fixture.
"""

import datetime as dt
import json
from pathlib import Path

from src.evidence.graph import EvidenceDirection, EvidenceItem, detect_contradictions
from src.orchestration.case import CaseInput

GOLDEN_CASES_DIR = Path(__file__).parent.parent.parent / "evaluation" / "golden_cases"


def load_golden_case(path: Path) -> CaseInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.UTC)

    items = [
        EvidenceItem(
            evidence_id=f"{raw['case_id']}-evidence-{i}",
            source=e["source"],
            type=e["type"],
            value=e["source"],
            direction=EvidenceDirection(e["direction"]),
            confidence=e["confidence"],
            timestamp=now,
            provenance=e["source"],
        )
        for i, e in enumerate(raw.get("evidence", []))
    ]

    facts = raw.get("available_facts", {})

    return CaseInput(
        case_id=raw["case_id"],
        customer_id=facts.get("customer_id", "UNKNOWN"),
        transaction_id=facts.get("transaction_id"),
        customer_message=raw["synthetic_input"]["customer_message"],
        evidence_items=items,
        contradictions=detect_contradictions(items),
        # Deliberately NOT derived from raw["expected_human_involvement"] — that field is the
        # golden case's expected *answer*, and using it here would make run_golden_cases.py
        # circular (grading the orchestrator against a signal built from the grade itself).
        # The only escalation signal Phase 6 can legitimately compute offline is contradictory
        # evidence — Phase 7's Policy Engine (src/policies/) now independently classifies
        # action-risk from `transaction_type`/`amount_usd`/`requested_action` below, which is
        # what actually closes the high_value_transfer gap Phase 6 left honestly open.
        escalation_required=bool(detect_contradictions(items)),
        candidate_questions=_derive_candidate_questions(raw),
        transaction_type=facts.get("transaction_type"),
        amount_usd=_usd_amount(facts, "amount", "currency"),
        requested_action=facts.get("requested_action"),
        requested_amount_usd=_usd_amount(facts, "requested_amount", "requested_currency"),
    )


def _usd_amount(facts: dict, amount_key: str, currency_key: str) -> float | None:
    # No exchange-rate data is loaded in an offline golden-case fixture
    # context (docs/project-status.md § Phase 4 detail: conversion needs
    # daily_exchange_rates) — only fixtures already denominated in USD get a
    # numeric amount here; anything else stays honestly `None` rather than a
    # guessed conversion.
    amount = facts.get(amount_key)
    currency = facts.get(currency_key)
    if amount is None or (currency and currency != "USD"):
        return None
    return float(amount)


def _derive_candidate_questions(raw: dict) -> list[str]:
    # Golden cases don't carry pre-written candidate questions (that's an
    # LLM-generation concern, docs/architecture.md § 8) — a single generic,
    # clearly-labeled-synthetic candidate is enough to exercise the
    # Next-Best-Question gate deterministically in mock mode.
    if raw.get("missing_information"):
        return ["¿Podrías confirmar tu ubicación actual?"]
    return []


def load_all_golden_cases() -> list[CaseInput]:
    return [load_golden_case(p) for p in sorted(GOLDEN_CASES_DIR.glob("*.json"))]
