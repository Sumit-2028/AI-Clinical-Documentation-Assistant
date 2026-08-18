from uuid import uuid4

from fastapi.testclient import TestClient

from app.audit import InMemoryAuditLogger
from app.main import create_app
from app.repository import InMemoryDocumentRepository
from app.service import InputProcessingService


def make_client():
    service = InputProcessingService(
        repository=InMemoryDocumentRepository(),
        audit_logger=InMemoryAuditLogger(),
    )
    return TestClient(create_app(service))


def test_typed_endpoint_and_get_endpoint():
    client = make_client()
    patient_id = uuid4()
    encounter_id = uuid4()

    response = client.post(
        "/api/v1/step1/documents/typed",
        data={"patient_id": str(patient_id), "encounter_id": str(encounter_id)},
        files={"file": ("report.txt", b"Patient has hypertension", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["input_modality"] == "typed"
    assert body["processing_status"] == "complete"

    get_response = client.get(f"/api/v1/step1/documents/{body['document_id']}")
    assert get_response.status_code == 200
    assert get_response.json() == body


def test_handwritten_endpoint_and_human_verification_endpoint():
    client = make_client()
    response = client.post(
        "/api/v1/step1/documents/handwritten",
        data={"patient_id": str(uuid4()), "encounter_id": str(uuid4())},
        # Declared as text so the deterministic OCR mock, which decodes the
        # upload as UTF-8, still yields extractable fields.  Content signature
        # validation rejects text bytes labelled as an image.
        files={"file": ("note.txt", b"Patient has penicillin allergy", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "pending_human_verification"
    field_id = body["extracted_fields"][0]["field_id"]

    verified = client.post(
        f"/api/v1/step1/documents/{body['document_id']}/human-verify",
        json={
            "field_id": field_id,
            "verified_text": "Confirmed penicillin allergy",
            "reviewer_id": "doctor-123",
            "approved": True,
        },
    )

    assert verified.status_code == 200
    assert verified.json()["processing_status"] == "complete"
    assert verified.json()["verification_state"] == "verified"


def test_multilingual_endpoint_and_missing_document_error():
    client = make_client()
    response = client.post(
        "/api/v1/step1/documents/multilingual",
        json={
            "patient_id": str(uuid4()),
            "encounter_id": str(uuid4()),
            "text_input": "Patient has fever",
            "source_language": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["input_modality"] == "multilingual"
    assert response.json()["translation_confidence"] == 1.0

    missing = client.get(f"/api/v1/step1/documents/{uuid4()}")
    assert missing.status_code == 404


def test_invalid_multilingual_request_is_rejected():
    client = make_client()

    response = client.post(
        "/api/v1/step1/documents/multilingual",
        json={"text_input": "missing identifiers"},
    )

    assert response.status_code == 422
