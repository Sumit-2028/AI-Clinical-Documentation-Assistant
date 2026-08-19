from threading import Lock
from typing import Protocol
from uuid import UUID

from contracts.schemas import Step1Output
from services.object_storage import StoredObject


class EncounterPatientMismatchError(ValueError):
    """Raised when an existing encounter belongs to another patient."""


class DocumentRepository(Protocol):
    def save(self, output: Step1Output) -> Step1Output:
        ...

    def get(self, document_id: UUID) -> Step1Output | None:
        ...

    def validate_encounter(self, *, patient_id: UUID, encounter_id: UUID) -> None:
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

    def validate_encounter(self, *, patient_id: UUID, encounter_id: UUID) -> None:
        return None

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
        from database.models import DocumentRecord, Encounter, ExtractionResult, ProcessingJob

        try:
            encounter = self.db.query(Encounter).filter(Encounter.id == output.encounter_id).first()
            if encounter is None:
                self.db.add(
                    Encounter(
                        id=output.encounter_id,
                        patient_id=output.patient_id,
                        status="active",
                    )
                )
                # There are intentionally no ORM relationships on the shared
                # foundation models; flush the parent explicitly before the
                # document row is inserted to satisfy the FK in PostgreSQL.
                self.db.flush()
            elif encounter.patient_id != output.patient_id:
                raise EncounterPatientMismatchError(
                    "Encounter does not belong to the requested patient."
                )
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

    def validate_encounter(self, *, patient_id: UUID, encounter_id: UUID) -> None:
        from database.models import Encounter

        encounter = self.db.query(Encounter).filter(Encounter.id == encounter_id).first()
        if encounter is not None and encounter.patient_id != patient_id:
            raise EncounterPatientMismatchError(
                "Encounter does not belong to the requested patient."
            )

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


class SessionScopedSqlAlchemyDocumentRepository:
    """Open a short-lived database session for each repository operation."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def save(self, output: Step1Output) -> Step1Output:
        with self.session_factory() as db:
            return SqlAlchemyDocumentRepository(db).save(output)

    def get(self, document_id: UUID) -> Step1Output | None:
        with self.session_factory() as db:
            return SqlAlchemyDocumentRepository(db).get(document_id)

    def validate_encounter(self, *, patient_id: UUID, encounter_id: UUID) -> None:
        with self.session_factory() as db:
            SqlAlchemyDocumentRepository(db).validate_encounter(
                patient_id=patient_id,
                encounter_id=encounter_id,
            )

    def record_source_object(self, document_id: UUID, stored: StoredObject) -> None:
        with self.session_factory() as db:
            SqlAlchemyDocumentRepository(db).record_source_object(document_id, stored)

    def get_source_object(self, document_id: UUID) -> StoredObject | None:
        with self.session_factory() as db:
            return SqlAlchemyDocumentRepository(db).get_source_object(document_id)


__all__ = [
    "DocumentRepository",
    "EncounterPatientMismatchError",
    "InMemoryDocumentRepository",
    "SessionScopedSqlAlchemyDocumentRepository",
    "SqlAlchemyDocumentRepository",
]
