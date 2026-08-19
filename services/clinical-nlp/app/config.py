"""Step 2 Clinical NLP configuration via Pydantic BaseSettings."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


CLINICAL_NLP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Step2Settings(BaseSettings):
    """Configuration for Step 2 Clinical NLP service."""

    model_config = SettingsConfigDict(
        env_file=(
            PROJECT_ROOT / ".env",
            CLINICAL_NLP_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Step 2 mode - production is default, no silent mock fallbacks
    step2_nlp_mode: str = Field(
        default="production",
        description="Step 2 NLP mode. Must be 'production'.",
    )

    # Gemini API configuration
    gemini_api_key: str = Field(
        default="AQ.Ab8RN6JrGDyqRZYz6LfZCZ57K_djg3PQ4j0G_YbsxJKAdGLWTA",
        description="Gemini API key for clinical contextualization. Required for production mode.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model name for contextualization.",
    )
    gemini_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Gemini API base URL.",
    )
    gemini_endpoint: str | None = Field(
        default=None,
        description="Optional full endpoint override.",
    )

    # Shared AI transport settings
    ai_timeout_seconds: float = Field(
        default=15.0,
        description="HTTP timeout for AI provider calls.",
    )
    ai_max_retries: int = Field(
        default=2,
        description="Maximum retries for AI provider calls.",
    )

    @field_validator("step2_nlp_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value.lower() != "production":
            raise ValueError("STEP2_NLP_MODE must be 'production'. Mock mode is not supported in production paths.")
        return value.lower()

    @field_validator("gemini_api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("GEMINI_API_KEY is required for production mode.")
        return value.strip()


# Global settings instance
settings = Step2Settings()