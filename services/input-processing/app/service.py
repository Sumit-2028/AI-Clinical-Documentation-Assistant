from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contracts.schemas import (
    ConfidenceTier,
    DualRunResult,
    ExtractedField,
    InputModality,
    ProcessingStatus,
    Step1Output,
    VerificationState,
)

from .adapters import AdapterBundle, build_adapter_bundle
from .audit import AuditLogger, InMemoryAuditLogger
from .confidence import ConfidenceScorer, decide_confidence_gate
from .gating.service import apply_document_gate, replace_field
from .preprocessing import (
    decode_uploaded_text,
    is_high_risk,
    normalize_text,
    split_into_candidate_fields,
)
from .repository import DocumentRepository, InMemoryDocumentRepository


class DocumentNotFoundError(LookupError):
    pass


class FieldNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ExtractionRun:
    text: str
    confidence: float
    second_pass_text: str | None = None
    second_pass_confidence: float | None = None
    dual_run_triggered: bool = False
    dual_run_agreement: bool | None = None


class InputProcessingService:
    def __init__(
        self,
        *,
        repository: DocumentRepository | None = None,
        audit_logger: AuditLogger | None = None,
        adapters: AdapterBundle | None = None,
    ) -> None:
        self.repository = repository or InMemoryDocumentRepository()
        self.audit_logger = audit_logger or InMemoryAuditLogger()
        self.adapters = adapters or build_adapter_bundle()

    def process_typed(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        content: bytes,
        filename: str | None = None,
    ) -> Step1Output:
        document_id = uuid4()
        audit_event = self.audit_logger.record(
            document_id,
            "step1.processing_started",
            details={"input_modality": InputModality.TYPED.value},
        )

        try:
            text = decode_uploaded_text(content)
            run = ExtractionRun(text=text, confidence=0.97)
            return self._complete_run(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.TYPED,
                source_language="en",
                original_language_text=None,
                translation_confidence=1.0,
                run=run,
                ocr_engine_used=None,
                vlm_model_used=None,
            )
        except Exception as exc:
            return self._failed_output(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.TYPED,
                source_language="en",
                original_language_text=None,
                translation_confidence=1.0,
                ocr_engine_used=None,
                vlm_model_used=None,
                error=exc,
            )

    def process_handwritten(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        content: bytes,
        filename: str | None = None,
    ) -> Step1Output:
        document_id = uuid4()
        audit_event = self.audit_logger.record(
            document_id,
            "step1.processing_started",
            details={"input_modality": InputModality.HANDWRITTEN.value},
        )

        try:
            ocr_result = self.adapters.ocr.extract(content, filename=filename)
            text = normalize_text(ocr_result.text)
            vlm_result = None
            if ocr_result.confidence < 0.90:
                vlm_result = self.adapters.vlm.analyze(
                    content,
                    ocr_text=text,
                    filename=filename,
                )

            if vlm_result is not None and vlm_result.text:
                final_text = normalize_text(vlm_result.text)
                final_confidence = ConfidenceScorer.score(
                    ocr_result.confidence,
                    vlm_result.confidence,
                )
                dual_run = ExtractionRun(
                    text=final_text,
                    confidence=final_confidence,
                    second_pass_text=normalize_text(vlm_result.text),
                    second_pass_confidence=vlm_result.confidence,
                    dual_run_triggered=True,
                    dual_run_agreement=(
                        normalize_text(ocr_result.text).casefold()
                        == normalize_text(vlm_result.text).casefold()
                    ),
                )
            else:
                dual_run = ExtractionRun(
                    text=text,
                    confidence=ocr_result.confidence,
                )

            return self._complete_run(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.HANDWRITTEN,
                source_language="en",
                original_language_text=None,
                translation_confidence=1.0,
                run=dual_run,
                ocr_engine_used=ocr_result.engine,
                vlm_model_used=vlm_result.model if vlm_result else None,
            )
        except Exception as exc:
            return self._failed_output(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.HANDWRITTEN,
                source_language="en",
                original_language_text=None,
                translation_confidence=1.0,
                ocr_engine_used=getattr(self.adapters.ocr, "engine_name", None),
                vlm_model_used=getattr(self.adapters.vlm, "model_name", None),
                error=exc,
            )

    def process_multilingual(
        self,
        *,
        patient_id: UUID,
        encounter_id: UUID,
        text_input: str,
        source_language: str,
    ) -> Step1Output:
        document_id = uuid4()
        audit_event = self.audit_logger.record(
            document_id,
            "step1.processing_started",
            details={
                "input_modality": InputModality.MULTILINGUAL.value,
                "source_language": source_language,
            },
        )

        try:
            original_text = normalize_text(text_input)
            translation = self.adapters.translation.translate(
                original_text,
                source_language=source_language,
            )
            run = ExtractionRun(
                text=normalize_text(translation.translated_text),
                confidence=translation.confidence,
            )
            return self._complete_run(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.MULTILINGUAL,
                source_language=source_language,
                original_language_text=original_text,
                translation_confidence=translation.confidence,
                run=run,
                ocr_engine_used=None,
                vlm_model_used=None,
            )
        except Exception as exc:
            return self._failed_output(
                document_id=document_id,
                audit_log_id=audit_event.audit_log_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                modality=InputModality.MULTILINGUAL,
                source_language=source_language,
                original_language_text=normalize_text(text_input),
                translation_confidence=0.0,
                ocr_engine_used=None,
                vlm_model_used=None,
                error=exc,
            )

    def get_document(self, document_id: UUID) -> Step1Output:
        output = self.repository.get(document_id)
        if output is None:
            raise DocumentNotFoundError(str(document_id))
        return output

    def human_verify(
        self,
        *,
        document_id: UUID,
        field_id: UUID,
        verified_text: str,
        reviewer_id: str,
        approved: bool,
    ) -> Step1Output:
        output = self.get_document(document_id)
        field = next(
            (candidate for candidate in output.extracted_fields if candidate.field_id == field_id),
            None,
        )
        if field is None:
            raise FieldNotFoundError(str(field_id))

        clean_text = normalize_text(verified_text)
        if not clean_text:
            raise ValueError("Verified text cannot be empty.")
        if approved:
            updated_field = field.model_copy(
                update={
                    "standardized_text": clean_text,
                    "extraction_confidence": 1.0,
                    "confidence_tier": ConfidenceTier.VERIFIED,
                    "dual_run_result": DualRunResult(
                        triggered=True,
                        second_pass_text=clean_text,
                        agreement=True,
                    ),
                    "requires_doctor_review_before_memory_write": False,
                }
            )
            updated_output = replace_field(output, updated_field)
            remaining_review = any(
                candidate.requires_doctor_review_before_memory_write
                for candidate in updated_output.extracted_fields
            )
            updated_output = apply_document_gate(
                updated_output,
                verification_state=(
                    VerificationState.PENDING
                    if remaining_review
                    else VerificationState.VERIFIED
                ),
            )
        else:
            updated_field = field.model_copy(
                update={
                    "confidence_tier": ConfidenceTier.HUMAN_VERIFICATION_REQUIRED,
                    "requires_doctor_review_before_memory_write": True,
                }
            )
            updated_output = replace_field(output, updated_field).model_copy(
                update={
                    "processing_status": ProcessingStatus.FAILED,
                    "verification_state": VerificationState.REJECTED,
                }
            )

        self.repository.save(updated_output)
        self.audit_logger.record(
            document_id,
            "step1.human_verification",
            actor_id=reviewer_id,
            details={
                "field_id": str(field_id),
                "approved": approved,
            },
        )
        return updated_output

    def _complete_run(
        self,
        *,
        document_id: UUID,
        audit_log_id: UUID,
        patient_id: UUID,
        encounter_id: UUID,
        modality: InputModality,
        source_language: str,
        original_language_text: str | None,
        translation_confidence: float,
        run: ExtractionRun,
        ocr_engine_used: str | None,
        vlm_model_used: str | None,
    ) -> Step1Output:
        candidates = split_into_candidate_fields(run.text)
        if not candidates:
            raise ValueError("No readable clinical text was extracted.")

        fields: list[ExtractedField] = []
        for candidate in candidates:
            high_risk = is_high_risk(candidate)
            decision = decide_confidence_gate(
                run.confidence,
                high_risk=high_risk,
                dual_run_triggered=run.dual_run_triggered,
                dual_run_agreement=run.dual_run_agreement,
            )
            fields.append(
                ExtractedField(
                    raw_text=candidate,
                    standardized_text=candidate,
                    extraction_confidence=run.confidence,
                    is_high_risk_field=high_risk,
                    confidence_tier=decision.tier,
                    dual_run_result=DualRunResult(
                        triggered=run.dual_run_triggered,
                        second_pass_text=run.second_pass_text,
                        agreement=run.dual_run_agreement,
                    ),
                    requires_doctor_review_before_memory_write=decision.requires_review,
                )
            )

        requires_review = any(
            field.requires_doctor_review_before_memory_write for field in fields
        )
        output = Step1Output(
            document_id=document_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            input_modality=modality,
            source_language=source_language,
            extracted_fields=fields,
            translation_confidence=translation_confidence,
            original_language_text=original_language_text,
            ocr_engine_used=ocr_engine_used,
            vlm_model_used=vlm_model_used,
            processing_status=(
                ProcessingStatus.PENDING_HUMAN_VERIFICATION
                if requires_review
                else ProcessingStatus.COMPLETE
            ),
            audit_log_id=audit_log_id,
            created_at=datetime.now(timezone.utc),
            verification_state=(
                VerificationState.PENDING
                if requires_review
                else VerificationState.NOT_REQUIRED
            ),
        )
        self.repository.save(output)
        self.audit_logger.record(
            document_id,
            "step1.processing_completed",
            details={
                "processing_status": output.processing_status.value,
                "verification_state": output.verification_state.value,
            },
        )
        return output

    def _failed_output(
        self,
        *,
        document_id: UUID,
        audit_log_id: UUID,
        patient_id: UUID,
        encounter_id: UUID,
        modality: InputModality,
        source_language: str,
        original_language_text: str | None,
        translation_confidence: float,
        ocr_engine_used: str | None,
        vlm_model_used: str | None,
        error: Exception,
    ) -> Step1Output:
        output = Step1Output(
            document_id=document_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            input_modality=modality,
            source_language=source_language,
            extracted_fields=[],
            translation_confidence=translation_confidence,
            original_language_text=original_language_text,
            ocr_engine_used=ocr_engine_used,
            vlm_model_used=vlm_model_used,
            processing_status=ProcessingStatus.FAILED,
            audit_log_id=audit_log_id,
            created_at=datetime.now(timezone.utc),
            verification_state=VerificationState.NOT_REQUIRED,
        )
        self.repository.save(output)
        self.audit_logger.record(
            document_id,
            "step1.processing_failed",
            details={"error_type": type(error).__name__},
        )
        return output
