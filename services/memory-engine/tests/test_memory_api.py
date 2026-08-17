from uuid import uuid4

from fastapi.testclient import TestClient

from contracts.schemas import (
    ClinicalEventValidationStatus,
    InputModality,
    MemorySource,
    SourceTextSpan,
)
from services.memory_engine.app.main import create_app
from services.memory_engine.app.service import MemoryEngineService


def make_event(*, status="active", assertion="affirmed"):
    text = "Patient has Hypertension"
    return {
        "event_local_id": str(uuid4()),
        "original_text": text,
        "processed_text": text,
        "normalized_concept": "Hypertension",
        "snomed_ct_id": "38341003",
        "entity_type": "condition",
        "clinical_domain": "cardiology",
        "relationships": [],
        "assertion": assertion,
        "clinical_status": status,
        "temporal_context": "current",
        "temporal_date": None,
        "bioclinicalbert_confidence": 0.94,
        "gemini_contextualization_confidence": 0.90,
        "source_document_id": str(uuid4()),
        "source_text_span": {"start": 0, "end": len(text)},
        "input_modality": InputModality.TYPED.value,
        "source_language": "en",
        "translation_confidence": 1.0,
        "validation_status": ClinicalEventValidationStatus.VALID.value,
    }


def make_client():
    return TestClient(create_app(MemoryEngineService()))


def test_write_gate_and_memory_read_endpoints():
    client = make_client()
    patient_id = uuid4()
    encounter_id = uuid4()

    response = client.post(
        "/api/v1/step3/memory/events",
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "source": MemorySource.SIMULATED_ABHA.value,
            "clinical_events": [make_event()],
        },
    )

    assert response.status_code == 200
    body = response.json()
    event_id = body["written_events"][0]["event_id"]
    assert body["written_events"][0]["trust_tier"] == 1

    events = client.get(f"/api/v1/step3/memory/{patient_id}/events")
    assert events.status_code == 200
    assert len(events.json()["events"]) == 1
    assert events.json()["events"][0]["event_id"] == event_id

    state = client.get(f"/api/v1/step3/memory/{patient_id}/current-state")
    assert state.status_code == 200
    assert state.json()["concept_threads"][0]["event_count"] == 1


def test_retrieval_and_tier3_approval_api():
    client = make_client()
    patient_id = uuid4()
    encounter_id = uuid4()
    write = client.post(
        "/api/v1/step3/memory/events",
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "source": MemorySource.PATIENT_UPLOAD.value,
            "clinical_events": [make_event()],
        },
    )
    event_id = write.json()["written_events"][0]["event_id"]

    before = client.post(
        "/api/v1/step3/memory/retrieve",
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "query_concepts": ["hypertension"],
        },
    )
    assert before.status_code == 200
    assert before.json()["verified_context"]["conditions"] == []

    approved = client.post(
        f"/api/v1/step3/tier3/{event_id}/approve",
        json={"physician_id": "doctor-123"},
    )
    assert approved.status_code == 200
    assert approved.json()["new_trust_tier"] == 2

    after = client.post(
        "/api/v1/step3/memory/retrieve",
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "query_concepts": ["hypertension"],
        },
    )
    assert len(after.json()["verified_context"]["conditions"]) == 1


def test_conflict_and_resolution_api():
    client = make_client()
    patient_id = uuid4()
    encounter_id = uuid4()
    base = {
        "patient_id": str(patient_id),
        "encounter_id": str(encounter_id),
        "source": MemorySource.SIMULATED_ABHA.value,
    }
    first = dict(base, clinical_events=[make_event()])
    second = dict(
        base,
        source=MemorySource.PATIENT_UPLOAD.value,
        clinical_events=[make_event(status="inactive", assertion="negated")],
    )
    client.post("/api/v1/step3/memory/events", json=first)
    conflict_response = client.post("/api/v1/step3/memory/events", json=second)
    assert conflict_response.json()["conflicts_detected"]

    conflicts = client.get(
        "/api/v1/step3/conflicts",
        params={"patient_id": str(patient_id), "status": "unresolved"},
    )
    assert conflicts.status_code == 200
    conflict_id = conflicts.json()[0]["conflict_id"]

    resolved = client.post(
        f"/api/v1/step3/conflicts/{conflict_id}/resolve",
        json={
            "resolution_action": "confirm_event_a",
            "physician_id": "doctor-123",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
