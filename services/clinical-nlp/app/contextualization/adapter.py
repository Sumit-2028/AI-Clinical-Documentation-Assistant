from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from services.ai_adapters import (
    AIProviderError,
    AIProviderResponseError,
    JSONHTTPClient,
    env_float,
    env_int,
)
from typing import Protocol

from .assertion import detect_assertion
from .temporal import extract_temporal_context


@dataclass(frozen=True)
class ContextualizationResult:
    assertion: str
    clinical_status: str
    temporal_context: str
    temporal_date: object | None
    confidence: float


class ContextualizationAdapter(Protocol):
    model_name: str

    def contextualize(self, text: str, entity_text: str) -> ContextualizationResult:
        ...


class MockGeminiContextualizationAdapter:
    """Deterministic contextualizer with explicit mock provenance."""

    model_name = "mock-gemini-contextualizer"

    def contextualize(self, text: str, entity_text: str) -> ContextualizationResult:
        assertion = detect_assertion(text, entity_text)
        temporal = extract_temporal_context(text)
        return ContextualizationResult(
            assertion=assertion.assertion,
            clinical_status=(
                "inactive"
                if temporal.temporal_context == "past" and assertion.assertion == "affirmed"
                else assertion.clinical_status
            ),
            temporal_context=temporal.temporal_context,
            temporal_date=temporal.temporal_date,
            confidence=min(assertion.confidence, temporal.confidence, 0.84),
        )


class ProductionGeminiContextualizationAdapter:
    model_name = "gemini-contextualizer"

    def __init__(
        self,
        model=None,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        http_client: JSONHTTPClient | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.model_name = model_name or self.model_name
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip(
            "/"
        )
        self.endpoint = endpoint
        self.http_client = http_client or JSONHTTPClient(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def contextualize(self, text: str, entity_text: str) -> ContextualizationResult:
        if self.model is not None:
            return self.model(text, entity_text)
        if not self.api_key:
            raise NLPProviderUnavailableError(
                "Gemini contextualization requires GEMINI_API_KEY or an injected model."
            )

        endpoint = self.endpoint or (
            f"{self.base_url}/models/{self.model_name}:generateContent"
        )
        response = self.http_client.post_json(
            endpoint,
            {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": _contextualization_prompt(text, entity_text)}],
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0,
                },
            },
            provider=self.model_name,
            operation="clinical_contextualization",
            headers={"x-goog-api-key": self.api_key},
        )
        content = _gemini_text(response)
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AIProviderResponseError(
                f"Gemini model '{self.model_name}' returned invalid contextualization JSON."
            ) from exc
        return _contextualization_result(parsed, self.model_name)


class NLPProviderUnavailableError(AIProviderError):
    """Raised when configured clinical NLP provider execution is unavailable."""


def _contextualization_prompt(text: str, entity_text: str) -> str:
    return (
        "Return only JSON with keys assertion, clinical_status, "
        "temporal_context, temporal_date, confidence. "
        "Use temporal_date as YYYY-MM-DD or null and confidence between 0 and 1. "
        f"Entity: {entity_text}\nClinical text: {text}"
    )


def _gemini_text(response: dict[str, Any] | Any) -> str:
    candidates = response.get("candidates") if isinstance(response, dict) else None
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        if parts and isinstance(parts[0], dict) and isinstance(parts[0].get("text"), str):
            return parts[0]["text"]
    direct = response.get("text") if isinstance(response, dict) else None
    if isinstance(direct, str):
        return direct
    raise AIProviderResponseError(
        "Gemini response did not contain a text candidate."
    )


def _contextualization_result(value: Any, provider: str) -> ContextualizationResult:
    if not isinstance(value, dict):
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned a non-object contextualization."
        )
    required = ("assertion", "clinical_status", "temporal_context", "confidence")
    if any(not isinstance(value.get(key), str) for key in required[:3]):
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned incomplete contextualization."
        )
    try:
        confidence = float(value["confidence"])
    except (TypeError, ValueError) as exc:
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned invalid contextualization confidence."
        ) from exc
    if not 0.0 <= confidence <= 1.0:
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned out-of-range contextualization confidence."
        )
    temporal_date = value.get("temporal_date")
    if temporal_date is not None:
        try:
            temporal_date = date.fromisoformat(str(temporal_date))
        except ValueError as exc:
            raise AIProviderResponseError(
                f"AI provider '{provider}' returned invalid temporal_date."
            ) from exc
    return ContextualizationResult(
        assertion=value["assertion"].strip(),
        clinical_status=value["clinical_status"].strip(),
        temporal_context=value["temporal_context"].strip(),
        temporal_date=temporal_date,
        confidence=confidence,
    )
