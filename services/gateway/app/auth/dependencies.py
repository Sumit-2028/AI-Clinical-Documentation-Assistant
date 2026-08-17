from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db

from .model import User
from .security import (
    ACCESS_TOKEN_TYPE,
    TokenValidationError,
    decode_token,
)


bearer_scheme = HTTPBearer(auto_error=False)
# Compatibility name for future routes that prefer OAuth-style terminology.
oauth2_scheme = bearer_scheme


def _unauthorized(detail: str = "Could not validate credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Insufficient permissions.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Extract and validate an access token from the Authorization header."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        return decode_token(
            credentials.credentials,
            expected_type=ACCESS_TOKEN_TYPE,
        )
    except TokenValidationError as exc:
        raise _unauthorized(str(exc)) from exc


def _find_user(db: Session, user_id: str) -> User | None:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return None

    return db.query(User).filter(User.id == parsed_user_id).first()


def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user = _find_user(db, payload["sub"])

    if user is None or not user.is_active:
        raise _unauthorized("User is not authorized.")

    return user


# Explicit alias for routes that want to communicate the active-user policy.
get_current_active_user = get_current_user


def require_roles(*roles: str) -> Callable[..., User]:
    allowed_roles = {role.value if hasattr(role, "value") else role for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise _forbidden("Required role is missing.")
        return current_user

    return dependency


def require_permissions(*permissions: str) -> Callable[..., User]:
    from .rbac import has_permission

    required_permissions = {
        permission.value if hasattr(permission, "value") else permission
        for permission in permissions
    }

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not all(
            has_permission(current_user, permission)
            for permission in required_permissions
        ):
            raise _forbidden("Required permission is missing.")
        return current_user

    return dependency


# Singular aliases make the dependency ergonomic for one-policy routes.
require_role = require_roles
require_permission = require_permissions


def require_pipeline_access(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """Authorize the mounted pipeline routes by operation and resource.

    Service applications remain independently testable and unprotected when
    run alone.  When mounted by the gateway, this dependency is applied to
    every pipeline route and maps the existing RBAC permissions to the exact
    contract operation.
    """

    from .rbac import Permission, has_permission

    path = request.url.path
    method = request.method.upper()
    required_permission = _pipeline_permission(path, method)
    if required_permission is None:
        return current_user
    if not has_permission(current_user, required_permission):
        raise _forbidden("Required permission is missing.")
    return current_user


def _pipeline_permission(path: str, method: str):
    from .rbac import Permission

    if "/step1/" in path:
        if method == "GET":
            return Permission.DOCUMENTS_READ
        if path.endswith("/human-verify"):
            return Permission.DOCUMENTS_REVIEW
        return Permission.DOCUMENTS_WRITE

    if "/step2/" in path:
        return Permission.DOCUMENTS_READ if method == "GET" else Permission.DOCUMENTS_WRITE

    if "/step3/" in path:
        if method == "GET" or path.endswith("/retrieve"):
            return Permission.MEMORY_READ
        if "/resolve" in path or "/tier3/" in path:
            return Permission.MEMORY_WRITE
        return Permission.MEMORY_WRITE

    if "/step4/" in path:
        if path.endswith("/finalize"):
            return Permission.DOCUMENTS_REVIEW
        return Permission.DOCUMENTS_WRITE

    return None
