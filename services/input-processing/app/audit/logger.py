from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol
from uuid import UUID, uuid4


_SENSITIVE_DETAIL_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "content",
    "document_text",
    "medical_text",
    "text_input",
}


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    def clean(value: Any, *, key: str | None = None) -> Any:
        if key is not None and key.casefold() in _SENSITIVE_DETAIL_KEYS:
            return "[redacted]"
        if isinstance(value, dict):
            return {
                str(item_key): clean(item_value, key=str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value]
        if isinstance(value, str) and len(value) > 256:
            return value[:256] + "…"
        return value

    return clean(details or {})


@dataclass(frozen=True)
class AuditEvent:
    audit_log_id: UUID
    document_id: UUID
    action: str
    actor_id: str | None
    details: dict[str, Any]
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class AuditLogger(Protocol):
    def record(
        self,
        document_id: UUID,
        action: str,
        *,
        actor_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        ...


class InMemoryAuditLogger:
    """Development audit sink; replace with an append-only durable sink later."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self,
        document_id: UUID,
        action: str,
        *,
        actor_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            audit_log_id=uuid4(),
            document_id=document_id,
            action=action,
            actor_id=actor_id,
            details=_safe_details(details),
        )
        with self._lock:
            self._events.append(event)
        return event

    def list_for_document(self, document_id: UUID) -> list[AuditEvent]:
        with self._lock:
            return [event for event in self._events if event.document_id == document_id]


class SqlAlchemyAuditLogger:
    """Durable append-only audit logger using the shared audit_logs table."""

    def __init__(self, db) -> None:
        self.db = db

    def record(
        self,
        document_id: UUID,
        action: str,
        *,
        actor_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        from database.models import AuditLog

        event = AuditEvent(
            audit_log_id=uuid4(),
            document_id=document_id,
            action=action,
            actor_id=actor_id,
            details=_safe_details(details),
        )
        try:
            self.db.add(
                AuditLog(
                    id=event.audit_log_id,
                    action=action,
                    entity_type="step1_document",
                    entity_id=document_id,
                    metadata_={
                        "actor_id": actor_id,
                        **_safe_details(details),
                    },
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return event
