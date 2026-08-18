"""Optional integration coverage against the configured PostgreSQL database."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from database.models import Patient, PatientAssignment
from services.gateway.app.auth.model import User
from services.gateway.app.database import SessionLocal, check_database_connection
from services.gateway.app.main import create_app


def test_registration_login_and_patient_access_persist_in_postgres():
    try:
        check_database_connection()
    except Exception as exc:
        pytest.skip(f"Configured PostgreSQL is unavailable: {type(exc).__name__}")

    suffix = uuid4().hex
    physician_email = f"integration-physician-{suffix}@example.com"
    other_email = f"integration-other-{suffix}@example.com"
    patient_email = f"integration-patient-{suffix}@example.com"
    password = "integration-password-123"
    client = TestClient(create_app())
    created_patient_ids: list[UUID] = []

    try:
        physician = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Integration Physician", "email": physician_email, "password": password},
        )
        patient = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Integration Patient", "email": patient_email, "password": password, "role": "patient"},
        )
        other = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Other Physician", "email": other_email, "password": password},
        )
        assert physician.status_code == 201
        assert patient.status_code == 201
        assert other.status_code == 201

        patient_id = UUID(patient.json()["patient_id"])
        created_patient_ids.append(patient_id)
        physician_headers = _login(client, physician_email, password)
        other_headers = _login(client, other_email, password)
        patient_headers = _login(client, patient_email, password)

        me = client.get("/api/v1/auth/me", headers=patient_headers)
        assert me.status_code == 200
        assert UUID(me.json()["patient_id"]) == patient_id

        created_for_physician = client.post(
            "/api/v1/patients",
            headers=physician_headers,
            json={"display_name": "Assigned Integration Patient"},
        )
        assert created_for_physician.status_code == 200
        assigned_patient_id = UUID(created_for_physician.json()["patient_id"])
        created_patient_ids.append(assigned_patient_id)

        allowed = client.get(f"/api/v1/patients/{assigned_patient_id}", headers=physician_headers)
        denied = client.get(f"/api/v1/patients/{assigned_patient_id}", headers=other_headers)
        assert allowed.status_code == 200
        assert denied.status_code == 403

        # A fresh SQLAlchemy session verifies the identifier and assignment
        # survive the request/session boundary (and therefore a backend restart).
        with SessionLocal() as db:
            persisted = db.query(Patient).filter(Patient.id == assigned_patient_id).first()
            assignment = db.query(PatientAssignment).filter(PatientAssignment.patient_id == assigned_patient_id).first()
            assert persisted is not None
            assert assignment is not None
            assert assignment.status == "active"
    finally:
        _cleanup(physician_email, other_email, patient_email, created_patient_ids=created_patient_ids)


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _cleanup(*emails: str, created_patient_ids: list[UUID]) -> None:
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.in_(emails)).all()
        user_ids = [user.id for user in users]
        patient_rows = db.query(Patient).filter(Patient.user_id.in_(user_ids)).all() if user_ids else []
        for created_patient_id in created_patient_ids:
            assigned = db.query(Patient).filter(Patient.id == created_patient_id).first()
            if assigned is not None:
                patient_rows.append(assigned)
        for patient in {row.id: row for row in patient_rows}.values():
            db.delete(patient)
        for user in users:
            db.delete(user)
        db.commit()
