"""PostgreSQL acceptance coverage for shared patient memory across clinicians."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from database.models import Patient
from services.gateway.app.auth.security import hash_password
from services.gateway.app.auth.model import User
from services.gateway.app.database import SessionLocal, check_database_connection
from services.gateway.app.integration import build_integrated_services
from services.gateway.app.main import create_app


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        + f"5 0 obj << /Length {len(stream)} >> stream\n".encode()
        + stream
        + b"\nendstream endobj\n%%EOF\n"
    )


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _process_report(
    client: TestClient,
    headers: dict[str, str],
    *,
    patient_id: str,
    encounter_id: str,
    text: str,
) -> list[dict]:
    step1 = client.post(
        "/api/v1/step1/documents/typed",
        headers=headers,
        data={"patient_id": patient_id, "encounter_id": encounter_id},
        files={"file": ("report.pdf", _pdf(text), "application/pdf")},
    )
    assert step1.status_code == 200
    step1_body = step1.json()

    step2 = client.post(
        "/api/v1/step2/process",
        headers=headers,
        json={
            "document_id": step1_body["document_id"],
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "step1_output": step1_body,
        },
    )
    assert step2.status_code == 200
    events = step2.json()["clinical_events"]

    step3 = client.post(
        "/api/v1/step3/memory/events",
        headers=headers,
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "source": "patient_upload",
            "clinical_events": events,
        },
    )
    assert step3.status_code == 200
    return events


def test_authorized_clinicians_share_postgres_longitudinal_memory(monkeypatch):
    try:
        check_database_connection()
    except Exception as exc:
        pytest.skip(f"Configured PostgreSQL is unavailable: {type(exc).__name__}")

    for name in ("STEP1_AI_MODE", "STEP2_NLP_MODE", "STEP4_LLM_MODE"):
        monkeypatch.setenv(name, "mock")

    suffix = uuid4().hex
    password = "multi-clinician-password-123"
    clinician_a_email = f"clinician-a-{suffix}@example.com"
    clinician_b_email = f"clinician-b-{suffix}@example.com"
    admin_email = f"admin-{suffix}@example.com"
    client = TestClient(create_app(build_integrated_services(persistent=True)))
    user_ids = []
    patient_id = None

    try:
        for email, role in (
            (clinician_a_email, "physician"),
            (clinician_b_email, "physician"),
        ):
            response = client.post(
                "/api/v1/auth/register",
                json={"full_name": email.split("@")[0], "email": email, "password": password, "role": role},
            )
            assert response.status_code == 201
            user_ids.append(response.json()["id"])

        with SessionLocal() as db:
            admin = User(
                email=admin_email,
                full_name="Integration Admin",
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            user_ids.append(str(admin.id))

        clinician_a = _login(client, clinician_a_email, password)
        clinician_b = _login(client, clinician_b_email, password)
        admin_headers = _login(client, admin_email, password)

        created = client.post(
            "/api/v1/patients",
            headers=clinician_a,
            json={"display_name": "Shared Longitudinal Patient"},
        )
        assert created.status_code == 200
        patient_id = created.json()["patient_id"]
        assert patient_id.isdigit()
        assert 6 <= len(patient_id) <= 8

        with SessionLocal() as db:
            clinician_b_row = db.query(User).filter(User.email == clinician_b_email).one()
            clinician_b_id = str(clinician_b_row.id)

        assigned = client.post(
            f"/api/v1/patients/{patient_id}/assignments",
            headers=admin_headers,
            json={"physician_id": clinician_b_id},
        )
        assert assigned.status_code == 200

        first_encounter = str(uuid4())
        second_encounter = str(uuid4())
        _process_report(
            client,
            clinician_a,
            patient_id=patient_id,
            encounter_id=first_encounter,
            text="Patient has hypertension and takes amlodipine.",
        )
        _process_report(
            client,
            clinician_b,
            patient_id=patient_id,
            encounter_id=second_encounter,
            text="Patient has diabetes and takes metformin.",
        )

        retrieved = client.post(
            "/api/v1/step3/memory/retrieve",
            headers=clinician_b,
            json={
                "patient_id": patient_id,
                "encounter_id": second_encounter,
                "query_concepts": ["hypertension", "diabetes", "amlodipine", "metformin"],
            },
        )
        assert retrieved.status_code == 200
        body = retrieved.json()
        surfaced = body["unverified_information"] + body["verified_context"]["conditions"]
        concepts = {
            str(item.get("normalized_concept", "")).casefold()
            for item in surfaced
        }
        assert "hypertension" in concepts
        assert any("diabetes" in concept for concept in concepts)
    finally:
        with SessionLocal() as db:
            if patient_id is not None:
                patient = db.query(Patient).filter(Patient.public_patient_id == int(patient_id)).first()
                if patient is not None:
                    db.delete(patient)
            users = db.query(User).filter(User.email.in_([clinician_a_email, clinician_b_email, admin_email])).all()
            for user in users:
                db.delete(user)
            db.commit()
