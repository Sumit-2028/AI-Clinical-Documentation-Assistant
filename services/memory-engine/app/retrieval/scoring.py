"""Deterministic relevance scoring for longitudinal patient-memory retrieval."""

from dataclasses import dataclass
import re
from typing import Sequence
from uuid import UUID

from contracts.schemas import MemoryEvent


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_QUERY_ALIASES = {
    "allergies": "allergy",
    "medications": "medication",
    "conditions": "condition",
    "procedures": "procedure",
    "labs": "laboratory",
    "lab": "laboratory",
    "htn": "hypertension",
}


@dataclass(frozen=True)
class RelevanceResult:
    score: float
    reasons: tuple[str, ...] = ()


def normalize_text(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.casefold()))


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.casefold()))


def _query_variants(query: str) -> tuple[str, ...]:
    normalized = normalize_text(query)
    if not normalized:
        return ()
    alias = _QUERY_ALIASES.get(normalized)
    return (normalized, alias) if alias and alias != normalized else (normalized,)


def _best_query_score(event: MemoryEvent, query: str) -> tuple[float, tuple[str, ...]]:
    variants = _query_variants(query)
    if not variants:
        return 0.0, ()

    concept = normalize_text(event.normalized_concept)
    concept_tokens = _tokens(concept)
    searchable_fields = {
        "domain": normalize_text(event.clinical_domain),
        "entity_type": normalize_text(event.entity_type),
        "text": normalize_text(f"{event.original_text} {event.processed_text}"),
    }
    best_score = 0.0
    best_reasons: tuple[str, ...] = ()

    for variant in variants:
        variant_tokens = _tokens(variant)
        if not variant_tokens:
            continue

        if variant == concept:
            score = 1.0
            reasons = ("normalized_concept_exact",)
        elif variant in concept or concept in variant:
            score = 0.90
            reasons = ("normalized_concept_partial",)
        elif variant in searchable_fields["entity_type"] or variant in searchable_fields["domain"]:
            score = 0.82
            reasons = ("clinical_type_match",)
        else:
            concept_overlap = len(variant_tokens & concept_tokens) / len(variant_tokens)
            text_tokens = _tokens(searchable_fields["text"])
            text_overlap = len(variant_tokens & text_tokens) / len(variant_tokens)
            overlap = max(concept_overlap, text_overlap)
            score = 0.68 * overlap
            reasons = ("clinical_text_overlap",) if overlap else ()

        if score > best_score:
            best_score = score
            best_reasons = reasons

    return best_score, best_reasons


def calculate_relevance(
    event: MemoryEvent,
    *,
    query_concepts: Sequence[str],
    encounter_id: UUID | None = None,
) -> RelevanceResult:
    """Return a bounded, explainable score without model or database randomness."""

    queries = tuple(query for query in query_concepts if normalize_text(query))
    if not queries:
        score = 0.50
        reasons: list[str] = ["patient_context"]
    else:
        matches = [_best_query_score(event, query) for query in queries]
        best_score, best_reasons = max(matches, key=lambda result: result[0])
        if best_score <= 0.0:
            return RelevanceResult(score=0.0)
        score = best_score
        reasons = list(best_reasons)

    if encounter_id is not None and event.encounter_id == encounter_id:
        score = min(1.0, score + 0.08)
        reasons.append("current_encounter")

    return RelevanceResult(score=round(score, 6), reasons=tuple(reasons))


def score_relevance(
    event: MemoryEvent,
    query_concepts: Sequence[str],
    encounter_id: UUID | None = None,
) -> float:
    """Convenience API returning only the deterministic numeric score."""

    return calculate_relevance(
        event,
        query_concepts=query_concepts,
        encounter_id=encounter_id,
    ).score


__all__ = ["RelevanceResult", "calculate_relevance", "normalize_text", "score_relevance"]
