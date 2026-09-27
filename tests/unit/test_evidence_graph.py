"""Unit tests for the pure-logic parts of the Evidence Engine
(src/evidence/graph.py, src/evidence/device.py) — no database required, per
.claude/rules/testing.md. The DB-coupled evidence rules (_device_evidence,
_amount_evidence, _complaint_evidence, _velocity_evidence) are verified
against the live loaded dataset instead (docs/project-status.md § Phase 5
detail) — an offline unit test would just be re-testing the SQL driver, not
the extraction logic itself.
"""

import datetime as dt
from types import SimpleNamespace

from src.evidence.device import compute_device_fingerprint
from src.evidence.graph import (
    EvidenceItem,
    _auth_evidence,
    _country_evidence,
    detect_contradictions,
)
from src.models.evidence import EvidenceDirection

_TS = dt.datetime(2026, 1, 1, 12, 0)


def test_fingerprint_is_stable_for_the_same_inputs() -> None:
    a = compute_device_fingerprint("1.2.3.4", "iOS", "Safari")
    b = compute_device_fingerprint("1.2.3.4", "iOS", "Safari")
    assert a == b


def test_fingerprint_differs_for_different_ip() -> None:
    a = compute_device_fingerprint("1.2.3.4", "iOS", "Safari")
    b = compute_device_fingerprint("5.6.7.8", "iOS", "Safari")
    assert a != b


def test_fingerprint_is_none_without_ip_address() -> None:
    """Missing ip_address must produce Unknown (None), never a fabricated
    stable ID from platform/browser alone (src/evidence/device.py's
    documented limitation)."""
    assert compute_device_fingerprint(None, "iOS", "Safari") is None
    assert compute_device_fingerprint("", "iOS", "Safari") is None


def test_country_evidence_flags_mismatch_as_supporting_fraud() -> None:
    txn = SimpleNamespace(transaction_country="Argentina")
    item = _country_evidence(txn, "Colombia", _TS)
    assert item.direction == EvidenceDirection.SUPPORTS_FRAUD


def test_country_evidence_match_supports_legitimate() -> None:
    txn = SimpleNamespace(transaction_country="Colombia")
    item = _country_evidence(txn, "Colombia", _TS)
    assert item.direction == EvidenceDirection.SUPPORTS_LEGITIMATE


def test_country_evidence_unknown_home_country_is_neutral_not_guessed() -> None:
    txn = SimpleNamespace(transaction_country="Colombia")
    item = _country_evidence(txn, None, _TS)
    assert item.direction == EvidenceDirection.NEUTRAL
    assert item.confidence is None


def test_auth_evidence_declined_supports_fraud() -> None:
    txn = SimpleNamespace(transaction_status="Declined", response_code="51")
    item = _auth_evidence(txn, _TS)
    assert item.direction == EvidenceDirection.SUPPORTS_FRAUD


def test_auth_evidence_approved_with_success_code_supports_legitimate() -> None:
    """Regression: the dataset's success code is '0', not '00'
    (docs/project-status.md § Phase 4 detail — the same bug class as
    src/ml/features.py's auth_failed)."""
    txn = SimpleNamespace(transaction_status="Approved", response_code="0")
    item = _auth_evidence(txn, _TS)
    assert item.direction == EvidenceDirection.SUPPORTS_LEGITIMATE


def _evidence(direction: EvidenceDirection, confidence: float | None) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"e-{direction}-{confidence}",
        source="test",
        type="test_type",
        value="v",
        direction=direction,
        confidence=confidence,
        timestamp=_TS,
        provenance="test",
    )


def test_contradiction_detected_between_two_conflicting_strong_signals() -> None:
    """The required Phase 5 test (docs/implementation-roadmap.md): a
    known-device signal (supports_legitimate) alongside a country-mismatch
    signal (supports_fraud), both confident, must be flagged as a
    contradiction — not silently resolved by picking one."""
    known_device = _evidence(EvidenceDirection.SUPPORTS_LEGITIMATE, 0.6)
    new_country = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.6)
    contradictions = detect_contradictions([known_device, new_country])
    assert (known_device.evidence_id, new_country.evidence_id) in contradictions


def test_no_contradiction_when_confidence_below_threshold() -> None:
    weak_legit = _evidence(EvidenceDirection.SUPPORTS_LEGITIMATE, 0.1)
    weak_fraud = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.1)
    assert detect_contradictions([weak_legit, weak_fraud]) == []


def test_no_contradiction_when_directions_agree() -> None:
    a = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.6)
    b = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.7)
    assert detect_contradictions([a, b]) == []


def test_neutral_evidence_is_never_flagged_as_contradicting() -> None:
    neutral = _evidence(EvidenceDirection.NEUTRAL, 0.9)
    fraud = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.6)
    assert detect_contradictions([neutral, fraud]) == []


def test_evidence_item_to_dict_shape() -> None:
    item = _evidence(EvidenceDirection.SUPPORTS_FRAUD, 0.5)
    d = item.to_dict()
    assert set(d.keys()) == {
        "evidence_id",
        "source",
        "type",
        "value",
        "direction",
        "confidence",
        "timestamp",
        "provenance",
    }
    assert d["direction"] == "supports_fraud"
