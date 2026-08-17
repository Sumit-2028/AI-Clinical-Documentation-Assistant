import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger(__name__)

_SENSITIVE_DETAIL_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "authorization",
    "content",
    "document",
    "medical_text",
    "text_input",
}


def _safe_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Return locations/messages without echoing submitted medical content."""

    safe: list[dict[str, Any]] = []
    for error in exc.errors():
        safe.append(
            {
                "type": error.get("type", "validation_error"),
                "loc": list(error.get("loc", ())),
                "msg": error.get("msg", "Request validation failed."),
            }
        )
    return safe


def _safe_path(path: str) -> str:
    from .logging import redact_request_path

    return redact_request_path(path)


def _safe_details(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.casefold() in _SENSITIVE_DETAIL_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(item_key): _safe_details(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_details(item) for item in value]
    if isinstance(value, str) and len(value) > 256:
        return value[:256] + "…"
    return value


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "application_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class DatabaseUnavailableError(AppError):
    def __init__(self, message: str = "Database is unavailable.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="database_unavailable",
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(
        request: Request,
        exc: AppError,
    ) -> JSONResponse:
        logger.warning(
            "Application error",
            extra={
                "path": _safe_path(request.url.path),
                "status_code": exc.status_code,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": _safe_details(exc.details),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "Request validation error",
            extra={
                "path": _safe_path(request.url.path),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed.",
                    "details": {"errors": _safe_validation_errors(exc)},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.error(
            "Database error",
            extra={
                "path": _safe_path(request.url.path),
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                "error_type": type(exc).__name__,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "database_error",
                    "message": "Database operation failed.",
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            "Unhandled error",
            extra={
                "path": _safe_path(request.url.path),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "error_type": type(exc).__name__,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "Internal server error.",
                    "details": {},
                }
            },
        )
