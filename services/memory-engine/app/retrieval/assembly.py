"""Contract-preserving assembly of retrieved patient context."""

from collections.abc import Iterable
from uuid import UUID

from contracts.schemas import (
    ConflictRecord,
    MemoryContextItem,
    MemoryEvent,
    RetrievedContext,
    VerifiedContext,
)

from .safety import RetrievalSafetyFilter


def _context_item(event: MemoryEvent) -> MemoryContextItem:
    return MemoryContextItem(
        event_id=event.event_id,
        concept_thread_id=event.concept_thread_id,
        normalized_concept=event.normalized_concept,
        clinical_status=event.clinical_status,
        assertion=event.assertion,
        temporal_context=event.temporal_context,
        original_text=event.original_text,
        trust_tier=event.current_trust_tier,
        provenance=event.provenance,
    )


def _category(event: MemoryEvent) -> str:
    entity_type = event.entity_type.casefold()
    domain = event.clinical_domain.casefold()
    concept = event.normalized_concept.casefold()
    if entity_type == "medication" or domain == "medication":
        return "medications"
    if entity_type == "allergy" or "allergy" in concept:
        return "allergies"
    if entity_type == "procedure" or domain == "procedure":
        return "procedures"
    if entity_type in {"lab", "lab_result"} or domain in {"laboratory", "lab"}:
        return "lab_trends"
    if entity_type == "condition":
        return "conditions"
    return "significant_events"


class PatientContextAssembler:
    """Builds the exact RetrievedContext contract after safety classification."""

    def __init__(self, safety_filter: RetrievalSafetyFilter) -> None:
        self.safety_filter = safety_filter

    def assemble(
        self,
        *,
        patient_id: UUID,
        events: Iterable[MemoryEvent],
        conflicts: list[ConflictRecord],
    ) -> RetrievedContext:
        verified = VerifiedContext()
        unverified: list[MemoryContextItem] = []
        unresolved_event_ids = self.safety_filter.unresolved_event_ids(patient_id)
        seen: set[UUID] = set()

        for event in events:
            if event.patient_id != patient_id or event.event_id in seen:
                continue
            seen.add(event.event_id)
            item = _context_item(event)
            decision = self.safety_filter.classify(
                event,
                unresolved_event_ids=unresolved_event_ids,
            )
            if decision.verified:
                getattr(verified, _category(event)).append(item)
            else:
                unverified.append(item)

        return RetrievedContext(
            verified_context=verified,
            unverified_information=unverified,
            conflicts=conflicts,
        )


__all__ = ["PatientContextAssembler"]
