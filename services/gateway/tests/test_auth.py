from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.gateway.app.auth.dependencies import (
    require_permissions,
    require_roles,
)
from services.gateway.app.auth.model import User
from services.gateway.app.auth.rbac import Permission, Role, has_permission
from services.gateway.app.auth.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from services.gateway.app.database import get_db
from services.gateway.app.main import create_app


class FakeQuery:
    def __init__(self, users: list[User]) -> None:
        self.users = users

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
    def __init__(self, users: list[User]) -> None:
        self.users = users

    def query(self, model):
        return FakeQuery(self.users)


def make_user(
    *,
    email: str = "doctor@example.com",
    password: str = "password123",
    role: str = "physician",
    is_active: bool = True,
) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Demo Physician",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )


@pytest.fixture
def auth_client():
    user = make_user()
    db = FakeSession([user])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


def test_valid_login_returns_distinct_access_and_refresh_tokens(auth_client):
    client, user = auth_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_token(body["access_token"], expected_type=ACCESS_TOKEN_TYPE)["sub"] == str(
        user.id
    )
    assert decode_token(
        body["refresh_token"], expected_type=REFRESH_TOKEN_TYPE
    )["sub"] == str(user.id)
    assert body["access_token"] != body["refresh_token"]


def test_invalid_password_is_rejected(auth_client):
    client, user = auth_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_unknown_user_is_rejected(auth_client):
    client, _ = auth_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "password123"},
    )

    assert response.status_code == 401


def test_inactive_user_is_rejected():
    user = make_user(is_active=False)
    db = FakeSession([user])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "password123"},
        )

    assert response.status_code == 401


def test_access_token_validation_and_me_endpoint(auth_client):
    client, user = auth_client
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    ).json()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "full_name": "Demo Physician",
        "role": "physician",
        "is_active": True,
    }


def test_missing_or_expired_access_token_is_rejected(auth_client):
    client, user = auth_client

    assert client.get("/api/v1/auth/me").status_code == 401

    expired_token = create_access_token(
        str(user.id),
        expires_delta=timedelta(seconds=-1),
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_refresh_token_returns_new_token_pair(auth_client):
    client, user = auth_client
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    ).json()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert decode_token(body["access_token"], expected_type=ACCESS_TOKEN_TYPE)
    assert decode_token(body["refresh_token"], expected_type=REFRESH_TOKEN_TYPE)
    assert body["refresh_token"] != login["refresh_token"]


def test_invalid_refresh_token_and_access_token_are_rejected(auth_client):
    client, user = auth_client
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    ).json()

    for token in ["not-a-jwt", login["access_token"]]:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )
        assert response.status_code == 401


def test_role_and_permission_checks():
    physician = SimpleNamespace(role=Role.PHYSICIAN.value)
    reviewer = SimpleNamespace(role=Role.REVIEWER.value)

    assert has_permission(physician, Permission.MEMORY_WRITE)
    assert not has_permission(reviewer, Permission.MEMORY_WRITE)

    physician_only = require_roles(Role.PHYSICIAN)
    assert physician_only(physician) is physician
    with pytest.raises(HTTPException) as role_error:
        physician_only(reviewer)
    assert role_error.value.status_code == 403

    write_documents = require_permissions(Permission.DOCUMENTS_WRITE)
    assert write_documents(physician) is physician
    with pytest.raises(HTTPException) as permission_error:
        write_documents(reviewer)
    assert permission_error.value.status_code == 403


def test_token_types_are_enforced():
    access_token = create_access_token(str(uuid4()))
    refresh_token = create_refresh_token(str(uuid4()))

    with pytest.raises(ValueError):
        decode_token(access_token, expected_type=REFRESH_TOKEN_TYPE)
    with pytest.raises(ValueError):
        decode_token(refresh_token, expected_type=ACCESS_TOKEN_TYPE)
