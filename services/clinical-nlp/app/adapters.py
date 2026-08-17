from dataclasses import dataclass
import os

from services.ai_adapters import env_float, env_int

from .contextualization import (
    ContextualizationAdapter,
    MockGeminiContextualizationAdapter,
    ProductionGeminiContextualizationAdapter,
)
from .ner import (
    BioClinicalBERTNERAdapter,
    MockClinicalNERAdapter,
    NERAdapter,
)


@dataclass(frozen=True)
class NLPAdapterBundle:
    ner: NERAdapter
    contextualization: ContextualizationAdapter


def build_adapter_bundle(mode: str | None = None) -> NLPAdapterBundle:
    selected_mode = (mode or os.getenv("STEP2_NLP_MODE", "mock")).lower()
    if selected_mode == "mock":
        return NLPAdapterBundle(
            ner=MockClinicalNERAdapter(),
            contextualization=MockGeminiContextualizationAdapter(),
        )

    return NLPAdapterBundle(
        ner=BioClinicalBERTNERAdapter(
            model_name=os.getenv("BIOCLINICALBERT_MODEL_NAME"),
            model_path=os.getenv("BIOCLINICALBERT_MODEL_PATH"),
        ),
        contextualization=ProductionGeminiContextualizationAdapter(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_name=os.getenv("GEMINI_MODEL"),
            base_url=os.getenv("GEMINI_API_URL"),
            endpoint=os.getenv("GEMINI_ENDPOINT"),
            timeout_seconds=env_float("AI_TIMEOUT_SECONDS", 15.0),
            max_retries=env_int("AI_MAX_RETRIES", 2),
        ),
    )
