"""Replaceable candidate-retrieval boundary for memory context search."""

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from contracts.schemas import MemoryEvent

from ..retrieval.scoring import calculate_relevance


@dataclass(frozen=True)
class VectorSearchResult:
    event: MemoryEvent
    score: float


class VectorStore(Protocol):
    """Interface for a future pgvector or external semantic index."""

    def search(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        query_concepts: Sequence[str],
    ) -> list[VectorSearchResult]: ...


class BasicVectorStore:
    """Deterministic local replacement backed by the existing memory store.

    The name represents the replaceable vector boundary; this MVP implementation
    intentionally uses lexical concept/text overlap and does not create a new DB.
    """

    def __init__(self, memory_store) -> None:
        self.memory_store = memory_store

    def search(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        query_concepts: Sequence[str],
    ) -> list[VectorSearchResult]:
        results: list[VectorSearchResult] = []
        for event in self.memory_store.list_events(patient_id):
            relevance = calculate_relevance(
                event,
                query_concepts=query_concepts,
                encounter_id=encounter_id,
            )
            if query_concepts and relevance.score <= 0.0:
                continue
            results.append(VectorSearchResult(event=event, score=relevance.score))

        return sorted(
            results,
            key=lambda result: (
                -result.score,
                -int(result.event.encounter_id == encounter_id),
                -result.event.created_at.timestamp(),
                str(result.event.event_id),
            ),
        )


__all__ = ["BasicVectorStore", "VectorSearchResult", "VectorStore"]
