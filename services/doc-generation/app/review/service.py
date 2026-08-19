"""Physician review and finalization state transitions."""

from datetime import datetime, timezone
from uuid import UUID

from contracts.schemas import (
    DocumentProvenanceEntry,
    DocumentReviewResponse,
    DocumentStatus,
    FinalizeDocumentRequest,
    GeneratedDocument,
    ReviewAction,
)

from ..context import ContextAssembler, PromptBuilder
from ..feedback import FeedbackCollector, MemoryWriteClient, build_memory_write_payload
from ..generation import DocumentGenerator
from ..repository import DocumentRecord, DocumentRepository
from ..validation import DocumentValidator


class DocumentNotFoundError(LookupError):
    pass


class DocumentReviewError(ValueError):
    pass


class MemoryWriteHandoffError(RuntimeError):
    pass


class DocumentReviewService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        generator: DocumentGenerator,
        context_assembler: ContextAssembler,
        prompt_builder: PromptBuilder,
        validator: DocumentValidator,
        memory_write_client: MemoryWriteClient | None = None,
        feedback_collector: FeedbackCollector | None = None,
        generate_document,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.context_assembler = context_assembler
        self.prompt_builder = prompt_builder
        self.validator = validator
        self.memory_write_client = memory_write_client
        self.feedback_collector = feedback_collector
        self.generate_document = generate_document

    def finalize(
        self,
        *,
        document_id: UUID,
        request: FinalizeDocumentRequest,
    ) -> DocumentReviewResponse:
        record = self.repository.get(document_id)
        if record is None:
            raise DocumentNotFoundError(str(document_id))
        if record.document.status == DocumentStatus.FINALIZED:
            raise DocumentReviewError("Document is already finalized.")

        if request.action == ReviewAction.REJECT_REGENERATE:
            regenerated = self.generate_document(
                record.request.model_copy(
                    update={
                        "physician_instructions": request.regenerate_notes
                        or record.request.physician_instructions
                    }
                )
            )
            regenerated.flags_for_physician_review.append(
                # Pydantic models are mutable by design for this internal review result.
                self._regeneration_flag(request.physician_id)
            )
            regenerated = regenerated.model_copy(
                update={"flags_for_physician_review": regenerated.flags_for_physician_review}
            )
            self._add_review(record, request, regenerated.document_id)
            stored = self.repository.get(regenerated.document_id)
            if stored is not None:
                stored.review_history.append(
                    {"action": request.action.value, "physician_id": request.physician_id}
                )
                self.repository.update(stored)
            return DocumentReviewResponse(
                document_id=regenerated.document_id,
                status=DocumentStatus.DRAFT,
                document=regenerated,
            )

        reviewed_document = record.document
        if request.action == ReviewAction.EDIT and request.edited_sections is not None:
            reviewed_document = self._apply_edit(reviewed_document, request)

        if request.action == ReviewAction.EDIT:
            context = self.context_assembler.assemble(
                patient_id=record.request.patient_id,
                encounter_id=record.request.encounter_id,
                current_events=list(record.request.current_consultation_events),
                retrieved_context=record.request.retrieved_context,
            )
            validation = self.validator.validate(reviewed_document, context)
            if not validation.passed:
                raise DocumentReviewError(
                    "Edited document failed deterministic safety validation."
                )
            reviewed_document = reviewed_document.model_copy(
                update={"validation_result": validation}
            )

        if not reviewed_document.validation_result.passed:
            raise DocumentReviewError(
                "Document cannot be finalized until validation failures are resolved."
            )

        payload = build_memory_write_payload(
            record.request,
            actor_id=request.physician_id,
        )
        self._submit_memory_payload(payload)
        finalized = reviewed_document.model_copy(
            update={
                "status": DocumentStatus.FINALIZED,
                "finalized_at": datetime.now(timezone.utc),
            }
        )
        record.document = finalized
        self._add_review(record, request, finalized.document_id)
        self.repository.update(record)
        return DocumentReviewResponse(
            document_id=finalized.document_id,
            status=DocumentStatus.FINALIZED,
            finalized_at=finalized.finalized_at,
            memory_write_payload=payload,
        )

    @staticmethod
    def _apply_edit(document: GeneratedDocument, request: FinalizeDocumentRequest) -> GeneratedDocument:
        edited = request.edited_sections
        if edited is None:
            return document
        updates = {
            field: getattr(edited, field)
            for field in edited.model_fields_set
        }
        sections = document.sections.model_copy(update=updates)
        provenance = [
            entry.model_copy(
                update={
                    "generated_text": getattr(sections, entry.section) or entry.generated_text,
                    "source_kind": "physician_edit",
                }
            )
            for entry in document.provenance_map
        ]
        return document.model_copy(
            update={"sections": sections, "provenance_map": provenance}
        )

    @staticmethod
    def _regeneration_flag(physician_id: str):
        from contracts.schemas import DocumentReviewFlag

        return DocumentReviewFlag(
            code="REGENERATED_AFTER_REJECTION",
            message=f"Draft regenerated after physician review by {physician_id}.",
            severity="info",
        )

    def _add_review(
        self,
        record: DocumentRecord,
        request: FinalizeDocumentRequest,
        document_id: UUID,
    ) -> None:
        record.review_history.append(
            {
                "action": request.action.value,
                "physician_id": request.physician_id,
                "document_id": str(document_id),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if self.feedback_collector is not None:
            self.feedback_collector.record(
                document_id=document_id,
                action=request.action.value,
                physician_id=request.physician_id,
                notes=request.regenerate_notes,
            )

    def _submit_memory_payload(self, payload) -> None:
        if self.memory_write_client is None:
            return
        try:
            self.memory_write_client.submit(payload)
        except Exception as exc:  # pragma: no cover - adapter-specific failures
            raise MemoryWriteHandoffError(
                "Step 3 memory_write_payload handoff failed; document remains a draft."
            ) from exc


__all__ = [
    "DocumentNotFoundError",
    "DocumentReviewError",
    "DocumentReviewService",
    "MemoryWriteHandoffError",
]
