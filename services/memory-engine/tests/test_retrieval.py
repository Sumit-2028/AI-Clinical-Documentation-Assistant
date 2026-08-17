from uuid import uuid4

from contracts.schemas import (
    ClinicalEvent,
    ClinicalEventValidationStatus,
    InputModality,
    MemoryRetrieveRequest,
    MemoryWriteRequest,
    MemorySource,
    TrustTier,
)
from services.memory_engine.app.retrieval import score_relevance
from services.memory_engine.app.service import MemoryEngineService
from services.memory_engine.app.stores import InMemoryMemoryStore


def make_event(
    *,
    concept="Hypertension",
    entity_type="condition",
    domain="cardiology",
    source_document_id=None,
    status="active",
    assertion="affirmed",
):
    text = f"Patient has {concept}"
    return ClinicalEvent(
        event_local_id=uuid4(),
        original_text=text,
        processed_text=text,
        normalized_concept=concept,
        snomed_ct_id="38341003" if concept == "Hypertension" else None,
        entity_type=entity_type,
        clinical_domain=domain,
        relationships=[],
        assertion=assertion,
        clinical_status=status,
        temporal_context="current",
        temporal_date=None,
        bioclinicalbert_confidence=0.94,
        gemini_contextualization_confidence=0.90,
        source_document_id=source_document_id or uuid4(),
        source_text_span={"start": 0, "end": len(text)},
        input_modality=InputModality.TYPED,
        source_language="en",
        translation_confidence=1.0,
        validation_status=ClinicalEventValidationStatus.VALID,
    )


def write(
    service,
    event,
    *,
    patient_id=None,
    encounter_id=None,
    source=MemorySource.SIMULATED_ABHA,
):
    patient_id = patient_id or uuid4()
    encounter_id = encounter_id or uuid4()
    response = service.write_events(
        request=MemoryWriteRequest(
            patient_id=patient_id,
            encounter_id=encounter_id,
            source=source,
            clinical_events=[event],
        )
    )
    return response, patient_id, encounter_id


def test_relevance_prioritizes_exact_current_context_and_excludes_irrelevant():
    service = MemoryEngineService(store=InMemoryMemoryStore())
    patient_id = uuid4()
    current_encounter = uuid4()
    _, _, _ = write(
        service,
        make_event(concept="Diabetes"),
        patient_id=patient_id,
        encounter_id=uuid4(),
    )
    _, _, _ = write(
        service,
        make_event(concept="Hypertension"),
        patient_id=patient_id,
        encounter_id=current_encounter,
    )

    context = service.retrieve(
        MemoryRetrieveRequest(
            patient_id=patient_id,
            encounter_id=current_encounter,
            query_concepts=["hypertension"],
        )
    )

    assert [item.normalized_concept for item in context.verified_context.conditions] == [
        "Hypertension"
    ]
    assert score_relevance(
        service.get_events(patient_id).events[1],
        ["hypertension"],
        current_encounter,
    ) > score_relevance(
        service.get_events(patient_id).events[0],
        ["hypertension"],
        current_encounter,
    )


def test_trust_filtering_keeps_patient_upload_unverified():
    service = MemoryEngineService(store=InMemoryMemoryStore())
    response, patient_id, encounter_id = write(
        service,
        make_event(),
        source=MemorySource.PATIENT_UPLOAD,
    )

    context = service.retrieve(
        MemoryRetrieveRequest(
            patient_id=patient_id,
            encounter_id=encounter_id,
            query_concepts=["hypertension"],
        )
    )

    assert context.verified_context.conditions == []
    assert [item.event_id for item in context.unverified_information] == [
        response.written_events[0].event_id
    ]
    assert context.unverified_information[0].trust_tier == TrustTier.UNVERIFIED


def test_unresolved_conflict_is_not_verified_and_is_returned():
    service = MemoryEngineService(store=InMemoryMemoryStore())
    patient_id = uuid4()
    encounter_id = uuid4()
    write(service, make_event(), patient_id=patient_id, encounter_id=encounter_id)
    write(
        service,
        make_event(status="inactive", assertion="negated"),
        patient_id=patient_id,
        encounter_id=encounter_id,
        source=MemorySource.PATIENT_UPLOAD,
    )

    context = service.retrieve(
        MemoryRetrieveRequest(
            patient_id=patient_id,
            encounter_id=encounter_id,
            query_concepts=["hypertension"],
        )
    )

    assert context.verified_context.conditions == []
    assert len(context.unverified_information) == 2
    assert len(context.conflicts) == 1


def test_patient_isolation_and_provenance_are_preserved():
    service = MemoryEngineService(store=InMemoryMemoryStore())
    patient_a = uuid4()
    patient_b = uuid4()
    encounter_a = uuid4()
    source_document_id = uuid4()
    written, _, _ = write(
        service,
        make_event(source_document_id=source_document_id),
        patient_id=patient_a,
        encounter_id=encounter_a,
    )
    write(
        service,
        make_event(source_document_id=uuid4()),
        patient_id=patient_b,
        encounter_id=uuid4(),
    )

    context = service.retrieve(
        MemoryRetrieveRequest(
            patient_id=patient_a,
            encounter_id=encounter_a,
            query_concepts=[],
        )
    )

    assert len(context.verified_context.conditions) == 1
    item = context.verified_context.conditions[0]
    assert item.event_id == written.written_events[0].event_id
    assert item.provenance.source_document_id == source_document_id
    assert item.provenance.source_event_id == service.get_events(patient_a).events[0].source_event_id


def test_retrieval_is_deterministic_for_same_store_and_query():
    service = MemoryEngineService(store=InMemoryMemoryStore())
    patient_id = uuid4()
    encounter_id = uuid4()
    write(service, make_event(concept="Hypertension"), patient_id=patient_id, encounter_id=encounter_id)
    write(service, make_event(concept="Diabetes", domain="endocrinology"), patient_id=patient_id, encounter_id=uuid4())

    request = MemoryRetrieveRequest(
        patient_id=patient_id,
        encounter_id=encounter_id,
        query_concepts=[],
    )
    first = service.retrieve(request)
    second = service.retrieve(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
