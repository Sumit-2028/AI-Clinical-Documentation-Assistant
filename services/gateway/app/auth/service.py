from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from database.models import Patient

from .model import User
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    REFRESH_TOKEN_TYPE,
    refresh_token_replay_store,
    TokenValidationError,
    hash_password,
    verify_password,
)


class DuplicateEmailError(ValueError):
    """Raised when registration would violate the unique email constraint."""


class RegistrationRoleError(ValueError):
    """Raised when a public registration requests a privileged role."""


PUBLIC_REGISTRATION_ROLES = frozenset({"physician", "patient"})


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    role: str = "physician",
) -> User:
    """Create a user and any role-required patient profile atomically."""

    normalized_email = normalize_email(email)
    clean_name = " ".join(full_name.split())
    if role not in PUBLIC_REGISTRATION_ROLES:
        raise RegistrationRoleError("This role cannot be created through public registration.")

    existing = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing is not None:
        raise DuplicateEmailError("An account with this email already exists.")

    user = User(
        email=normalized_email,
        full_name=clean_name,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )

    try:
        db.add(user)
        db.flush()
        if role == "patient":
            db.add(Patient(user_id=user.id, display_name=clean_name))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEmailError("An account with this email already exists.") from exc
    except Exception:
        db.rollback()
        raise

    return user


def patient_id_for_user(db: Session, user_id: UUID) -> UUID | None:
    """Return the durable patient profile linked to a user, if one exists."""

    try:
        patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    except AttributeError:
        # Lightweight auth test sessions may only implement the users table.
        return None
    return patient.id if patient is not None else None


def user_response_data(db: Session, user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "patient_id": patient_id_for_user(db, user.id),
    }


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    user = (
        db.query(User)
        .filter(User.email == normalize_email(email))
        .first()
    )

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user


def get_user_by_id(db: Session, user_id: str) -> User | None:
    try:
        parsed_user_id = UUID(user_id)
    except (TypeError, ValueError):
        return None

    return db.query(User).filter(User.id == parsed_user_id).first()


def issue_tokens(user: User) -> dict[str, str]:
    return {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


def login_user(
    db: Session,
    email: str,
    password: str,
):
    user = authenticate_user(
        db,
        email,
        password,
    )

    if not user:
        return None

    return issue_tokens(user)


def refresh_user_tokens(
    db: Session,
    refresh_token: str,
) -> dict[str, str] | None:
    try:
        payload = decode_token(
            refresh_token,
            expected_type=REFRESH_TOKEN_TYPE,
        )
    except TokenValidationError:
        return None

    user = get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        return None

    if not refresh_token_replay_store.consume(payload):
        return None

    # Rotate the refresh token on every successful refresh. Token storage and
    # revocation can be added later without changing this endpoint contract.
    return issue_tokens(user)
