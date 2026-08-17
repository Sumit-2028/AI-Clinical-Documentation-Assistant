"""Clinical documentation generation orchestration."""

from contracts.schemas import (
    ClinicalEventValidationStatus,
    DocumentValidationResult,
    GenerateDocumentRequest,
    GeneratedDocument,
)
from services.ai_adapters import AIProviderError

from .context import ContextAssembler, PromptBuilder, PromptInjectionError
from .feedback import FeedbackCollector, MemoryWriteClient
from .generation import (
    DeterministicMockGenerator,
    DocumentGenerator,
    GeneratorUnavailableError,
    build_document_generator,
)
from .repository import DocumentRecord, DocumentRepository, InMemoryDocumentRepository
from .review import DocumentReviewService
from .templates import TemplateRegistry
from .validation import DocumentValidator


class DocumentGenerationError(ValueError):
    pass


class DocumentService:
    def __init__(
        self,
        *,
        repository: DocumentRepository | None = None,
        generator: DocumentGenerator | None = None,
        memory_write_client: MemoryWriteClient | None = None,
    ) -> None:
        self.repository = repository or InMemoryDocumentRepository()
        self.generator = generator or build_document_generator()
        self.memory_write_client = memory_write_client
        self.feedback_collector = FeedbackCollector()
        self.context_assembler = ContextAssembler()
        self.prompt_builder = PromptBuilder()
        self.validator = DocumentValidator()
        self.review_service = DocumentReviewService(
            repository=self.repository,
            generator=self.generator,
            context_assembler=self.context_assembler,
            prompt_builder=self.prompt_builder,
            validator=self.validator,
            memory_write_client=memory_write_client,
            feedback_collector=self.feedback_collector,
            generate_document=self.generate,
        )

    def generate(self, request: GenerateDocumentRequest) -> GeneratedDocument:
        invalid_events = [
            event.event_local_id
            for event in request.current_consultation_events
            if event.validation_status != ClinicalEventValidationStatus.VALID
        ]
        if invalid_events:
            raise DocumentGenerationError("Cannot generate from invalid clinical events.")

        context = self.context_assembler.assemble(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            current_events=request.current_consultation_events,
            retrieved_context=request.retrieved_context,
        )
        try:
            prompt = self.prompt_builder.build(
                context,
                document_type=request.document_type,
                physician_instructions=request.physician_instructions,
            )
        except PromptInjectionError as exc:
            raise DocumentGenerationError(
                "Physician instructions were rejected by prompt safety policy."
            ) from exc
        try:
            draft = self.generator.generate(
                context,
                document_type=request.document_type,
                physician_instructions=request.physician_instructions,
            )
        except GeneratorUnavailableError as exc:
            raise DocumentGenerationError(
                "Documentation generation provider is unavailable."
            ) from exc
        except AIProviderError as exc:
            raise DocumentGenerationError(
                "Documentation generation provider failed safely."
            ) from exc

        document = GeneratedDocument(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            document_type=request.document_type,
            sections=draft.sections,
            flags_for_physician_review=list(draft.flags),
            provenance_map=list(draft.provenance_map),
            validation_result=DocumentValidationResult(
                passed=True,
                failures=[],
                auto_regeneration_attempts=0,
            ),
            generator=draft.generator,
        )
        validation = self.validator.validate(document, context)
        document = document.model_copy(update={"validation_result": validation})
        self.repository.create(
            DocumentRecord(
                document=document,
                request=request,
                prompt=prompt,
            )
        )
        return document

    def finalize(self, document_id, request):
        return self.review_service.finalize(
            document_id=document_id,
            request=request,
        )

    def get(self, document_id):
        record = self.repository.get(document_id)
        return record.document if record else None


DocumentGenerationService = DocumentService


__all__ = ["DocumentGenerationError", "DocumentGenerationService", "DocumentService"]
