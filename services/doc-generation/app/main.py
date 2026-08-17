from fastapi import FastAPI

from .router import router
from .service import DocumentService


def create_app(service: DocumentService | None = None) -> FastAPI:
    app = FastAPI(
        title="Clinical Memory System - Step 4 Documentation Generation",
        version="1.0.0",
    )
    app.state.document_service = service or DocumentService()
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "doc-generation"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
