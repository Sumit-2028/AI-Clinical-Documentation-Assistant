"""Authenticated end-to-end coverage for the composed backend pipeline."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from contracts.schemas import DocumentStatus, DocumentType, MemorySource
from services.gateway.app.auth.model import User
from services.gateway.app.auth.security import hash_password
from services.gateway.app.database import get_db
from services.gateway.app.main import create_app
from services.doc_generation.app.repository import (
    DocumentRecord,
    SqlAlchemyDocumentRepository,
)


class FakeQuery:
    def __init__(self, users):
        self.users = list(users)

    def filter(self, expression):
        field_name = expression.left.name
        expected_value = expression.right.value
        self.users = [
            user
            for user in self.users
            if getattr(user, field_name) == expected_value
        ]
        return self

    def first(self):
        return self.users[0] if self.users else None


class FakeSession:
    def __init__(self, users):
        self.users = users

    def query(self, model):
        return FakeQuery(self.users)


def make_user(*, email: str, role: str = "physician") -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Integration Physician" if role == "physician" else "Integration Reviewer",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )


def make_client():
    physician = make_user(email="doctor@example.com")
    reviewer = make_user(email="reviewer@example.com", role="reviewer")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeSession([physician, reviewer])
    return TestClient(app), app, physician, reviewer


def login(client, email: str):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_complete_authenticated_pipeline_reaches_the_single_memory_write_gate():
    client, app, physician, _ = make_client()
    headers = login(client, physician.email)
    patient_id = uuid4()
    encounter_id = uuid4()

    assert client.get("/api/v1/auth/me").status_code == 401
    unauthorized = client.post(
        "/api/v1/step1/documents/typed",
        data={"patient_id": str(patient_id), "encounter_id": str(encounter_id)},
        files={"file": ("note.txt", b"Patient has hypertension.", "text/plain")},
    )
    assert unauthorized.status_code == 401

    step1 = client.post(
        "/api/v1/step1/documents/typed",
        headers=headers,
        data={"patient_id": str(patient_id), "encounter_id": str(encounter_id)},
        files={"file": ("note.txt", b"Patient has hypertension.", "text/plain")},
    )
    assert step1.status_code == 200
    step1_body = step1.json()
    assert step1_body["processing_status"] == "complete"
    assert step1_body["audit_log_id"]

    step2 = client.post(
        "/api/v1/step2/process",
        headers=headers,
        json={
            "document_id": step1_body["document_id"],
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "step1_output": step1_body,
        },
    )
    assert step2.status_code == 200
    step2_body = step2.json()
    assert step2_body["clinical_events"]
    clinical_event = step2_body["clinical_events"][0]
    assert clinical_event["source_document_id"] == step1_body["document_id"]
    assert clinical_event["validation_status"] == "valid"

    step3 = client.post(
        "/api/v1/step3/memory/events",
        headers=headers,
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "source": MemorySource.PATIENT_UPLOAD.value,
            "clinical_events": step2_body["clinical_events"],
        },
    )
    assert step3.status_code == 200
    step3_body = step3.json()
    assert step3_body["written_events"]
    assert step3_body["written_events"][0]["trust_tier"] == 3

    retrieved = client.post(
        "/api/v1/step3/memory/retrieve",
        headers=headers,
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "query_concepts": ["hypertension"],
        },
    )
    assert retrieved.status_code == 200
    retrieved_body = retrieved.json()
    assert retrieved_body["verified_context"]["conditions"] == []
    assert len(retrieved_body["unverified_information"]) == 1
    assert retrieved_body["unverified_information"][0]["provenance"][
        "source_document_id"
    ] == step1_body["document_id"]

    generated = client.post(
        "/api/v1/step4/documents/generate",
        headers=headers,
        json={
            "patient_id": str(patient_id),
            "encounter_id": str(encounter_id),
            "document_type": "soap_note",
            "current_consultation_events": step2_body["clinical_events"],
            "retrieved_context": retrieved_body,
        },
    )
    assert generated.status_code == 200
    generated_body = generated.json()
    assert generated_body["status"] == "draft"
    assert generated_body["validation_result"]["passed"] is True
    assert generated_body["provenance_map"]

    finalized = client.post(
        f"/api/v1/step4/documents/{generated_body['document_id']}/finalize",
        headers=headers,
        json={"action": "accept", "physician_id": str(physician.id)},
    )
    assert finalized.status_code == 200
    finalized_body = finalized.json()
    assert finalized_body["status"] == "finalized"
    assert finalized_body["memory_write_payload"]["source"] == (
        MemorySource.PHYSICIAN_APPROVED_CONSULTATION.value
    )

    stored = client.get(
        f"/api/v1/step3/memory/{patient_id}/events",
        headers=headers,
    )
    assert stored.status_code == 200
    stored_events = stored.json()["events"]
    approved_events = [
        event
        for event in stored_events
        if event["source"] == MemorySource.PHYSICIAN_APPROVED_CONSULTATION.value
    ]
    assert len(approved_events) == 1
    assert approved_events[0]["provenance"]["source_document_id"] == step1_body[
        "document_id"
    ]
    assert approved_events[0]["provenance"]["source_event_id"] == clinical_event[
        "event_local_id"
    ]
    assert len(app.state.memory_engine_service.store.list_events(patient_id)) == 2


def test_gateway_authorization_patient_isolation_and_conflict_behavior():
    client, _, physician, reviewer = make_client()
    physician_headers = login(client, physician.email)
    reviewer_headers = login(client, reviewer.email)
    patient_a = uuid4()
    patient_b = uuid4()
    encounter_id = uuid4()

    denied_write = client.post(
        "/api/v1/step1/documents/typed",
        headers=reviewer_headers,
        data={"patient_id": str(patient_a), "encounter_id": str(encounter_id)},
        files={"file": ("note.txt", b"Patient has hypertension.", "text/plain")},
    )
    assert denied_write.status_code == 403

    step1 = client.post(
        "/api/v1/step1/documents/typed",
        headers=physician_headers,
        data={"patient_id": str(patient_a), "encounter_id": str(encounter_id)},
        files={"file": ("note.txt", b"Patient has hypertension.", "text/plain")},
    ).json()
    events = client.post(
        "/api/v1/step2/process",
        headers=physician_headers,
        json={
            "document_id": step1["document_id"],
            "patient_id": str(patient_a),
            "encounter_id": str(encounter_id),
            "step1_output": step1,
        },
    ).json()["clinical_events"]

    first = client.post(
        "/api/v1/step3/memory/events",
        headers=physician_headers,
        json={
            "patient_id": str(patient_a),
            "encounter_id": str(encounter_id),
            "source": MemorySource.SIMULATED_ABHA.value,
            "clinical_events": events,
        },
    )
    assert first.status_code == 200

    contradictory = [
        {
            **event,
            "event_local_id": str(uuid4()),
            "assertion": "negated",
            "clinical_status": "inactive",
        }
        for event in events
    ]
    conflict = client.post(
        "/api/v1/step3/memory/events",
        headers=physician_headers,
        json={
            "patient_id": str(patient_a),
            "encounter_id": str(encounter_id),
            "source": MemorySource.PATIENT_UPLOAD.value,
            "clinical_events": contradictory,
        },
    )
    assert conflict.status_code == 200
    assert conflict.json()["conflicts_detected"]

    isolated = client.post(
        "/api/v1/step3/memory/retrieve",
        headers=physician_headers,
        json={
            "patient_id": str(patient_b),
            "encounter_id": encounter_id.__str__(),
            "query_concepts": ["hypertension"],
        },
    )
    assert isolated.status_code == 200
    assert isolated.json() == {
        "verified_context": {
            "conditions": [],
            "medications": [],
            "allergies": [],
            "procedures": [],
            "lab_trends": [],
            "significant_events": [],
        },
        "unverified_information": [],
        "conflicts": [],
    }

    conflicts = client.get(
        "/api/v1/step3/conflicts",
        headers=reviewer_headers,
        params={"patient_id": str(patient_a), "status": "unresolved"},
    )
    assert conflicts.status_code == 200
    assert len(conflicts.json()) == 1


def test_gateway_mounts_all_existing_pipeline_contract_paths():
    client, app, _, _ = make_client()
    expected_paths = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/me",
        "/api/v1/step1/documents/typed",
        "/api/v1/step1/documents/handwritten",
        "/api/v1/step1/documents/multilingual",
        "/api/v1/step1/documents/{document_id}",
        "/api/v1/step1/documents/{document_id}/human-verify",
        "/api/v1/step2/process",
        "/api/v1/step2/process/{document_id}",
        "/api/v1/step3/memory/events",
        "/api/v1/step3/memory/{patient_id}/events",
        "/api/v1/step3/memory/{patient_id}/current-state",
        "/api/v1/step3/memory/retrieve",
        "/api/v1/step3/conflicts",
        "/api/v1/step3/conflicts/{conflict_id}/resolve",
        "/api/v1/step3/tier3/{event_id}/approve",
        "/api/v1/step3/tier3/{event_id}/reject",
        "/api/v1/step4/documents/generate",
        "/api/v1/step4/documents/{document_id}/finalize",
    }

    assert expected_paths <= set(app.openapi()["paths"])
    assert client.get("/api/v1/step3/conflicts").status_code == 401


class FailingCommitSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.rollback_count = 0

    def add(self, value):
        return None

    def query(self, model):
        return self

    def filter(self, expression):
        return self

    def first(self):
        return self.existing

    def commit(self):
        raise RuntimeError("database transaction failed")

    def rollback(self):
        self.rollback_count += 1


def make_document_record():
    patient_id = uuid4()
    encounter_id = uuid4()
    document_id = uuid4()
    document = SimpleNamespace(
        document_id=document_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        document_type=DocumentType.SOAP_NOTE,
        status=DocumentStatus.DRAFT,
        generated_at=datetime.now(timezone.utc),
        finalized_at=None,
        model_dump=lambda mode="json": {"document_id": str(document_id)},
    )
    request = SimpleNamespace(model_dump=lambda mode="json": {})
    return DocumentRecord(document=document, request=request, prompt="prompt")


def test_durable_document_repository_rolls_back_create_and_update_failures():
    record = make_document_record()
    create_session = FailingCommitSession()

    with pytest.raises(RuntimeError, match="database transaction failed"):
        SqlAlchemyDocumentRepository(create_session).create(record)
    assert create_session.rollback_count == 1

    existing_row = SimpleNamespace(
        status="draft",
        content={},
        finalized_at=None,
    )
    update_session = FailingCommitSession(existing=existing_row)
    with pytest.raises(RuntimeError, match="database transaction failed"):
        SqlAlchemyDocumentRepository(update_session).update(record)
    assert update_session.rollback_count == 1
