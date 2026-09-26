"""Structured error responses (docs/api-contracts.md § 2).

Internal stack traces are never exposed to the client (prompt.md § 44) — the
generic-exception handler logs the full exception server-side and returns only a
correlation ID the client can hand back for support/debugging.
"""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that should produce a specific, safe client response."""

    def __init__(self, message: str, *, code: str = "app_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found", status_code=404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(message, code="unauthorized", status_code=403)


def _error_body(code: str, message: str, correlation_id: str | None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "correlation_id": correlation_id}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, correlation_id),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Request validation failed", correlation_id),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.exception(
        "Unhandled exception", extra={"correlation_id": correlation_id}
    )
    return JSONResponse(
        status_code=500,
        content=_error_body(
            "internal_error",
            "An internal error occurred. Reference the correlation_id for support.",
            correlation_id,
        ),
    )
