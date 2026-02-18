"""
Bubby Vision — Global Exception Handlers

Provides consistent, structured error responses for the entire API.
Catches unhandled exceptions, validation errors, and HTTP exceptions
so every error response follows the same JSON schema.
"""

from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

import structlog

log = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with consistent JSON format."""
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors → 422 with field details."""
        request_id = getattr(request.state, "request_id", None)
        errors = []
        for err in exc.errors():
            errors.append({
                "field": " → ".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            })

        log.warning(
            "validation_error",
            path=str(request.url.path),
            errors=errors,
            request_id=request_id,
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "status_code": 422,
                "detail": "Validation error",
                "errors": errors,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catch-all for unhandled exceptions → 500 with safe details."""
        request_id = getattr(request.state, "request_id", None)

        log.error(
            "unhandled_exception",
            path=str(request.url.path),
            method=request.method,
            error=str(exc),
            traceback=traceback.format_exc(),
            request_id=request_id,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
