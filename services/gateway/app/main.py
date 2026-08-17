from fastapi import FastAPI

from .auth.router import router as auth_router


app = FastAPI(
    title="Clinical Memory System Gateway",
    version="1.0.0",
)


app.include_router(
    auth_router,
    prefix="/api/v1",
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "gateway",
    }