import os
from pathlib import Path

# Use the repository's configured database when a local .env is present. The
# fallback keeps isolated gateway tests importable in CI without redirecting
# repository-wide PostgreSQL integration tests to an unavailable database.
if "DATABASE_URL" not in os.environ and not (
    Path(__file__).resolve().parents[3] / ".env"
).exists():
    os.environ["DATABASE_URL"] = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_memory_test"
    )
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-change-me")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")
