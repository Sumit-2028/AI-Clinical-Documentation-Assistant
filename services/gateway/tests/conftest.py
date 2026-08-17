import os


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_memory_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-change-me")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")
