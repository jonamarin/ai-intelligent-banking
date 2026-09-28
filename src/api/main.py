"""FastAPI application factory.

Phase 1: health check, correlation-ID propagation, structured error responses.
Phase 10 adds the domain endpoints (`docs/api-contracts.md` § 1, `src/api/cases.py`)
and the server-rendered UI (`src/api/ui.py`) on top — see those modules for detail.
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from src.api.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.monitoring import tracing
from src.monitoring.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    register_business_metrics,
    render_latest,
)

CORRELATION_ID_HEADER = "X-Correlation-ID"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="AI Fraud & Dispute Investigator", version="0.1.0")

    # Starlette's add_exception_handler is typed generically over `Exception`;
    # mypy can't narrow it to our specific handler signatures even though
    # FastAPI's own runtime dispatch does this correctly. Known ecosystem gap.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        # docs/observability.md § 1 "Traces": one span per request, seeded
        # with the correlation ID so it and every audit event a case
        # produces underneath it (src/policies/gateway.py) share one
        # identifier -- fixes the Phase 10-documented gap where
        # AuditEvent.correlation_id was always written as None.
        tracing.seed_trace_id(correlation_id)
        path = request.url.path
        start = time.perf_counter()
        with tracing.span("http.request", method=request.method, path=path):
            response = await call_next(request)
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(
            time.perf_counter() - start
        )
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method, path=path, status=str(response.status_code)
        ).inc()
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @app.get("/metrics")
    async def metrics() -> Response:
        """docs/observability.md § 1/§ 4 -- Prometheus text-exposition
        format, scraped by `infrastructure/prometheus/prometheus.yml` when
        the optional `monitoring` docker-compose profile is running
        (`docs/project-status.md` § Phase 13 detail). No auth: this is a
        local-dev-only endpoint on a prototype with no production
        deployment (CLAUDE.md § 7) -- exposing it publicly as-is would be a
        real gap for an actual deployment, noted in docs/security-model.md."""
        body, content_type = render_latest()
        return Response(content=body, media_type=content_type)

    from src.api.cases import router as cases_router
    from src.api.deps import get_db_engine
    from src.api.ui import router as ui_router

    app.include_router(cases_router)
    app.include_router(ui_router)
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # register_business_metrics is itself idempotent per process (see its
    # docstring for a real bug this guarded against) -- safe to call on
    # every create_app(), including the many independent app instances
    # tests/unit/test_api_cases.py's fixtures build.
    register_business_metrics(get_db_engine)

    return app


app = create_app()
