from fastapi import FastAPI

from .router import router
from .service import MemoryEngineService


def create_app(service: MemoryEngineService | None = None) -> FastAPI:
    app = FastAPI(
        title="Clinical Memory System - Patient Memory Engine",
        version="1.0.0",
    )
    app.state.memory_engine_service = service or MemoryEngineService()
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "memory-engine"}

    return app


app = create_app()
