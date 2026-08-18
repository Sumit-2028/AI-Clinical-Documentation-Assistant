"""In-process composition of the complete clinical documentation pipeline.

The production deployment can replace each service with a network client, but
the gateway owns the composition boundary so local development and CI exercise
the same contracts without requiring external AI providers or service
processes.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from services.clinical_nlp.app.service import ClinicalNLPService
from services.clinical_nlp.app.repository import SessionScopedSqlAlchemyClinicalEventRepository
from services.doc_generation.app.repository import (
    SessionScopedSqlAlchemyDocumentRepository as SessionScopedStep4Repository,
)
from services.doc_generation.app.service import DocumentService
from services.input_processing.app.service import InputProcessingService
from services.input_processing.app.audit import SessionScopedSqlAlchemyAuditLogger
from services.input_processing.app.repository import (
    SessionScopedSqlAlchemyDocumentRepository as SessionScopedStep1Repository,
)
from services.memory_engine.app.service import MemoryEngineService
from services.memory_engine.app.stores import SessionScopedSqlAlchemyMemoryStore
from .config import settings
from .database import SessionLocal


class InProcessMemoryWriteClient:
    """Step 4 handoff client that always enters the Step 3 write gate."""

    def __init__(self, memory_service: MemoryEngineService) -> None:
        self.memory_service = memory_service

    def submit(self, payload):
        return self.memory_service.write_events(payload)


@dataclass(frozen=True)
class IntegratedBackendServices:
    step1: InputProcessingService
    step2: ClinicalNLPService
    step3: MemoryEngineService
    step4: DocumentService


def _configure_provider_environment() -> None:
    """Bridge pydantic settings (including values from .env) to adapters."""

    test_runtime = settings.app_env.casefold() == "test" or bool(os.getenv("PYTEST_CURRENT_TEST"))
    gemini_key = (
        settings.gemini_api_key.get_secret_value()
        if settings.gemini_api_key is not None
        else None
    )
    # A common local configuration mistake is copying the API key into the
    # optional endpoint variable. Never use a secret as a URL; fall back to
    # the configured Gemini base URL while preserving the backend-only key.
    gemini_endpoint = settings.gemini_endpoint
    if gemini_endpoint and gemini_key and gemini_endpoint == gemini_key:
        gemini_endpoint = None
    values = {
        "STEP1_AI_MODE": "mock" if test_runtime else settings.step1_ai_mode,
        "STEP1_AI_PROVIDER": settings.step1_ai_provider,
        "STEP1_AI_ENDPOINT": settings.step1_ai_endpoint,
        "STEP2_NLP_MODE": "mock" if test_runtime else settings.step2_nlp_mode,
        "GEMINI_MODEL": settings.gemini_model,
        "GEMINI_API_URL": settings.gemini_api_url,
        "GEMINI_ENDPOINT": gemini_endpoint,
        "BIOCLINICALBERT_MODEL_NAME": settings.bioclinicalbert_model_name,
        "BIOCLINICALBERT_MODEL_PATH": settings.bioclinicalbert_model_path,
        "STEP4_LLM_MODE": "mock" if test_runtime else settings.step4_llm_mode,
        "STEP4_LLM_PROVIDER": settings.step4_llm_provider,
        "STEP4_LLM_ENDPOINT": settings.step4_llm_endpoint,
        "STEP4_LLM_MODEL": settings.step4_llm_model,
        "STEP4_LLM_TIMEOUT_SECONDS": str(settings.step4_llm_timeout_seconds),
        "STEP4_LLM_MAX_RETRIES": str(settings.step4_llm_max_retries),
    }
    secrets = {
        "STEP1_AI_API_KEY": settings.step1_ai_api_key,
        "GEMINI_API_KEY": settings.gemini_api_key,
        "STEP4_LLM_API_KEY": settings.step4_llm_api_key,
    }
    for name, value in values.items():
        if value is not None:
            os.environ[name] = str(value)
    for name, value in secrets.items():
        if value is not None:
            os.environ[name] = value.get_secret_value()


def build_integrated_services(
    *,
    persistent: bool | None = None,
) -> IntegratedBackendServices:
    """Build one deterministic, shared service graph for a gateway instance."""

    if persistent is None:
        _configure_provider_environment()
        configured = os.getenv(
            "CLINICAL_PIPELINE_PERSISTENCE",
            "true" if settings.clinical_pipeline_persistence else "false",
        ).strip().lower()
        persistent = configured not in {"0", "false", "no", "off"}
        # Test clients intentionally override the gateway database dependency
        # with lightweight sessions. Never couple those tests to the process
        # global production session factory.
        if settings.app_env.casefold() == "test" or os.getenv("PYTEST_CURRENT_TEST"):
            persistent = False

    if persistent:
        step1_repository = SessionScopedStep1Repository(SessionLocal)
        step1_audit = SessionScopedSqlAlchemyAuditLogger(SessionLocal)
        step2_repository = SessionScopedSqlAlchemyClinicalEventRepository(SessionLocal)
        memory_store = SessionScopedSqlAlchemyMemoryStore(SessionLocal)
        step4_repository = SessionScopedStep4Repository(SessionLocal)
    else:
        step1_repository = None
        step1_audit = None
        step2_repository = None
        memory_store = None
        step4_repository = None

    step3 = MemoryEngineService(store=memory_store)
    step4 = DocumentService(
        repository=step4_repository,
        memory_write_client=InProcessMemoryWriteClient(step3),
    )
    return IntegratedBackendServices(
        step1=InputProcessingService(
            repository=step1_repository,
            audit_logger=step1_audit,
        ),
        step2=ClinicalNLPService(repository=step2_repository),
        step3=step3,
        step4=step4,
    )


__all__ = [
    "InProcessMemoryWriteClient",
    "IntegratedBackendServices",
    "build_integrated_services",
]
