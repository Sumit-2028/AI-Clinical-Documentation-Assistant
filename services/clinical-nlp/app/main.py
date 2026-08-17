from fastapi import FastAPI

from .router import router
from .service import ClinicalNLPService


def create_app(service: ClinicalNLPService | None = None) -> FastAPI:
    app = FastAPI(
        title="Clinical Memory System - Step 2 Clinical NLP",
        version="1.0.0",
    )
    app.state.clinical_nlp_service = service or ClinicalNLPService()
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "clinical-nlp"}

    return app


app = create_app()
