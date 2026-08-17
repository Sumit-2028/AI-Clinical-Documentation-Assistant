from enum import StrEnum
from typing import Any


class Role(StrEnum):
    ADMIN = "admin"
    PHYSICIAN = "physician"
    REVIEWER = "reviewer"
    NURSE = "nurse"
    PATIENT = "patient"


class Permission(StrEnum):
    AUTH_ME = "auth:me"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    PATIENTS_READ = "patients:read"
    PATIENTS_WRITE = "patients:write"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    DOCUMENTS_REVIEW = "documents:review"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"


ALL_PERMISSIONS = frozenset(permission.value for permission in Permission)

ROLE_PERMISSIONS = {
    Role.ADMIN.value: ALL_PERMISSIONS,
    Role.PHYSICIAN.value: frozenset(
        {
            Permission.AUTH_ME.value,
            Permission.PATIENTS_READ.value,
            Permission.PATIENTS_WRITE.value,
            Permission.DOCUMENTS_READ.value,
            Permission.DOCUMENTS_WRITE.value,
            Permission.DOCUMENTS_REVIEW.value,
            Permission.MEMORY_READ.value,
            Permission.MEMORY_WRITE.value,
        }
    ),
    Role.REVIEWER.value: frozenset(
        {
            Permission.AUTH_ME.value,
            Permission.PATIENTS_READ.value,
            Permission.DOCUMENTS_READ.value,
            Permission.DOCUMENTS_REVIEW.value,
            Permission.MEMORY_READ.value,
        }
    ),
    Role.NURSE.value: frozenset(
        {
            Permission.AUTH_ME.value,
            Permission.PATIENTS_READ.value,
            Permission.PATIENTS_WRITE.value,
            Permission.DOCUMENTS_READ.value,
            Permission.DOCUMENTS_WRITE.value,
            Permission.MEMORY_READ.value,
        }
    ),
    Role.PATIENT.value: frozenset(
        {
            Permission.AUTH_ME.value,
            Permission.PATIENTS_READ.value,
            Permission.DOCUMENTS_READ.value,
        }
    ),
}


def _role_value(user_or_role: Any) -> str:
    role = getattr(user_or_role, "role", user_or_role)
    return role.value if hasattr(role, "value") else str(role)


def has_role(user_or_role: Any, role: str | Role) -> bool:
    expected_role = role.value if hasattr(role, "value") else role
    return _role_value(user_or_role) == expected_role


def has_permission(user_or_role: Any, permission: str | Permission) -> bool:
    permission_value = permission.value if hasattr(permission, "value") else permission
    role = _role_value(user_or_role)
    if role == Role.ADMIN.value:
        return True
    return permission_value in ROLE_PERMISSIONS.get(role, frozenset())


def permissions_for_role(role: str | Role) -> frozenset[str]:
    role_value = role.value if hasattr(role, "value") else role
    return ROLE_PERMISSIONS.get(role_value, frozenset())
