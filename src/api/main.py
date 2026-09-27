"""FastAPI application factory.

Phase 1: health check, correlation-ID propagation, structured error responses.
Phase 10 adds the domain endpoints (`docs/api-contracts.md` § 1, `src/api/cases.py`)
and the server-rendered UI (`src/api/ui.py`) on top — see those modules for detail.
"""

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
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    from src.api.cases import router as cases_router
    from src.api.ui import router as ui_router

    app.include_router(cases_router)
    app.include_router(ui_router)
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    return app


app = create_app()
