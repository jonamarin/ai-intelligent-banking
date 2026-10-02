"""Prometheus-format metrics (`docs/observability.md` § 1).

Real counters/histograms incremented at real instrumentation points (see
`src/monitoring/README.md` for the full list — never a metric that's
declared but left unfed). `GET /metrics` (`src/api/main.py`) exposes them
in the standard Prometheus text exposition format; `infrastructure/
prometheus/prometheus.yml` scrapes it when the optional `monitoring`
docker-compose profile is running (`docs/project-status.md` § Phase 13
detail).

System/LLM/security/tool metrics are plain running counters, reset on
process restart — the normal Prometheus convention (rate() over a counter,
not the raw value, is what a real dashboard/alert would use). Business
metrics (`BusinessMetricsCollector`) are different on purpose: derived
*state* (today's automation rate, today's pending-review count) computed
fresh from the database on every scrape, not an in-process running total
that would silently reset and misrepresent history across a restart.
"""

import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import text
from sqlalchemy.engine import Engine

REGISTRY = CollectorRegistry()

# --- system (docs/observability.md § 1 "Metrics — system") ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests handled",
    ["method", "path", "status"],
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    registry=REGISTRY,
)
DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query latency, measured via a SQLAlchemy engine event hook "
    "(src/monitoring/instrumentation.py) -- every query on an instrumented "
    "engine, not a hand-picked sample.",
    registry=REGISTRY,
)

# --- LLM / AI agent (docs/observability.md § 1 "Metrics — LLM") ---
LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "LLM client calls, by pipeline stage and outcome",
    ["stage", "outcome"],  # outcome: success | degraded
    registry=REGISTRY,
)
LLM_CALL_DURATION_SECONDS = Histogram(
    "llm_call_duration_seconds",
    "LLM client call latency (including retries), by pipeline stage",
    ["stage"],
    registry=REGISTRY,
)
CASES_LLM_DEGRADED_TOTAL = Counter(
    "cases_llm_degraded_total",
    "Cases that fell back to the deterministic LLM-unavailable path "
    "(docs/demo-script.md Scenario E)",
    registry=REGISTRY,
)

# --- ML (docs/observability.md § 1 "Metrics — ML") ---
FRAUD_MODEL_SCORE = Histogram(
    "fraud_model_score",
    "The trained fraud model's score for a live case (src/ml/score.py), "
    "observed whenever one was available -- distribution, not a per-case "
    "label; docs/decision-policy.md § 5's risk bands applied the same score "
    "to each case's authorization outcome at the time it ran.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)
CASES_MODEL_DEGRADED_TOTAL = Counter(
    "cases_model_degraded_total",
    "Cases where the fraud model's score was expected but unavailable "
    "(the artifact hasn't been trained yet, or the transaction wasn't in "
    "the cached feature sample) -- docs/demo-script.md Scenario F.",
    registry=REGISTRY,
)

# --- security (docs/observability.md § 1 "unsafe-action rate (should "
# --- always be 0; alert if not)") ---
INJECTION_ATTEMPTS_DETECTED_TOTAL = Counter(
    "injection_attempts_detected_total",
    "Prompt-injection attempts detected and refused (docs/guardrails.md § 4)",
    registry=REGISTRY,
)
UNSAFE_ACTIONS_TOTAL = Counter(
    "unsafe_actions_total",
    "Account-affecting actions authorized without human approval for an "
    "injection attempt or an unresolved contradiction. Must always be 0 -- "
    "tests/security/test_red_team.py proves this offline on every commit; "
    "this counter is the same invariant, watched live "
    "(infrastructure/prometheus/alerts.yml).",
    registry=REGISTRY,
)

# --- tools / policy (docs/observability.md § 1 business/system overlap) ---
TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total",
    "Tool proposals evaluated by the authorization chain",
    ["tool_name", "authorized", "requires_human_approval"],
    registry=REGISTRY,
)
DUPLICATE_ACTIONS_DETECTED_TOTAL = Counter(
    "duplicate_actions_detected_total",
    "Idempotency-key collisions (docs/demo-script.md Scenario J)",
    registry=REGISTRY,
)


@contextmanager
def time_histogram(histogram: Histogram, /, **labels: str) -> Iterator[None]:
    """`with time_histogram(LLM_CALL_DURATION_SECONDS, stage="extract_intent"): ...`
    -- observes wall-clock duration into the histogram (labeled, if any
    labels are given) regardless of whether the block raises."""
    start = time.perf_counter()
    try:
        yield
    finally:
        target = histogram.labels(**labels) if labels else histogram
        target.observe(time.perf_counter() - start)


class BusinessMetricsCollector:
    """Registered once, in `src/api/main.py`, against the real engine
    (docs/observability.md § 1 "Metrics — business"). Queries `fraud_cases`
    fresh on every `/metrics` scrape rather than duplicating
    `evaluation/`'s offline evaluation logic -- this is a live operational
    view, not a substitute for `docs/evaluation-plan.md`'s evaluation.
    Degrades to emitting nothing (not raising) if the database is
    unreachable, so one collector's failure never breaks the whole scrape
    (docs/architecture.md § 10).

    **A real, non-obvious finding from testing this** (not merely
    anticipated): `Settings.db_connect_timeout_seconds` bounds the TCP
    connect step, but not DNS resolution ahead of it -- on this development
    machine, resolving the `.env` default's `db` hostname (correct only
    *inside* docker-compose's network, `.env.example`'s own comment) from
    the bare host took **~60 seconds** the first time in a session (Windows'
    resolver retrying suffixed forms before giving up), not the ~3 seconds
    a plain DNS failure normally takes once cached. A collector that only
    trusted `connect_timeout` would have let one `/metrics` scrape hang far
    past Prometheus's own default 10s `scrape_timeout` -- caught by the
    test suite genuinely slowing down (tests/unit/test_metrics.py), not by
    inspection. Fixed with an explicit wall-clock bound around the whole
    query, independent of what's actually slow underneath it."""

    _TIMEOUT_SECONDS = 3.0

    def __init__(self, engine_factory: Callable[[], Engine]) -> None:
        self._engine_factory = engine_factory

    def collect(self) -> Iterable[GaugeMetricFamily]:
        rates = self._query_with_timeout()
        if rates is None:
            return
        total, automated, pending_review = rates

        total_family = GaugeMetricFamily(
            "business_fraud_cases_total", "Total fraud_cases rows currently in the database"
        )
        total_family.add_metric([], total)
        yield total_family

        automation_family = GaugeMetricFamily(
            "business_automation_rate",
            "Share of fraud_cases resolved with no human review required",
        )
        automation_family.add_metric([], automated / total)
        yield automation_family

        escalation_family = GaugeMetricFamily(
            "business_human_escalation_rate",
            "Share of fraud_cases currently pending human review",
        )
        escalation_family.add_metric([], pending_review / total)
        yield escalation_family

    def _query_with_timeout(self) -> tuple[float, float, float] | None:
        """Runs `_query` on a worker thread with a hard wall-clock bound —
        see the class docstring for why `connect_timeout` alone isn't
        enough. Deliberately *not* `with ThreadPoolExecutor(...) as pool:`
        — that context manager's own `__exit__` calls `shutdown(wait=True)`
        unconditionally, which would block right here for however long the
        hung thread actually takes (the exact ~60s stall this method
        exists to avoid), even after `future.result(timeout=...)` has
        already given up. `shutdown(wait=False)` lets this call return
        immediately; the worker thread is abandoned, not killed (Python has
        no safe way to kill a thread) — it finishes or raises on its own
        time and is garbage collected without this call ever waiting on
        it."""
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._query)
        try:
            return future.result(timeout=self._TIMEOUT_SECONDS)
        except Exception:
            # Covers both a genuine failure (DB unreachable, query error)
            # and the timeout itself -- either way, "nothing to report" is
            # the correct degrade (docs/architecture.md § 10).
            return None
        finally:
            pool.shutdown(wait=False)

    def _query(self) -> tuple[float, float, float] | None:
        engine = self._engine_factory()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT count(*) FROM fraud_cases")).scalar() or 0
            if not total:
                return None
            automated = (
                conn.execute(
                    text(
                        "SELECT count(*) FROM fraud_cases "
                        "WHERE human_review_status = 'not_required'"
                    )
                ).scalar()
                or 0
            )
            pending_review = (
                conn.execute(
                    text("SELECT count(*) FROM fraud_cases WHERE human_review_status = 'pending'")
                ).scalar()
                or 0
            )
        return float(total), float(automated), float(pending_review)


_business_metrics_registered = False


def register_business_metrics(engine_factory: Callable[[], Engine]) -> None:
    """Explicitly idempotent per process -- `src/api/main.py`'s
    `create_app()` is a factory called once per app instance (once per test
    building its own app, in `tests/unit/test_api_cases.py`), so this can
    be called many times in one process.

    **A real bug found and fixed while verifying this phase, not merely
    anticipated**: the original version relied on
    `CollectorRegistry.register()` raising `ValueError` on a duplicate
    name, with callers expected to catch it. That never actually
    triggered -- `prometheus_client` only detects a name collision for
    collectors that implement `describe()` (this one didn't), so every
    `create_app()` call silently registered a *new*
    `BusinessMetricsCollector` instance rather than being rejected. Each
    one independently queries the database on every `/metrics` scrape
    (`docs/architecture.md` § 10's cost concern compounds per duplicate);
    on this development machine, with `tests/unit/test_api_cases.py`'s 18
    tests each building an app, that meant up to 18 sequential ~2.7s DNS
    failures serialized into one scrape -- exactly the wall-clock cost
    `tests/unit/test_metrics.py` caught as a genuine, reproducible slowdown
    (not the DNS-latency issue this collector's own timeout already
    handles; a different bug in front of it). Fixed with an explicit
    module-level guard instead of trusting the library to reject the
    duplicate."""
    global _business_metrics_registered
    if _business_metrics_registered:
        return
    REGISTRY.register(BusinessMetricsCollector(engine_factory))
    _business_metrics_registered = True


def render_latest() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
