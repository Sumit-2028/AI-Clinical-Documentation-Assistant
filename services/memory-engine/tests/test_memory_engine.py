from uuid import uuid4

import pytest

from contracts.schemas import (
    ClinicalEvent,
    ClinicalEventValidationStatus,
    ConflictResolutionAction,
    ConflictStatus,
    InputModality,
    MemoryRetrieveRequest,
    MemorySource,
    MemoryWriteRequest,
    ProcessingStatus,
    SourceTextSpan,
    TierReviewRequest,
    TrustTier,
)
from services.memory_engine.app.service import (
    ConflictResolutionError,
    MemoryEngineService,
)
from services.memory_engine.app.stores import InMemoryMemoryStore
from services.memory_engine.app.write_gate import MemoryWriteGate


def make_clinical_event(
    *,
    concept: str = "Hypertension",
    code: str | None = "38341003",
    status: str = "active",
    assertion: str = "affirmed",
    entity_type: str = "condition",
) -> ClinicalEvent:
    source_text = f"Patient has {concept}"
    return ClinicalEvent(
        event_local_id=uuid4(),
        original_text=source_text,
        processed_text=source_text,
        normalized_concept=concept,
        snomed_ct_id=code,
        entity_type=entity_type,
        clinical_domain=("medication" if entity_type == "medication" else "cardiology"),
        relationships=[],
        assertion=assertion,
        clinical_status=status,
        temporal_context="current",
        temporal_date=None,
        bioclinicalbert_confidence=0.94,
        gemini_contextualization_confidence=0.90,
        source_document_id=uuid4(),
        source_text_span=SourceTextSpan(start=0, end=len(source_text)),
        input_modality=InputModality.TYPED,
        source_language="en",
        translation_confidence=1.0,
        validation_status=ClinicalEventValidationStatus.VALID,
    )


@pytest.fixture
def service():
    return MemoryEngineService(store=InMemoryMemoryStore())


def write(service, event, *, source=MemorySource.SIMULATED_ABHA, patient_id=None, encounter_id=None):
    patient_id = patient_id or uuid4()
    encounter_id = encounter_id or uuid4()
    response = service.write_events(
        MemoryWriteRequest(
            patient_id=patient_id,
            encounter_id=encounter_id,
            source=source,
            clinical_events=[event],
        )
    )
    return response, patient_id, encounter_id


def test_new_memory_event_passes_single_write_gate(service):
    response, patient_id, _ = write(service, make_clinical_event())

    assert len(response.written_events) == 1
    written = response.written_events[0]
    assert written.trust_tier == TrustTier.VERIFIED
    assert written.is_new_thread is True
    assert service.get_events(patient_id).events[0].patient_id == patient_id


def test_repeated_event_is_append_only_and_reuses_concept_thread(service):
    first = make_clinical_event()
    response_a, patient_id, encounter_id = write(service, first)
    response_b, _, _ = write(
        service,
        make_clinical_event(),
        patient_id=patient_id,
        encounter_id=encounter_id,
    )

    assert response_b.written_events[0].is_new_thread is False
    assert response_b.written_events[0].concept_thread_id == response_a.written_events[0].concept_thread_id
    events = service.get_events(patient_id).events
    assert len(events) == 2
    assert events[0].event_id != events[1].event_id
    assert service.get_current_state(patient_id).concept_threads[0].event_count == 2


def test_provenance_is_retained(service):
    event = make_clinical_event()
    response, patient_id, _ = write(service, event)
    stored = service.get_events(patient_id).events[0]

    assert stored.provenance.source_document_id == event.source_document_id
    assert stored.provenance.source_event_id == event.event_local_id
    assert stored.provenance.source_text_span == event.source_text_span
    assert stored.provenance.input_modality == event.input_modality
    assert stored.provenance.source_language == event.source_language
    assert stored.provenance.confidence == 0.90


def test_patient_upload_is_tier3_and_not_verified(service):
    response, patient_id, _ = write(
        service,
        make_clinical_event(),
        source=MemorySource.PATIENT_UPLOAD,
    )

    assert response.written_events[0].trust_tier == TrustTier.UNVERIFIED
    context = service.retrieve(
        MemoryRetrieveRequest(patient_id=patient_id, encounter_id=uuid4())
    )
    assert context.verified_context.conditions == []
    assert len(context.unverified_information) == 1


def test_conflict_detection_and_explicit_resolution(service):
    active = make_clinical_event()
    _, patient_id, encounter_id = write(service, active)
    inactive = make_clinical_event(
        status="inactive",
        assertion="negated",
    )
    second, _, _ = write(
        service,
        inactive,
        source=MemorySource.PATIENT_UPLOAD,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )

    assert len(second.conflicts_detected) == 1
    conflict = service.list_conflicts(patient_id=patient_id)[0]
    assert conflict.status == ConflictStatus.UNRESOLVED
    context = service.retrieve(
        MemoryRetrieveRequest(patient_id=patient_id, encounter_id=encounter_id)
    )
    assert len(context.conflicts) == 1
    assert context.verified_context.conditions == []

    resolved = service.resolve_conflict(
        conflict_id=conflict.conflict_id,
        action=ConflictResolutionAction.CONFIRM_EVENT_A,
        physician_id="doctor-123",
    )
    assert resolved.status == ConflictStatus.RESOLVED
    assert resolved.new_event_id is not None
    assert service.list_conflicts(
        patient_id=patient_id,
        status=ConflictStatus.UNRESOLVED,
    ) == []

    resolved_context = service.retrieve(
        MemoryRetrieveRequest(patient_id=patient_id, encounter_id=encounter_id)
    )
    assert len(resolved_context.verified_context.conditions) == 1
    assert len(resolved_context.unverified_information) == 1


def test_keep_unresolved_does_not_silently_resolve(service):
    _, patient_id, encounter_id = write(service, make_clinical_event())
    _, _, _ = write(
        service,
        make_clinical_event(status="inactive", assertion="negated"),
        source=MemorySource.PATIENT_UPLOAD,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )
    conflict = service.list_conflicts(patient_id=patient_id)[0]

    result = service.resolve_conflict(
        conflict_id=conflict.conflict_id,
        action=ConflictResolutionAction.KEEP_UNRESOLVED,
        physician_id="doctor-123",
    )

    assert result.status == ConflictStatus.UNRESOLVED
    assert service.list_conflicts(patient_id=patient_id)[0].status == ConflictStatus.UNRESOLVED


def test_tier3_approval_promotes_only_the_reviewed_event(service):
    response, patient_id, encounter_id = write(
        service,
        make_clinical_event(),
        source=MemorySource.PATIENT_UPLOAD,
    )
    event_id = response.written_events[0].event_id

    result = service.approve_tier3(event_id=event_id, physician_id="doctor-123")

    assert result.new_trust_tier == TrustTier.PHYSICIAN_REVIEWED
    stored = service.get_events(patient_id).events[0]
    assert stored.trust_tier == TrustTier.UNVERIFIED
    assert stored.current_trust_tier == TrustTier.PHYSICIAN_REVIEWED
    context = service.retrieve(
        MemoryRetrieveRequest(patient_id=patient_id, encounter_id=encounter_id)
    )
    assert len(context.verified_context.conditions) == 1
    assert context.verified_context.conditions[0].trust_tier == TrustTier.PHYSICIAN_REVIEWED


def test_tier3_rejection_keeps_event_unverified(service):
    response, patient_id, encounter_id = write(
        service,
        make_clinical_event(),
        source=MemorySource.PATIENT_UPLOAD,
    )
    event_id = response.written_events[0].event_id

    result = service.reject_tier3(event_id=event_id, physician_id="doctor-123")

    assert result.new_trust_tier == TrustTier.UNVERIFIED
    stored = service.get_events(patient_id).events[0]
    assert stored.current_trust_tier == TrustTier.UNVERIFIED
    assert stored.reviewed_status.value == "reviewed_rejected"
    context = service.retrieve(
        MemoryRetrieveRequest(patient_id=patient_id, encounter_id=encounter_id)
    )
    assert context.verified_context.conditions == []
    assert len(context.unverified_information) == 1


def test_invalid_clinical_event_is_rejected_by_write_gate(service):
    event = make_clinical_event().model_copy(
        update={"validation_status": ClinicalEventValidationStatus.INVALID}
    )
    response, patient_id, _ = write(service, event)

    assert response.written_events == []
    assert response.rejected_events[0].event_id == event.event_local_id
    assert service.get_events(patient_id).events == []


def test_resolving_conflict_twice_is_rejected(service):
    _, patient_id, encounter_id = write(service, make_clinical_event())
    _, _, _ = write(
        service,
        make_clinical_event(status="inactive", assertion="negated"),
        source=MemorySource.PATIENT_UPLOAD,
        patient_id=patient_id,
        encounter_id=encounter_id,
    )
    conflict = service.list_conflicts(patient_id=patient_id)[0]
    service.resolve_conflict(
        conflict_id=conflict.conflict_id,
        action=ConflictResolutionAction.CONFIRM_EVENT_A,
        physician_id="doctor-123",
    )

    with pytest.raises(ConflictResolutionError):
        service.resolve_conflict(
            conflict_id=conflict.conflict_id,
            action=ConflictResolutionAction.CONFIRM_EVENT_B,
            physician_id="doctor-123",
        )
