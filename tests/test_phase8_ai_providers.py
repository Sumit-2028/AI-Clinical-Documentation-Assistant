"""Offline coverage for Phase 8 provider boundaries."""

from uuid import uuid4

from contracts.schemas import DocumentType, RetrievedContext, VerifiedContext
from services.ai_adapters import JSONHTTPClient
from services.clinical_nlp.app.contextualization import (
    ProductionGeminiContextualizationAdapter,
)
from services.clinical_nlp.app.ner import BioClinicalBERTNERAdapter
from services.doc_generation.app.context import GenerationContext
from services.doc_generation.app.generation import (
    ProductionLLMGenerator,
    build_document_generator,
)
from services.input_processing.app.adapters import ProductionTranslationAdapter
from services.input_processing.app.ocr.production import ProductionOCRAdapter
from services.input_processing.app.vlm.production import ProductionVLMAdapter


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeHTTPClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, *, json, headers, timeout):
        self.calls.append(
            {"url": url, "payload": json, "headers": headers, "timeout": timeout}
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeProviderClient:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post_json(self, url, payload, **kwargs):
        self.calls.append({"url": url, "payload": payload, "metadata": kwargs})
        return self.body


def test_shared_http_transport_retries_without_logging_payload():
    transport = FakeHTTPClient(
        [TimeoutError("temporary"), FakeResponse(200, {"ok": True})]
    )
    sleeps = []
    client = JSONHTTPClient(
        client=transport,
        max_retries=1,
        sleep=sleeps.append,
    )

    response = client.post_json(
        "https://provider.invalid/ocr",
        {"medical_text": "sensitive content"},
        provider="test-provider",
        operation="ocr.extract",
        api_key="secret-key",
    )

    assert response == {"ok": True}
    assert len(transport.calls) == 2
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer secret-key"
    assert sleeps == [0.1]


def test_configured_step1_adapters_translate_provider_envelopes():
    ocr_client = FakeProviderClient({"text": "OCR text", "confidence": 0.91})
    ocr = ProductionOCRAdapter(
        provider_name="ocr-provider",
        api_key="ocr-key",
        endpoint="https://provider.invalid/ocr",
        http_client=ocr_client,
    )
    ocr_result = ocr.extract(b"image-bytes", filename="scan.png")
    assert ocr_result.text == "OCR text"
    assert ocr_result.confidence == 0.91
    assert ocr_client.calls[0]["metadata"]["operation"] == "ocr.extract"

    vlm_client = FakeProviderClient(
        {"text": "VLM text", "confidence": 0.88, "model": "vision-model"}
    )
    vlm = ProductionVLMAdapter(
        provider_name="vlm-provider",
        api_key="vlm-key",
        endpoint="https://provider.invalid/vlm",
        http_client=vlm_client,
    )
    assert vlm.analyze(b"image-bytes", ocr_text="OCR text").model == "vision-model"

    translation_client = FakeProviderClient(
        {"translated_text": "Translated text", "confidence": 0.86}
    )
    translation = ProductionTranslationAdapter(
        provider_name="translation-provider",
        api_key="translation-key",
        endpoint="https://provider.invalid/translate",
        http_client=translation_client,
    )
    result = translation.translate("texto", source_language="es")
    assert result.translated_text == "Translated text"
    assert result.provider_name == "translation-provider"


def test_gemini_adapter_parses_structured_contextualization():
    client = FakeProviderClient(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"assertion":"affirmed",'
                                    '"clinical_status":"active",'
                                    '"temporal_context":"past",'
                                    '"temporal_date":"2025-04-02",'
                                    '"confidence":0.93}'
                                )
                            }
                        ]
                    }
                }
            ]
        }
    )
    adapter = ProductionGeminiContextualizationAdapter(
        api_key="gemini-key",
        endpoint="https://provider.invalid/gemini",
        http_client=client,
    )

    result = adapter.contextualize("History of pneumonia", "pneumonia")

    assert result.assertion == "affirmed"
    assert result.temporal_date.isoformat() == "2025-04-02"
    assert client.calls[0]["metadata"]["operation"] == "clinical_contextualization"


def test_bioclinicalbert_normalizes_injected_model_output():
    adapter = BioClinicalBERTNERAdapter(
        model=lambda text: [
            {
                "word": "hypertension",
                "start": 12,
                "end": 24,
                "entity_group": "condition",
                "score": 0.95,
            }
        ]
    )

    entities = adapter.extract("Patient has hypertension")

    assert entities[0].text == "hypertension"
    assert entities[0].entity_type == "condition"
    assert entities[0].confidence == 0.95


def test_production_document_generator_preserves_provenance_boundary():
    patient_id = uuid4()
    encounter_id = uuid4()
    context = GenerationContext(
        patient_id=patient_id,
        encounter_id=encounter_id,
        current_events=(),
        verified_sources=(),
        unverified_sources=(),
        retrieved_context=RetrievedContext(verified_context=VerifiedContext()),
        flags=(),
    )
    generator = ProductionLLMGenerator(
        client=lambda *_args: {
            "sections": {
                "subjective": "No subjective information documented.",
                "objective": "No objective findings documented.",
                "assessment": "No assessment documented.",
                "plan": "Plan pending physician review.",
            }
        }
    )

    draft = generator.generate(context, document_type=DocumentType.SOAP_NOTE)

    assert draft.generator == "production_llm"
    assert draft.sections.assessment == "No assessment documented."
    assert {entry.section for entry in draft.provenance_map} == {
        "subjective",
        "objective",
        "assessment",
        "plan",
    }
    assert all(entry.is_inferred for entry in draft.provenance_map)


def test_document_generator_selection_remains_mock_by_default(monkeypatch):
    monkeypatch.delenv("STEP4_LLM_MODE", raising=False)
    assert build_document_generator().__class__.__name__ == "DeterministicMockGenerator"


def test_document_generator_selection_uses_environment_configuration(monkeypatch):
    monkeypatch.setenv("STEP4_LLM_MODE", "production")
    monkeypatch.setenv("STEP4_LLM_API_KEY", "configured-key")
    monkeypatch.setenv("STEP4_LLM_ENDPOINT", "https://provider.invalid/llm")

    generator = build_document_generator()

    assert isinstance(generator, ProductionLLMGenerator)
    assert generator.endpoint == "https://provider.invalid/llm"
