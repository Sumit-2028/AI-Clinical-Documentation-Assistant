"""In-process composition of the complete clinical documentation pipeline.

The production deployment can replace each service with a network client, but
the gateway owns the composition boundary so local development and CI exercise
the same contracts without requiring external AI providers or service
processes.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.clinical_nlp.app.service import ClinicalNLPService
from services.doc_generation.app.service import DocumentService
from services.input_processing.app.service import InputProcessingService
from services.memory_engine.app.service import MemoryEngineService


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


def build_integrated_services() -> IntegratedBackendServices:
    """Build one deterministic, shared service graph for a gateway instance."""

    step3 = MemoryEngineService()
    step4 = DocumentService(
        memory_write_client=InProcessMemoryWriteClient(step3),
    )
    return IntegratedBackendServices(
        step1=InputProcessingService(),
        step2=ClinicalNLPService(),
        step3=step3,
        step4=step4,
    )


__all__ = [
    "InProcessMemoryWriteClient",
    "IntegratedBackendServices",
    "build_integrated_services",
]
