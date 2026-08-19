"""Replaceable BioClinicalBERT token-classification adapter.

The pipeline only depends on the small NER adapter protocol.  Loading the
optional transformers stack is lazy, so importing the backend does not pull a
model into memory or silently substitute mock entities.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from .base import EntitySpan
from .hybrid import NLPModelUnavailableError


class BioClinicalBERTNERAdapter:
    model_name = "BioClinicalBERT"

    def __init__(self, model: Callable[[str], object] | None = None) -> None:
        self._model = model

    def extract(self, text: str) -> list[EntitySpan]:
        if not text.strip():
            return []
        model = self._model or self._load_model()
        raw_entities = model(text)
        if not isinstance(raw_entities, list):
            raise NLPModelUnavailableError(
                "BioClinicalBERT returned an invalid token-classification response."
            )
        entities: list[EntitySpan] = []
        for item in raw_entities:
            if not isinstance(item, Mapping):
                continue
            start = item.get("start")
            end = item.get("end")
            word = str(item.get("word") or item.get("text") or "").strip()
            if not word:
                continue
            if not isinstance(start, int) or not isinstance(end, int):
                start = text.casefold().find(word.casefold())
                end = start + len(word) if start >= 0 else -1
            if start < 0 or end <= start or end > len(text):
                continue
            score = item.get("score", 0.0)
            try:
                confidence = max(0.0, min(1.0, float(score)))
            except (TypeError, ValueError):
                confidence = 0.0
            label = str(item.get("entity_group") or item.get("entity") or "clinical_entity")
            entities.append(
                EntitySpan(
                    text=text[start:end],
                    start=start,
                    end=end,
                    entity_type=label.removeprefix("B-").removeprefix("I-").lower(),
                    confidence=confidence,
                    extraction_source="bioclinicalbert",
                )
            )
        return entities

    @staticmethod
    def _load_model():
        model_name = os.getenv(
            "BIOCLINICALBERT_MODEL_PATH",
            os.getenv("BIOCLINICALBERT_MODEL_NAME", "emilyalsentzer/Bio_ClinicalBERT"),
        )
        try:
            from transformers import pipeline  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise NLPModelUnavailableError(
                "transformers is not installed; configure a clinical NER provider."
            ) from exc
        try:
            return pipeline("token-classification", model=model_name, aggregation_strategy="simple")
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            raise NLPModelUnavailableError(
                f"BioClinicalBERT model '{model_name}' could not be loaded."
            ) from exc


__all__ = ["BioClinicalBERTNERAdapter"]
