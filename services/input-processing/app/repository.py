from threading import Lock
from typing import Protocol
from uuid import UUID

from contracts.schemas import Step1Output
from services.object_storage import StoredObject


class DocumentRepository(Protocol):
    def save(self, output: Step1Output) -> Step1Output:
        ...

    def get(self, document_id: UUID) -> Step1Output | None:
        ...

    def record_source_object(self, document_id: UUID, stored: StoredObject) -> None:
        """Associate a document with the stored bytes it was extracted from.

        Implementations added after ``save``/``get``; callers reach it through
        ``getattr`` so older repository doubles keep working.
        """
        ...

    def get_source_object(self, document_id: UUID) -> StoredObject | None:
        ...


class InMemoryDocumentRepository:
    """Thread-safe local repository used by the standalone Step 1 service."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Step1Output] = {}
        self._source_objects: dict[UUID, StoredObject] = {}
        self._lock = Lock()

    def save(self, output: Step1Output) -> Step1Output:
        with self._lock:
            self._documents[output.document_id] = output
        return output

    def get(self, document_id: UUID) -> Step1Output | None:
        with self._lock:
            return self._documents.get(document_id)

    def record_source_object(self, document_id: UUID, stored: StoredObject) -> None:
        with self._lock:
            self._source_objects[document_id] = stored

    def get_source_object(self, document_id: UUID) -> StoredObject | None:
        with self._lock:
            return self._source_objects.get(document_id)


class SqlAlchemyDocumentRepository:
    """Durable repository backed by the shared document/extraction tables."""

    def __init__(self, db) -> None:
        self.db = db

    def save(self, output: Step1Output) -> Step1Output:
        from database.models import DocumentRecord, ExtractionResult, ProcessingJob

        try:
            document = (
                self.db.query(DocumentRecord)
                .filter(DocumentRecord.id == output.document_id)
                .first()
            )
            if document is None:
                document = DocumentRecord(
                    id=output.document_id,
                    patient_id=output.patient_id,
                    encounter_id=output.encounter_id,
                    input_modality=output.input_modality.value,
                    source_language=output.source_language,
                    status=output.processing_status.value,
                )
                self.db.add(document)
            else:
                document.status = output.processing_status.value
                document.source_language = output.source_language

            extraction = (
                self.db.query(ExtractionResult)
                .filter(ExtractionResult.document_id == output.document_id)
                .first()
            )
            payload = output.model_dump(mode="json")
            confidence_values = [
                field.extraction_confidence for field in output.extracted_fields
            ]
            if extraction is None:
                extraction = ExtractionResult(
                    document_id=output.document_id,
                    field_payload=payload,
                    confidence=(
                        min(confidence_values) if confidence_values else None
                    ),
                    requires_review=any(
                        field.requires_doctor_review_before_memory_write
                        for field in output.extracted_fields
                    ),
                )
                self.db.add(extraction)
            else:
                extraction.field_payload = payload
                extraction.confidence = (
                    min(confidence_values) if confidence_values else None
                )
                extraction.requires_review = any(
                    field.requires_doctor_review_before_memory_write
                    for field in output.extracted_fields
                )

            job = (
                self.db.query(ProcessingJob)
                .filter(ProcessingJob.document_id == output.document_id)
                .filter(ProcessingJob.step == "step1")
                .first()
            )
            if job is None:
                self.db.add(
                    ProcessingJob(
                        document_id=output.document_id,
                        step="step1",
                        status=output.processing_status.value,
                    )
                )
            else:
                job.status = output.processing_status.value

            self.db.commit()
            return output
        except Exception:
            self.db.rollback()
            raise

    def get(self, document_id: UUID) -> Step1Output | None:
        from database.models import ExtractionResult

        extraction = (
            self.db.query(ExtractionResult)
            .filter(ExtractionResult.document_id == document_id)
            .order_by(ExtractionResult.created_at.desc())
            .first()
        )
        if extraction is None:
            return None
        return Step1Output.model_validate(extraction.field_payload)

    def record_source_object(self, document_id: UUID, stored: StoredObject) -> None:
        from database.models import DocumentRecord

        try:
            document = (
                self.db.query(DocumentRecord)
                .filter(DocumentRecord.id == document_id)
                .first()
            )
            if document is None:
                return
            document.storage_uri = stored.storage_uri
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_source_object(self, document_id: UUID) -> StoredObject | None:
        from database.models import DocumentRecord

        document = (
            self.db.query(DocumentRecord)
            .filter(DocumentRecord.id == document_id)
            .first()
        )
        if document is None or not document.storage_uri:
            return None

        bucket, _, key = document.storage_uri.removeprefix("s3://").partition("/")
        # Content type and size are authoritative in the object store; a head
        # request fills them in when the caller needs them.
        return StoredObject(
            key=key,
            bucket=bucket,
            storage_uri=document.storage_uri,
            content_type="",
            size_bytes=0,
            checksum_sha256="",
        )
