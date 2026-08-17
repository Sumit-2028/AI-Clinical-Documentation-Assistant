"""Collect physician review feedback without changing clinical memory directly."""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID


@dataclass(frozen=True)
class FeedbackRecord:
    document_id: UUID
    action: str
    physician_id: str
    notes: str | None
    created_at: datetime


class FeedbackCollector:
    def __init__(self) -> None:
        self._records: list[FeedbackRecord] = []
        self._lock = RLock()

    def record(
        self,
        *,
        document_id: UUID,
        action: str,
        physician_id: str,
        notes: str | None = None,
    ) -> FeedbackRecord:
        feedback = FeedbackRecord(
            document_id=document_id,
            action=action,
            physician_id=physician_id,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._records.append(feedback)
        return feedback

    def list(self, document_id: UUID | None = None) -> list[FeedbackRecord]:
        with self._lock:
            records = list(self._records)
        return (
            [record for record in records if record.document_id == document_id]
            if document_id is not None
            else records
        )


__all__ = ["FeedbackCollector", "FeedbackRecord"]
