"""Tests for src/monitoring/metrics.py — offline, no live Postgres.

`BusinessMetricsCollector` is tested against a real (in-memory SQLite)
engine rather than mocked — it issues real SQL, and the only thing worth
proving is that the SQL and the arithmetic are both correct, and that a
database failure degrades to "no business metrics" rather than a broken
scrape (docs/observability.md § 1 "Metrics — business";
docs/architecture.md § 10).
"""

from collections.abc import Generator

import pytest
from prometheus_client import Histogram
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src.models import Base
from src.monitoring.metrics import (
    REGISTRY,
    BusinessMetricsCollector,
    register_business_metrics,
    render_latest,
    time_histogram,
)


@pytest.fixture
def sqlite_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


def _insert_fraud_case(engine: Engine, case_id: str, human_review_status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO customers "
                "(customer_id, document_number, document_type, first_name, last_name, "
                "date_of_birth, city, state, country, segment, registration_date, "
                "registration_branch_id, customer_status, last_updated, accepts_marketing) "
                "VALUES ('CUST-1', 'DOC-1', 'CC', 'Test', 'Customer', '1990-01-01', "
                "'City', 'State', 'CO', 'mass', '2020-01-01T00:00:00', 'BR-1', "
                "'active', '2020-01-01T00:00:00', 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO fraud_cases (case_id, customer_id, transaction_id, status, "
                "escalation_required, human_review_status, created_at) "
                "VALUES (:case_id, 'CUST-1', NULL, 'open', 0, :status, "
                "'2026-01-01T00:00:00')"
            ),
            {"case_id": case_id, "status": human_review_status},
        )


def test_business_metrics_collector_computes_rates_from_real_rows(sqlite_engine: Engine) -> None:
    _insert_fraud_case(sqlite_engine, "CASE-1", "not_required")
    _insert_fraud_case(sqlite_engine, "CASE-2", "not_required")
    _insert_fraud_case(sqlite_engine, "CASE-3", "pending")
    _insert_fraud_case(sqlite_engine, "CASE-4", "approve")

    collector = BusinessMetricsCollector(lambda: sqlite_engine)
    families = {f.name: f for f in collector.collect()}

    assert families["business_fraud_cases_total"].samples[0].value == 4
    assert families["business_automation_rate"].samples[0].value == pytest.approx(0.5)
    assert families["business_human_escalation_rate"].samples[0].value == pytest.approx(0.25)


def test_business_metrics_collector_emits_nothing_for_an_empty_table(
    sqlite_engine: Engine,
) -> None:
    collector = BusinessMetricsCollector(lambda: sqlite_engine)
    assert list(collector.collect()) == []


def test_business_metrics_collector_degrades_to_nothing_on_a_db_failure() -> None:
    """docs/architecture.md § 10: one dependency's failure must never take
    down an unrelated capability -- a `/metrics` scrape still serves the
    system/LLM/security metrics even if the database is unreachable."""

    def _broken_engine_factory() -> Engine:
        raise ConnectionError("database unreachable")

    collector = BusinessMetricsCollector(_broken_engine_factory)
    assert list(collector.collect()) == []


def test_time_histogram_observes_a_duration() -> None:
    histogram = Histogram("test_only_duration_seconds", "test histogram", registry=None)
    with time_histogram(histogram):
        pass
    assert histogram.collect()[0].samples[0].value == 1  # the _count sample


def test_time_histogram_observes_even_when_the_block_raises() -> None:
    histogram = Histogram("test_only_duration_seconds_2", "test histogram", registry=None)
    with pytest.raises(ValueError), time_histogram(histogram):
        raise ValueError("boom")
    assert histogram.collect()[0].samples[0].value == 1


def test_time_histogram_supports_labels() -> None:
    histogram = Histogram(
        "test_only_labeled_duration_seconds", "test histogram", ["stage"], registry=None
    )
    with time_histogram(histogram, stage="extract_intent"):
        pass
    counted = [
        s for s in histogram.collect()[0].samples if s.name.endswith("_count") and s.value == 1
    ]
    assert counted and counted[0].labels == {"stage": "extract_intent"}


def test_register_business_metrics_is_idempotent_per_process() -> None:
    """Regression test for a real bug found while building this phase:
    `CollectorRegistry.register()` only rejects a duplicate NAME for
    collectors implementing `describe()` -- `BusinessMetricsCollector`
    doesn't, so it silently accepted an unbounded number of registrations,
    one per `src/api/main.py::create_app()` call (once per test building
    its own app in tests/unit/test_api_cases.py). Each duplicate
    independently queried the database on every `/metrics` scrape,
    serializing N x ~3s of DNS-failure latency into one call -- caught as
    tests/unit/test_metrics.py itself taking 50+ real seconds under the
    full suite, not by inspection. `register_business_metrics` now guards
    itself explicitly rather than trusting the library."""
    def _unused_engine_factory() -> Engine:
        raise AssertionError("a truly idempotent second registration never calls this")

    def _count_registered() -> int:
        return sum(
            1 for c in REGISTRY._collector_to_names if isinstance(c, BusinessMetricsCollector)
        )

    register_business_metrics(_unused_engine_factory)  # ensures at least one is registered
    after_first = _count_registered()
    register_business_metrics(_unused_engine_factory)
    after_second = _count_registered()
    assert after_second == after_first, "a second registration must be a no-op, not add another"


def test_render_latest_exposes_registered_counters() -> None:
    body, content_type = render_latest()
    text_body = body.decode()
    assert "text/plain" in content_type
    assert "http_requests_total" in text_body
    assert "llm_calls_total" in text_body
    assert "unsafe_actions_total" in text_body


def test_security_counters_increment_and_are_visible_in_render_latest() -> None:
    """Proves these aren't declared-but-never-touched metrics
    (docs/observability.md § 1's own bar: "unsafe-action rate (should
    always be 0; alert if not)") -- they live in the one shared REGISTRY
    that /metrics renders from, and incrementing them is visible there."""
    from src.monitoring.metrics import UNSAFE_ACTIONS_TOTAL

    before = UNSAFE_ACTIONS_TOTAL._value.get()
    UNSAFE_ACTIONS_TOTAL.inc()
    body, _ = render_latest()
    assert f"unsafe_actions_total {before + 1.0}" in body.decode()
