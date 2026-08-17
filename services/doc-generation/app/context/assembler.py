"""Assemble trusted, uncertain, and conflicting inputs for document generation."""

from dataclasses import dataclass
from uuid import UUID

from contracts.schemas import (
    ClinicalEvent,
    DocumentReviewFlag,
    MemoryContextItem,
    RetrievedContext,
    TrustTier,
)


@dataclass(frozen=True)
class ContextSource:
    text: str
    concept: str | None
    source_event_ids: tuple[UUID, ...]
    source_document_ids: tuple[UUID, ...]
    source_kind: str
    trust_tier: TrustTier | None
    confidence: float
    category: str | None = None
    is_inferred: bool = False


@dataclass(frozen=True)
class GenerationContext:
    patient_id: UUID
    encounter_id: UUID
    current_events: tuple[ClinicalEvent, ...]
    verified_sources: tuple[ContextSource, ...]
    unverified_sources: tuple[ContextSource, ...]
    retrieved_context: RetrievedContext
    flags: tuple[DocumentReviewFlag, ...]

    @property
    def supported_text(self) -> str:
        return " ".join(
            source.text
            for source in (*self.current_sources, *self.verified_sources)
        )

    @property
    def current_sources(self) -> tuple[ContextSource, ...]:
        return tuple(
            ContextSource(
                text=event.original_text,
                concept=event.normalized_concept,
                source_event_ids=(event.event_local_id,),
                source_document_ids=(event.source_document_id,),
                source_kind="current_consultation",
                trust_tier=None,
                confidence=min(
                    event.bioclinicalbert_confidence,
                    event.gemini_contextualization_confidence,
                    event.translation_confidence,
                ),
            )
            for event in self.current_events
        )

    @property
    def conflict_event_ids(self) -> set[UUID]:
        return {
            event_id
            for conflict in self.retrieved_context.conflicts
            for event_id in (conflict.event_a_id, conflict.event_b_id)
        }


class ContextAssembler:
    """Preserves trust labels instead of flattening all inputs into facts."""

    def assemble(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        current_events: list[ClinicalEvent],
        retrieved_context: RetrievedContext,
    ) -> GenerationContext:
        verified_items = self._verified_items(retrieved_context)
        verified_sources = tuple(
            self._memory_source(
                item,
                source_kind="verified_context",
                category=category,
            )
            for category, item in verified_items
        )
        unverified_sources = tuple(
            self._memory_source(
                item,
                source_kind=(
                    "conflicting_context"
                    if item.event_id in {
                        event_id
                        for conflict in retrieved_context.conflicts
                        for event_id in (conflict.event_a_id, conflict.event_b_id)
                    }
                    else "unverified_context"
                ),
            )
            for item in retrieved_context.unverified_information
        )

        flags: list[DocumentReviewFlag] = []
        if unverified_sources:
            flags.append(
                DocumentReviewFlag(
                    code="UNVERIFIED_CONTEXT",
                    message="Unverified information is available for physician review and is not treated as established fact.",
                    severity="warning",
                    source_event_ids=[
                        event_id
                        for source in unverified_sources
                        for event_id in source.source_event_ids
                    ],
                )
            )
        if retrieved_context.conflicts:
            flags.append(
                DocumentReviewFlag(
                    code="UNRESOLVED_CONFLICT",
                    message="Retrieved clinical conflicts require physician review before they can support a definitive statement.",
                    severity="high",
                    source_event_ids=[
                        event_id
                        for conflict in retrieved_context.conflicts
                        for event_id in (conflict.event_a_id, conflict.event_b_id)
                    ],
                )
            )

        return GenerationContext(
            patient_id=patient_id,
            encounter_id=encounter_id,
            current_events=tuple(current_events),
            verified_sources=verified_sources,
            unverified_sources=unverified_sources,
            retrieved_context=retrieved_context,
            flags=tuple(flags),
        )

    @staticmethod
    def _verified_items(context: RetrievedContext) -> list[tuple[str, MemoryContextItem]]:
        verified = context.verified_context
        return [
            (category, item)
            for category, items in (
                ("condition", verified.conditions),
                ("medication", verified.medications),
                ("allergy", verified.allergies),
                ("procedure", verified.procedures),
                ("laboratory", verified.lab_trends),
                ("significant_event", verified.significant_events),
            )
            for item in items
        ]

    @staticmethod
    def _memory_source(
        item: MemoryContextItem,
        *,
        source_kind: str,
        category: str | None = None,
    ) -> ContextSource:
        return ContextSource(
            text=item.original_text or item.normalized_concept,
            concept=item.normalized_concept,
            source_event_ids=(item.event_id,),
            source_document_ids=(item.provenance.source_document_id,),
            source_kind=source_kind,
            trust_tier=item.trust_tier,
            confidence=item.provenance.confidence,
            category=category,
        )


__all__ = ["ContextAssembler", "ContextSource", "GenerationContext"]
