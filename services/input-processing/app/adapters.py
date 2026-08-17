import os
from dataclasses import dataclass
from typing import Protocol

from services.ai_adapters import JSONHTTPClient, env_float, env_int

from .ocr import MockOCRAdapter, OCRAdapter, ProductionOCRAdapter
from .vlm import MockVLMAdapter, ProductionVLMAdapter, VLMAdapter


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    confidence: float
    provider_name: str


class TranslationAdapter(Protocol):
    provider_name: str

    def translate(self, text: str, *, source_language: str) -> TranslationResult:
        ...


class MockTranslationAdapter:
    provider_name = "mock-translation"

    def translate(self, text: str, *, source_language: str) -> TranslationResult:
        return TranslationResult(
            translated_text=text.strip(),
            confidence=1.0 if source_language.lower() == "en" else 0.86,
            provider_name=self.provider_name,
        )


class ProductionTranslationAdapter:
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
        self.provider_name = provider_name
        self.api_key = api_key
        self.endpoint = endpoint
        self.http_client = http_client or JSONHTTPClient(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def translate(self, text: str, *, source_language: str) -> TranslationResult:
        from .ocr.production import AIProviderUnavailableError

        if not self.api_key:
            raise AIProviderUnavailableError(
                f"Translation provider '{self.provider_name}' is not configured."
            )
        if not self.endpoint:
            raise AIProviderUnavailableError(
                f"Translation provider '{self.provider_name}' has no endpoint configured."
            )
        response = self.http_client.post_json(
            self.endpoint,
            {"text": text, "source_language": source_language},
            provider=self.provider_name,
            operation="translation.translate",
            api_key=self.api_key,
        )
        translated_text = response.get("translated_text")
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError(
                f"Translation provider '{self.provider_name}' response is missing translated_text."
            )
        try:
            confidence = float(response.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Translation provider '{self.provider_name}' returned invalid confidence."
            ) from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                f"Translation provider '{self.provider_name}' returned out-of-range confidence."
            )
        return TranslationResult(
            translated_text=translated_text.strip(),
            confidence=confidence,
            provider_name=str(response.get("provider_name") or self.provider_name),
        )


@dataclass(frozen=True)
class AdapterBundle:
    ocr: OCRAdapter
    vlm: VLMAdapter
    translation: TranslationAdapter


def build_adapter_bundle(mode: str | None = None) -> AdapterBundle:
    selected_mode = (mode or os.getenv("STEP1_AI_MODE", "mock")).lower()

    if selected_mode == "mock":
        return AdapterBundle(
            ocr=MockOCRAdapter(),
            vlm=MockVLMAdapter(),
            translation=MockTranslationAdapter(),
        )

    provider_name = os.getenv("STEP1_AI_PROVIDER", "configured-provider")
    api_key = os.getenv("STEP1_AI_API_KEY")
    endpoint = os.getenv("STEP1_AI_ENDPOINT")
    timeout_seconds = env_float("AI_TIMEOUT_SECONDS", 15.0)
    max_retries = env_int("AI_MAX_RETRIES", 2)
    return AdapterBundle(
        ocr=ProductionOCRAdapter(
            provider_name=provider_name,
            api_key=api_key,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        vlm=ProductionVLMAdapter(
            provider_name=provider_name,
            api_key=api_key,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        translation=ProductionTranslationAdapter(
            provider_name=provider_name,
            api_key=api_key,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
    )
