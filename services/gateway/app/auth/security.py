from datetime import datetime, timedelta, timezone
from threading import RLock
import time
from typing import Any
from uuid import UUID, uuid4

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from ..config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
MAX_PASSWORD_LENGTH = 1024


class TokenValidationError(ValueError):
    """Raised when a JWT cannot be trusted for the requested operation."""


class RefreshTokenReplayStore:
    """Single-process replay guard for rotated refresh tokens.

    A multi-replica deployment should back this same interface with a shared
    store. The local guard still prevents accidental replay in development and
    single-process deployments without adding infrastructure.
    """

    def __init__(self) -> None:
        self._used_until: dict[str, float] = {}
        self._lock = RLock()

    def consume(self, payload: dict[str, Any]) -> bool:
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not isinstance(jti, str) or not jti or not isinstance(exp, (int, float)):
            return False
        now = time.time()
        with self._lock:
            expired = [token_id for token_id, expiry in self._used_until.items() if expiry <= now]
            for token_id in expired:
                self._used_until.pop(token_id, None)
            if jti in self._used_until:
                return False
            self._used_until[jti] = float(exp)
            return True


refresh_token_replay_store = RefreshTokenReplayStore()


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password exceeds the maximum supported length.")
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    if not isinstance(plain_password, str) or len(plain_password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return pwd_context.verify(plain_password, password_hash)
    except (ValueError, TypeError):
        # A malformed stored hash must fail authentication, not crash the API.
        return False


def _create_token(
    user_id: str | UUID,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + expires_delta,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    user_id: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    return _create_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(
    user_id: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    return _create_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(
    token: str,
    *,
    expected_type: str | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT, including its application token type."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise TokenValidationError("Token has expired.") from exc
    except (JWTError, TypeError, ValueError) as exc:
        raise TokenValidationError("Token is invalid.") from exc

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not isinstance(subject, str) or not subject:
        raise TokenValidationError("Token subject is missing.")

    token_id = payload.get("jti")
    if not isinstance(token_id, str) or not token_id:
        raise TokenValidationError("Token identifier is missing.")

    issued_at = payload.get("iat")
    if not isinstance(issued_at, (int, float)):
        raise TokenValidationError("Token issue time is missing.")

    if token_type not in {ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE}:
        raise TokenValidationError("Token type is invalid.")

    if expected_type is not None and token_type != expected_type:
        raise TokenValidationError("Token type is not valid for this operation.")

    # python-jose validates exp when present. Requiring it prevents accepting
    # unsigned-by-policy, non-expiring application tokens.
    if "exp" not in payload:
        raise TokenValidationError("Token expiration is missing.")

    return payload
