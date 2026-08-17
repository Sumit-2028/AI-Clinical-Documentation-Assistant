from fastapi.testclient import TestClient

from contracts.schemas import MemoryWriteRequest
from services.doc_generation.app.main import create_app
from services.doc_generation.app.service import DocumentService

from .test_doc_generation import make_context, make_event


def test_generate_and_finalize_api_contract():
    client = TestClient(create_app(DocumentService()))
    request = {
        "patient_id": "11111111-1111-4111-8111-111111111111",
        "encounter_id": "22222222-2222-4222-8222-222222222222",
        "document_type": "soap_note",
        "current_consultation_events": [make_event().model_dump(mode="json")],
        "retrieved_context": make_context().model_dump(mode="json"),
        "physician_instructions": None,
    }

    generated = client.post("/api/v1/step4/documents/generate", json=request)

    assert generated.status_code == 200
    generated_body = generated.json()
    assert generated_body["status"] == "draft"
    assert generated_body["validation_result"]["passed"] is True
    document_id = generated_body["document_id"]

    finalized = client.post(
        f"/api/v1/step4/documents/{document_id}/finalize",
        json={"action": "accept", "physician_id": "doctor-123"},
    )

    assert finalized.status_code == 200
    body = finalized.json()
    assert body["status"] == "finalized"
    payload = MemoryWriteRequest.model_validate(body["memory_write_payload"])
    assert payload.source.value == "physician_approved_consultation"
    assert len(payload.clinical_events) == 1


def test_finalize_unknown_document_is_not_silently_created():
    client = TestClient(create_app(DocumentService()))
    response = client.post(
        "/api/v1/step4/documents/33333333-3333-4333-8333-333333333333/finalize",
        json={"action": "accept", "physician_id": "doctor-123"},
    )

    assert response.status_code == 404
