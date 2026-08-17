from datetime import datetime, timezone
from uuid import UUID, uuid4

from contracts.schemas import (
    ClinicalEvent,
    MemoryEvent,
    MemorySource,
    MemoryWriteResponse,
    RejectedMemoryEvent,
    ReviewedStatus,
    WrittenMemoryEvent,
)

from ..conflicts import detect_conflict
from ..provenance import build_provenance
from ..stores import InMemoryMemoryStore
from ..threads import match_concept_thread
from ..trust import initial_trust_tier


class MemoryWriteGate:
    """The sole application boundary that appends clinical memory events."""

    def __init__(self, store: InMemoryMemoryStore | None = None) -> None:
        self.store = store or InMemoryMemoryStore()

    def write(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        source: MemorySource,
        clinical_events: list[ClinicalEvent],
    ) -> MemoryWriteResponse:
        written: list[WrittenMemoryEvent] = []
        conflicts_detected: list[UUID] = []
        rejected: list[RejectedMemoryEvent] = []

        for clinical_event in clinical_events:
            if clinical_event.validation_status.value != "valid":
                rejected.append(
                    RejectedMemoryEvent(
                        event_id=clinical_event.event_local_id,
                        reason="ClinicalEvent validation_status is not valid.",
                    )
                )
                continue

            threads = self.store.list_threads(patient_id)
            match = match_concept_thread(clinical_event, threads)
            tier = initial_trust_tier(source)
            memory_event = MemoryEvent(
                event_id=uuid4(),
                patient_id=patient_id,
                encounter_id=encounter_id,
                source=source,
                source_event_id=clinical_event.event_local_id,
                concept_thread_id=match.concept_thread_id,
                normalized_concept=clinical_event.normalized_concept,
                snomed_ct_id=clinical_event.snomed_ct_id,
                entity_type=clinical_event.entity_type,
                clinical_domain=clinical_event.clinical_domain,
                original_text=clinical_event.original_text,
                processed_text=clinical_event.processed_text,
                assertion=clinical_event.assertion,
                clinical_status=clinical_event.clinical_status,
                temporal_context=clinical_event.temporal_context,
                temporal_date=clinical_event.temporal_date,
                trust_tier=tier,
                current_trust_tier=tier,
                reviewed_status=ReviewedStatus.UNREVIEWED,
                provenance=build_provenance(clinical_event),
                created_at=datetime.now(timezone.utc),
            )

            existing_events = self.store.list_events(patient_id)
            detected = detect_conflict(
                memory_event,
                existing_events,
                has_existing_pair=self.store.has_conflict_pair,
            )
            self.store._append_event(memory_event)
            if match.is_new_thread:
                self.store.create_thread(
                    patient_id=patient_id,
                    normalized_concept=memory_event.normalized_concept,
                    snomed_ct_id=memory_event.snomed_ct_id,
                    clinical_domain=memory_event.clinical_domain,
                    event=memory_event,
                )
            else:
                self.store.update_thread(memory_event)

            for conflict in detected:
                self.store.add_conflict(conflict)
                conflicts_detected.append(conflict.conflict_id)

            written.append(
                WrittenMemoryEvent(
                    event_id=memory_event.event_id,
                    concept_thread_id=memory_event.concept_thread_id,
                    trust_tier=memory_event.current_trust_tier,
                    thread_match_confidence=match.confidence,
                    thread_match_method=match.method,
                    is_new_thread=match.is_new_thread,
                )
            )

        return MemoryWriteResponse(
            written_events=written,
            conflicts_detected=conflicts_detected,
            rejected_events=rejected,
        )
