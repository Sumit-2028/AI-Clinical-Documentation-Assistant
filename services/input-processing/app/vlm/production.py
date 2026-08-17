from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from services.ai_adapters import AIProviderResponseError, JSONHTTPClient

from .base import VLMResult


class ProductionVLMAdapter:
    """Provider-neutral VLM boundary; provider clients are deployment injected."""

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
        self.model_name = provider_name
        self.api_key = api_key
        self.endpoint = endpoint
        self.http_client = http_client or JSONHTTPClient(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def analyze(
        self,
        content: bytes,
        *,
        ocr_text: str,
        filename: str | None = None,
    ) -> VLMResult:
        from ..ocr.production import AIProviderUnavailableError

        if not self.api_key:
            raise AIProviderUnavailableError(
                f"VLM provider '{self.model_name}' is not configured."
            )
        if not self.endpoint:
            raise AIProviderUnavailableError(
                f"VLM provider '{self.model_name}' has no endpoint configured."
            )
        response = self.http_client.post_json(
            self.endpoint,
            {
                "content_base64": base64.b64encode(content).decode("ascii"),
                "ocr_text": ocr_text,
                "filename": filename,
            },
            provider=self.model_name,
            operation="vlm.analyze",
            api_key=self.api_key,
        )
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise AIProviderResponseError(
                f"AI provider '{self.model_name}' response is missing 'text'."
            )
        try:
            confidence = float(response.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise AIProviderResponseError(
                f"AI provider '{self.model_name}' returned an invalid confidence."
            ) from exc
        if not 0.0 <= confidence <= 1.0:
            raise AIProviderResponseError(
                f"AI provider '{self.model_name}' returned an out-of-range confidence."
            )
        return VLMResult(
            text=text.strip(),
            confidence=confidence,
            model=str(response.get("model") or self.model_name),
        )
