"""Explicit Step 4 -> Step 3 memory handoff adapters."""

import json
from typing import Protocol
from urllib.request import Request, urlopen

from contracts.schemas import MemorySource, MemoryWriteRequest


class MemoryWriteClient(Protocol):
    def submit(self, payload: MemoryWriteRequest): ...


class DeferredMemoryWriteClient:
    """No-op development client: the caller receives the payload for POSTing."""

    def submit(self, payload: MemoryWriteRequest):
        return None


class HttpMemoryWriteClient:
    """Production handoff adapter for POST /api/v1/step3/memory/events."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 10.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def submit(self, payload: MemoryWriteRequest):
        request = Request(
            self.endpoint,
            data=json.dumps(payload.model_dump(mode="json")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read()
        return json.loads(body.decode("utf-8")) if body else None


def build_memory_write_payload(request) -> MemoryWriteRequest:
    return MemoryWriteRequest(
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        source=MemorySource.PHYSICIAN_APPROVED_CONSULTATION,
        clinical_events=list(request.current_consultation_events),
    )


__all__ = [
    "DeferredMemoryWriteClient",
    "HttpMemoryWriteClient",
    "MemoryWriteClient",
    "build_memory_write_payload",
]
