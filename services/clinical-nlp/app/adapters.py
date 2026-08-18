from dataclasses import dataclass

from .config import settings
from .contextualization import (
    ContextualizationAdapter,
    ProductionGeminiContextualizationAdapter,
)
from .ner import (
    HybridNERAdapter,
    NERAdapter,
)


@dataclass(frozen=True)
class NLPAdapterBundle:
    ner: NERAdapter
    contextualization: ContextualizationAdapter


def build_adapter_bundle() -> NLPAdapterBundle:
    """Build production adapter bundle using Step 2 settings.

    Requires GEMINI_API_KEY to be set in environment.
    """
    return NLPAdapterBundle(
        ner=HybridNERAdapter(),
        contextualization=ProductionGeminiContextualizationAdapter(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            timeout_seconds=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        ),
    )
