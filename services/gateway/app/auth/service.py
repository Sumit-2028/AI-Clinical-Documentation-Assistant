from sqlalchemy.orm import Session
from uuid import UUID

from .model import User
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    REFRESH_TOKEN_TYPE,
    refresh_token_replay_store,
    TokenValidationError,
    verify_password,
)


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    user = (
        db.query(User)
        .filter(User.email == email.strip().lower())
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
