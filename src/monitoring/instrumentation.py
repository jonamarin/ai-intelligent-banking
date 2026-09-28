"""Wires `src/monitoring/metrics.py`/`tracing.py` into real call sites.

Kept separate from `metrics.py`/`tracing.py` themselves so those two stay
framework-agnostic (no SQLAlchemy/FastAPI imports) — this module is the one
place that knows about the actual objects (a SQLAlchemy `Engine`) being
measured.
"""

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.monitoring.metrics import DB_QUERY_DURATION_SECONDS

_INSTRUMENTED_FLAG = "_observability_instrumented"


def instrument_engine(engine: Engine) -> None:
    """Registers `before/after_cursor_execute` hooks (the documented
    SQLAlchemy pattern for query-latency profiling) so every query issued
    through this engine observes its wall-clock duration into
    `DB_QUERY_DURATION_SECONDS` (docs/observability.md § 1 "Metrics —
    system": database latency). Idempotent per engine instance — safe to
    call more than once (e.g. once per test fixture) without double-
    counting, since `src/models/base.get_engine()` is called fresh per
    caller rather than memoized (see that module's own docstring for why)."""
    if getattr(engine, _INSTRUMENTED_FLAG, False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn: Any, *_args: Any, **_kwargs: Any) -> None:
        conn.info["_query_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn: Any, *_args: Any, **_kwargs: Any) -> None:
        start = conn.info.pop("_query_start", None)
        if start is not None:
            DB_QUERY_DURATION_SECONDS.observe(time.perf_counter() - start)

    setattr(engine, _INSTRUMENTED_FLAG, True)
