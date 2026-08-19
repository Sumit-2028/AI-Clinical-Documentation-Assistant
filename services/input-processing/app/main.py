from fastapi import FastAPI

from services.object_storage import ObjectStorage, build_object_storage

from .router import router
from .service import InputProcessingService


def create_app(
    service: InputProcessingService | None = None,
    storage: ObjectStorage | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Clinical Memory System - Step 1 Input Processing",
        version="1.0.0",
    )
    app.state.step1_service = service or InputProcessingService()
    app.state.object_storage = storage or build_object_storage()
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "input-processing"}

    return app


app = create_app()
