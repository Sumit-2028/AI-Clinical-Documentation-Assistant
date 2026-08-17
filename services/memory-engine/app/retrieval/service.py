from collections.abc import Sequence
from uuid import UUID

from contracts.schemas import MemoryEvent, RetrievedContext

from ..retrieval.assembly import PatientContextAssembler
from ..retrieval.scoring import calculate_relevance
from ..retrieval.safety import RetrievalSafetyFilter
from ..stores import InMemoryMemoryStore
from ..vector import BasicVectorStore, VectorSearchResult, VectorStore


class RetrievalService:
    """Coordinates candidate search, deterministic ranking, safety, and assembly."""

    def __init__(
        self,
        *,
        store: InMemoryMemoryStore,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.store = store
        self.vector_store = vector_store or BasicVectorStore(store)
        self.safety_filter = RetrievalSafetyFilter(store)
        self.assembler = PatientContextAssembler(self.safety_filter)

    def retrieve(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        query_concepts: Sequence[str],
    ) -> RetrievedContext:
        raw_candidates = self.vector_store.search(
            patient_id=patient_id,
            encounter_id=encounter_id,
            query_concepts=query_concepts,
        )
        candidates = self._normalize_candidates(
            raw_candidates,
            patient_id=patient_id,
            encounter_id=encounter_id,
            query_concepts=query_concepts,
        )
        candidate_events = [candidate.event for candidate in candidates]
        candidate_event_ids = {event.event_id for event in candidate_events}
        conflicts = [
            conflict
            for conflict in self.store.list_conflicts(
                patient_id=patient_id,
                status="unresolved",
            )
            if not query_concepts
            or conflict.event_a_id in candidate_event_ids
            or conflict.event_b_id in candidate_event_ids
        ]
        # Once a conflict is relevant, include both sides in the unverified
        # section even if a lexical/vector candidate search returned only one.
        # This prevents retrieval from hiding the contradictory evidence.
        for conflict in conflicts:
            for event_id in (conflict.event_a_id, conflict.event_b_id):
                if event_id in candidate_event_ids:
                    continue
                event = self.store.get_event(event_id)
                if event is not None and event.patient_id == patient_id:
                    candidate_events.append(event)
                    candidate_event_ids.add(event.event_id)
        return self.assembler.assemble(
            patient_id=patient_id,
            events=candidate_events,
            conflicts=conflicts,
        )

    @staticmethod
    def _normalize_candidates(
        candidates,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        query_concepts: Sequence[str],
    ) -> list[VectorSearchResult]:
        normalized: list[VectorSearchResult] = []
        seen: set[UUID] = set()
        for candidate in candidates:
            if isinstance(candidate, VectorSearchResult):
                event = candidate.event
                score = candidate.score
            elif isinstance(candidate, MemoryEvent):
                event = candidate
                score = calculate_relevance(
                    event,
                    query_concepts=query_concepts,
                    encounter_id=encounter_id,
                ).score
            else:
                event = candidate.event
                score = float(candidate.score)
            if event.patient_id != patient_id or event.event_id in seen:
                continue
            if query_concepts and score <= 0.0:
                continue
            seen.add(event.event_id)
            normalized.append(VectorSearchResult(event=event, score=score))

        return sorted(
            normalized,
            key=lambda result: (
                -result.score,
                -int(result.event.encounter_id == encounter_id),
                -result.event.created_at.timestamp(),
                str(result.event.event_id),
            ),
        )


def retrieve_context(
    store: InMemoryMemoryStore,
    *,
    patient_id: UUID,
    query_concepts: Sequence[str],
    encounter_id: UUID | None = None,
    vector_store: VectorStore | None = None,
) -> RetrievedContext:
    """Backward-compatible function facade over the retrieval service."""

    return RetrievalService(store=store, vector_store=vector_store).retrieve(
        patient_id=patient_id,
        encounter_id=encounter_id or UUID(int=0),
        query_concepts=query_concepts,
    )


__all__ = ["RetrievalService", "retrieve_context"]
