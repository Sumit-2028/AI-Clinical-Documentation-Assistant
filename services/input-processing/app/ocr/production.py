from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from services.ai_adapters import (
    AIProviderConfigurationError,
    AIProviderResponseError,
    JSONHTTPClient,
)

from .base import OCRResult


class AIProviderUnavailableError(AIProviderConfigurationError):
    """Raised when a production adapter cannot call its configured provider."""


class ProductionOCRAdapter:
    """Provider-neutral boundary for a real OCR integration.

    A provider client should be injected here by deployment-specific code. The
    Step 1 business layer never depends on a provider SDK or API key format.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        http_client: JSONHTTPClient | None = None,
    ) -> None:
        self.engine_name = provider_name
        self.api_key = api_key
        self.endpoint = endpoint
        self.http_client = http_client or JSONHTTPClient(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def extract(self, content: bytes, *, filename: str | None = None) -> OCRResult:
        if not self.api_key:
            raise AIProviderUnavailableError(
                f"OCR provider '{self.engine_name}' is not configured."
            )
        if not self.endpoint:
            raise AIProviderUnavailableError(
                f"OCR provider '{self.engine_name}' has no endpoint configured."
            )
        response = self.http_client.post_json(
            self.endpoint,
            {
                "content_base64": base64.b64encode(content).decode("ascii"),
                "filename": filename,
            },
            provider=self.engine_name,
            operation="ocr.extract",
            api_key=self.api_key,
        )
        text = _required_text(response, "text", self.engine_name)
        confidence = _confidence(response.get("confidence"), self.engine_name)
        return OCRResult(
            text=text,
            confidence=confidence,
            engine=str(response.get("engine") or self.engine_name),
        )


def _required_text(response: Mapping[str, Any], field: str, provider: str) -> str:
    value = response.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AIProviderResponseError(
            f"AI provider '{provider}' response is missing '{field}'."
        )
    return value.strip()


def _confidence(value: Any, provider: str) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned an invalid confidence."
        ) from exc
    if not 0.0 <= confidence <= 1.0:
        raise AIProviderResponseError(
            f"AI provider '{provider}' returned an out-of-range confidence."
        )
    return confidence
