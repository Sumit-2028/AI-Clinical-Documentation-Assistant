"""Document persistence adapters; generation never writes clinical memory here."""

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from contracts.schemas import GenerateDocumentRequest, GeneratedDocument


@dataclass
class DocumentRecord:
    document: GeneratedDocument
    request: GenerateDocumentRequest
    prompt: str
    review_history: list[dict] = field(default_factory=list)


class DocumentRepository(Protocol):
    def create(self, record: DocumentRecord) -> DocumentRecord: ...

    def get(self, document_id: UUID) -> DocumentRecord | None: ...

    def update(self, record: DocumentRecord) -> DocumentRecord: ...


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, DocumentRecord] = {}
        self._lock = RLock()

    def create(self, record: DocumentRecord) -> DocumentRecord:
        with self._lock:
            if record.document.document_id in self._records:
                raise ValueError(f"Document {record.document.document_id} already exists.")
            self._records[record.document.document_id] = record
        return record

    def get(self, document_id: UUID) -> DocumentRecord | None:
        with self._lock:
            return self._records.get(document_id)

    def update(self, record: DocumentRecord) -> DocumentRecord:
        with self._lock:
            if record.document.document_id not in self._records:
                raise KeyError(str(record.document.document_id))
            self._records[record.document.document_id] = record
        return record


class SqlAlchemyDocumentRepository:
    """Durable adapter using the existing generated_documents table."""

    def __init__(self, db) -> None:
        self.db = db

    def create(self, record: DocumentRecord) -> DocumentRecord:
        from database.models import GeneratedDocumentRecord as GeneratedDocumentRow

        try:
            self.db.add(
                GeneratedDocumentRow(
                    id=record.document.document_id,
                    patient_id=record.document.patient_id,
                    encounter_id=record.document.encounter_id,
                    document_type=record.document.document_type.value,
                    status=record.document.status.value,
                    content=self._content(record),
                    generated_at=record.document.generated_at,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return record

    def get(self, document_id: UUID) -> DocumentRecord | None:
        from database.models import GeneratedDocumentRecord as GeneratedDocumentRow

        row = self.db.query(GeneratedDocumentRow).filter(
            GeneratedDocumentRow.id == document_id
        ).first()
        if row is None:
            return None
        return self._record(row.content)

    def update(self, record: DocumentRecord) -> DocumentRecord:
        from database.models import GeneratedDocumentRecord as GeneratedDocumentRow

        row = self.db.query(GeneratedDocumentRow).filter(
            GeneratedDocumentRow.id == record.document.document_id
        ).first()
        if row is None:
            raise KeyError(str(record.document.document_id))
        try:
            row.status = record.document.status.value
            row.content = self._content(record)
            row.finalized_at = record.document.finalized_at
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return record

    @staticmethod
    def _content(record: DocumentRecord) -> dict:
        return {
            "document": record.document.model_dump(mode="json"),
            "request": record.request.model_dump(mode="json"),
            "prompt": record.prompt,
            "review_history": record.review_history,
        }

    @staticmethod
    def _record(content: dict) -> DocumentRecord:
        return DocumentRecord(
            document=GeneratedDocument.model_validate(content["document"]),
            request=GenerateDocumentRequest.model_validate(content["request"]),
            prompt=content.get("prompt", ""),
            review_history=content.get("review_history", []),
        )


__all__ = [
    "DocumentRecord",
    "DocumentRepository",
    "InMemoryDocumentRepository",
    "SqlAlchemyDocumentRepository",
]
