import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .auth.router import router as auth_router
from .auth.dependencies import require_pipeline_access
from .config import settings
from .exceptions import register_exception_handlers
from .integration import IntegratedBackendServices, build_integrated_services
from .logging import redact_request_path, setup_logging
from .rate_limit import InMemoryRateLimitMiddleware
from .patients.router import router as patients_router
from services.clinical_nlp.app.router import router as step2_router
from services.doc_generation.app.router import router as step4_router
from services.input_processing.app.router import router as step1_router
from services.memory_engine.app.router import router as step3_router


logger = logging.getLogger(__name__)


def create_app(
    integrated_services: IntegratedBackendServices | None = None,
) -> FastAPI:
    setup_logging()

    services = integrated_services or build_integrated_services()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
    )

    allowed_origins = [
        origin for origin in settings.cors_allowed_origins.split(",") if origin
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        requests_per_minute=settings.rate_limit_requests_per_minute,
        auth_requests_per_minute=settings.rate_limit_auth_requests_per_minute,
    )

    register_exception_handlers(app)

    app.state.step1_service = services.step1
    app.state.clinical_nlp_service = services.step2
    app.state.memory_engine_service = services.step3
    app.state.document_service = services.step4

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        start_time = time.perf_counter()

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["x-request-id"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": redact_request_path(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response

    app.include_router(
        auth_router,
        prefix="/api/v1",
    )
    app.include_router(
        patients_router,
        prefix="/api/v1",
    )

    pipeline_dependencies = [Depends(require_pipeline_access)]
    app.include_router(
        step1_router,
        prefix="/api/v1",
        dependencies=pipeline_dependencies,
    )
    app.include_router(
        step2_router,
        prefix="/api/v1",
        dependencies=pipeline_dependencies,
    )
    app.include_router(
        step3_router,
        prefix="/api/v1",
        dependencies=pipeline_dependencies,
    )
    app.include_router(
        step4_router,
        prefix="/api/v1",
        dependencies=pipeline_dependencies,
    )

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "service": "gateway",
        }

    return app


app = create_app()
