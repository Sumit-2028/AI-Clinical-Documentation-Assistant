"""Registration and patient-authorization coverage without requiring a live DB."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from database.models import Patient, PatientAssignment
from services.gateway.app.auth.model import User
from services.gateway.app.auth.security import hash_password
from services.gateway.app.database import get_db
from services.gateway.app.main import create_app


class Query:
    def __init__(self, values):
        self.values = list(values)

    def filter(self, expression):
        field_name = expression.left.name
        expected_value = expression.right.value
        if field_name == "lower":
            field_name = next(iter(expression.left.clauses)).name
            self.values = [value for value in self.values if str(getattr(value, field_name)).lower() == expected_value]
        else:
            self.values = [value for value in self.values if getattr(value, field_name) == expected_value]
        return self

    def first(self):
        return self.values[0] if self.values else None


class Session:
    def __init__(self, users=None):
        self.users = list(users or [])
        self.patients = []
        self.assignments = []
        self.rollback_count = 0

    def query(self, model):
        if model is User:
            return Query(self.users)
        if model is Patient:
            return Query(self.patients)
        if model is PatientAssignment:
            return Query(self.assignments)
        raise AssertionError(f"Unexpected model queried: {model}")

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        if isinstance(value, User):
            self.users.append(value)
        elif isinstance(value, Patient):
            self.patients.append(value)
        elif isinstance(value, PatientAssignment):
            self.assignments.append(value)
        else:
            raise AssertionError(f"Unexpected model added: {value}")

    def flush(self):
        for value in [*self.users, *self.patients, *self.assignments]:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    def commit(self):
        return None

    def rollback(self):
        self.rollback_count += 1


def user(email: str, role: str = "physician") -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Existing Physician",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )


def client_with_db(*users):
    db = Session(users)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), db


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_patient_registration_hashes_password_and_returns_stable_patient_id():
    client, db = client_with_db()
    registered = client.post(
        "/api/v1/auth/register",
        json={"full_name": "  Patient Example ", "email": " PATIENT@Example.COM ", "password": "password123", "role": "patient"},
    )

    assert registered.status_code == 201
    body = registered.json()
    patient_id = UUID(body["patient_id"])
    created_user = db.users[0]
    assert created_user.email == "patient@example.com"
    assert created_user.password_hash != "password123"
    assert db.patients[0].id == patient_id
    assert db.patients[0].user_id == created_user.id

    headers = login(client, "patient@example.com")
    first_me = client.get("/api/v1/auth/me", headers=headers).json()
    second_me = client.get("/api/v1/auth/me", headers=headers).json()
    assert first_me["patient_id"] == str(patient_id)
    assert second_me["patient_id"] == str(patient_id)
    assert len({patient.id for patient in db.patients}) == 1


def test_registration_rejects_duplicate_email_and_privileged_role():
    existing = user("doctor@example.com")
    client, _ = client_with_db(existing)

    duplicate = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Another Doctor", "email": "DOCTOR@example.com", "password": "password123"},
    )
    assert duplicate.status_code == 409

    privileged = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Administrator", "email": "admin@example.com", "password": "password123", "role": "admin"},
    )
    assert privileged.status_code == 422


def test_physician_can_create_and_lookup_assigned_patient_but_other_physician_cannot():
    doctor = user("doctor@example.com")
    other_doctor = user("other@example.com")
    client, db = client_with_db(doctor, other_doctor)
    doctor_headers = login(client, doctor.email)
    other_headers = login(client, other_doctor.email)

    created = client.post(
        "/api/v1/patients",
        headers=doctor_headers,
        json={"display_name": "Assigned Patient"},
    )
    assert created.status_code == 200
    patient_id = created.json()["patient_id"]
    assert len(db.assignments) == 1
    assert db.assignments[0].physician_id == doctor.id

    allowed = client.get(f"/api/v1/patients/{patient_id}", headers=doctor_headers)
    denied = client.get(f"/api/v1/patients/{patient_id}", headers=other_headers)
    assert allowed.status_code == 200
    assert allowed.json()["patient_id"] == patient_id
    assert denied.status_code == 403


def test_registration_rolls_back_when_commit_fails():
    from services.gateway.app.auth.service import register_user

    class FailingSession(Session):
        def commit(self):
            raise RuntimeError("commit failed")

    db = FailingSession()
    with pytest.raises(RuntimeError, match="commit failed"):
        register_user(db, email="rollback@example.com", full_name="Rollback User", password="password123")
    assert db.rollback_count == 1
