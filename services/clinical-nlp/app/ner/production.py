from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from .base import EntitySpan


class NLPModelUnavailableError(RuntimeError):
    """Raised when a production NLP model is not configured or injectable."""


class BioClinicalBERTNERAdapter:
    """Replaceable boundary for a BioClinicalBERT NER pipeline.

    The model callable is injected by deployment code. No model SDK or
    provider-specific assumptions leak into the NLP orchestration layer.
    """

    model_name = "BioClinicalBERT"

    def __init__(
        self,
        model: Callable[[str], list[EntitySpan]] | None = None,
        *,
        model_loader: Callable[[str], Callable[[str], Any]] | None = None,
        model_name: str | None = None,
        model_path: str | None = None,
    ) -> None:
        self.model = model
        self.model_loader = model_loader
        self.model_name = model_name or self.model_name
        self.model_path = model_path or os.getenv(
            "BIOCLINICALBERT_MODEL_PATH"
        ) or os.getenv(
            "BIOCLINICALBERT_MODEL_NAME", "emilyalsentzer/Bio_ClinicalBERT"
        )

    def extract(self, text: str) -> list[EntitySpan]:
        if self.model is None:
            self.model = self._load_model()
        return _normalize_entities(self.model(text), text)

    def _load_model(self) -> Callable[[str], Any]:
        if self.model_loader is not None:
            return self.model_loader(self.model_path)
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise NLPModelUnavailableError(
                "BioClinicalBERT requires an injected model or the optional transformers dependency."
            ) from exc
        try:
            return pipeline(
                "ner",
                model=self.model_path,
                aggregation_strategy="simple",
            )
        except Exception as exc:
            raise NLPModelUnavailableError(
                f"BioClinicalBERT model '{self.model_path}' could not be loaded."
            ) from exc


def _normalize_entities(value: Any, text: str) -> list[EntitySpan]:
    if not isinstance(value, list):
        raise NLPModelUnavailableError(
            "BioClinicalBERT provider returned a non-list entity result."
        )
    entities: list[EntitySpan] = []
    for item in value:
        if isinstance(item, EntitySpan):
            entities.append(item)
            continue
        if not isinstance(item, Mapping):
            raise NLPModelUnavailableError(
                "BioClinicalBERT provider returned an invalid entity."
            )
        entity_text = str(item.get("word") or item.get("text") or "").strip()
        if not entity_text:
            continue
        start_value = item.get("start")
        end_value = item.get("end")
        if start_value is None or end_value is None:
            start_value = text.find(entity_text)
            end_value = start_value + len(entity_text)
        try:
            start = int(start_value)
            end = int(end_value)
            confidence = float(item.get("score", item.get("confidence", 0.0)))
        except (TypeError, ValueError) as exc:
            raise NLPModelUnavailableError(
                "BioClinicalBERT provider returned invalid entity offsets or confidence."
            ) from exc
        if start < 0 or end < start or end > len(text) or not 0.0 <= confidence <= 1.0:
            raise NLPModelUnavailableError(
                "BioClinicalBERT provider returned an invalid entity span."
            )
        entities.append(
            EntitySpan(
                text=text[start:end] if text[start:end] else entity_text,
                start=start,
                end=end,
                entity_type=str(
                    item.get("entity_group") or item.get("entity") or "clinical_entity"
                ),
                confidence=confidence,
            )
        )
    return entities
