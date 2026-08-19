from collections.abc import Callable
import json
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
from ..patients.service import (
    PatientAccessDeniedError,
    PatientNotFoundError,
    get_patient_by_identifier,
    require_patient_access,
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
        # Do not disclose whether a token was malformed, expired, or signed
        # with the wrong key to an unauthenticated caller.
        raise _unauthorized() from exc


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


def _resolve_patient_identifier(db: Session, raw_patient_id: str | None) -> UUID | None:
    if raw_patient_id is None:
        return None
    try:
        return UUID(str(raw_patient_id))
    except ValueError:
        try:
            return get_patient_by_identifier(db, str(raw_patient_id)).id
        except PatientNotFoundError:
            return None


async def _patient_id_from_request(request: Request, db: Session) -> UUID | None:
    """Extract a patient identity without trusting frontend-only state."""

    path_patient_id = request.path_params.get("patient_id")
    if path_patient_id:
        return _resolve_patient_identifier(db, str(path_patient_id))

    query_patient_id = request.query_params.get("patient_id")
    if query_patient_id:
        return _resolve_patient_identifier(db, query_patient_id)

    content_type = request.headers.get("content-type", "").casefold()
    if request.method.upper() not in {"POST", "PUT", "PATCH"}:
        return None

    try:
        if content_type.startswith("multipart/"):
            form = await request.form()
            raw_patient_id = form.get("patient_id")
        elif "application/json" in content_type:
            body = await request.body()
            payload = json.loads(body.decode("utf-8")) if body else {}
            raw_patient_id = payload.get("patient_id") if isinstance(payload, dict) else None
        else:
            raw_patient_id = None
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    if raw_patient_id is None:
        return None
    return _resolve_patient_identifier(db, str(raw_patient_id))


def _patient_id_from_resource(request: Request) -> UUID | None:
    """Resolve ownership for resource paths that do not carry patient_id."""

    path = request.url.path
    resource_id = request.path_params.get("document_id")
    if resource_id:
        try:
            parsed_id = UUID(str(resource_id))
        except ValueError:
            return None
        try:
            if "/step1/" in path:
                output = request.app.state.step1_service.get_document(parsed_id)
                return output.patient_id
            if "/step2/" in path:
                batch = request.app.state.clinical_nlp_service.get(parsed_id)
                return batch.patient_id
            if "/step4/" in path:
                document = request.app.state.document_service.get(parsed_id)
                return document.patient_id if document is not None else None
        except Exception:
            return None

    resource_id = request.path_params.get("conflict_id")
    if resource_id:
        try:
            conflict = request.app.state.memory_engine_service.store.get_conflict(UUID(str(resource_id)))
            return conflict.patient_id if conflict is not None else None
        except (AttributeError, ValueError):
            return None

    resource_id = request.path_params.get("event_id")
    if resource_id:
        try:
            event = request.app.state.memory_engine_service.store.get_event(UUID(str(resource_id)))
            return event.patient_id if event is not None else None
        except (AttributeError, ValueError):
            return None

    return None


async def _resolve_pipeline_patient_id(request: Request, db: Session) -> UUID | None:
    return await _patient_id_from_request(request, db) or _patient_id_from_resource(request)


async def require_pipeline_access(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    request.state.current_user_id = str(current_user.id)
    required_permission = _pipeline_permission(path, method)
    if required_permission is None:
        return current_user
    if not has_permission(current_user, required_permission):
        raise _forbidden("Required permission is missing.")

    patient_id = await _resolve_pipeline_patient_id(request, db)
    if patient_id is not None:
        request.state.internal_patient_id = patient_id
    if patient_id is None:
        if path.endswith("/step3/conflicts") and method == "GET" and current_user.role != "admin":
            raise _forbidden("A patient_id filter is required for conflict access.")
        # Let the endpoint's own validation/not-found behavior handle routes
        # whose resource has not been created yet.
        return current_user

    try:
        require_patient_access(db, current_user, patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.") from exc
    except PatientAccessDeniedError as exc:
        raise _forbidden("Patient access is not permitted.") from exc
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
