from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            PROJECT_ROOT / ".env",
            GATEWAY_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Clinical Memory System Gateway"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = Field(
        ...,
        description="SQLAlchemy PostgreSQL database URL.",
    )

    jwt_secret_key: SecretStr = Field(
        ...,
        description="Secret used for signing JWTs.",
    )
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_allowed_origins: str = ""
    cors_allow_credentials: bool = False
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    rate_limit_auth_requests_per_minute: int = 20
    max_upload_size_bytes: int = 10 * 1024 * 1024

    clinical_pipeline_persistence: bool = True

    step1_ai_mode: str = "production"
    step1_ai_provider: str = "configured-provider"
    step1_ai_api_key: SecretStr | None = None
    step1_ai_endpoint: str | None = None
    step2_nlp_mode: str = "production"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-1.5-flash"
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_endpoint: str | None = None
    bioclinicalbert_model_name: str = "emilyalsentzer/Bio_ClinicalBERT"
    bioclinicalbert_model_path: str | None = None
    step4_llm_mode: str = "gemini"
    step4_llm_provider: str = "gemini"
    step4_llm_api_key: SecretStr | None = None
    step4_llm_endpoint: str | None = None
    step4_llm_model: str = "configured-model"
    step4_llm_timeout_seconds: float = 30.0
    step4_llm_max_retries: int = 2

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must point to a PostgreSQL database.")

        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: SecretStr) -> SecretStr:
        secret_value = value.get_secret_value()

        if len(secret_value) < 16:
            raise ValueError("JWT_SECRET_KEY must be at least 16 characters.")

        if secret_value in {
            "CHANGE_THIS_IN_PRODUCTION",
            "replace-me",
            "replace-with-a-secure-secret",
            "replace-with-a-secure-secret-at-least-16-chars",
        }:
            raise ValueError("JWT_SECRET_KEY must not use an unsafe placeholder.")

        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if value not in allowed:
            raise ValueError("JWT_ALGORITHM must be a supported HMAC algorithm.")
        return value

    @field_validator("access_token_expire_minutes", "refresh_token_expire_days")
    @classmethod
    def validate_token_expiration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Token expiration must be positive.")
        return value

    @field_validator(
        "rate_limit_requests_per_minute",
        "rate_limit_auth_requests_per_minute",
        "max_upload_size_bytes",
    )
    @classmethod
    def validate_security_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Security limits must be positive.")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed.")
        return ",".join(origins)


settings = Settings()
