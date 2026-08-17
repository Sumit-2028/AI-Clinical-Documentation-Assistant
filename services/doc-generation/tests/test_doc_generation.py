from uuid import uuid4

from contracts.schemas import (
    ClinicalEvent,
    ClinicalEventValidationStatus,
    ConflictRecord,
    DocumentSections,
    DocumentType,
    FinalizeDocumentRequest,
    GenerateDocumentRequest,
    MemoryContextItem,
    MemorySource,
    ProvenanceRecord,
    RetrievedContext,
    ReviewAction,
    SourceTextSpan,
    TrustTier,
    VerifiedContext,
)
from services.doc_generation.app.context import ContextAssembler
from services.doc_generation.app.generation import ProductionLLMGenerator
from services.doc_generation.app.service import DocumentService
from services.doc_generation.app.validation import DocumentValidator


def make_event(*, concept="Hypertension", status="active", assertion="affirmed"):
    text = f"Patient has {concept}"
    return ClinicalEvent(
        event_local_id=uuid4(),
        original_text=text,
        processed_text=text,
        normalized_concept=concept,
        snomed_ct_id="38341003" if concept == "Hypertension" else None,
        entity_type="condition",
        clinical_domain="cardiology",
        relationships=[],
        assertion=assertion,
        clinical_status=status,
        temporal_context="current",
        temporal_date=None,
        bioclinicalbert_confidence=0.94,
        gemini_contextualization_confidence=0.90,
        source_document_id=uuid4(),
        source_text_span=SourceTextSpan(start=0, end=len(text)),
        input_modality="typed",
        source_language="en",
        translation_confidence=1.0,
        validation_status=ClinicalEventValidationStatus.VALID,
    )


def make_context(*, unverified=False, conflict=False):
    event_id = uuid4()
    document_id = uuid4()
    item = MemoryContextItem(
        event_id=event_id,
        concept_thread_id=uuid4(),
        normalized_concept="Hypertension",
        clinical_status="active",
        assertion="affirmed",
        temporal_context="current",
        original_text="Patient has Hypertension",
        trust_tier=TrustTier.UNVERIFIED if unverified else TrustTier.VERIFIED,
        provenance=ProvenanceRecord(
            source_document_id=document_id,
            source_event_id=uuid4(),
            source_text_span=SourceTextSpan(start=0, end=25),
            input_modality="typed",
            source_language="en",
            confidence=0.88,
        ),
    )
    conflict_records = []
    if conflict:
        conflict_records.append(
            ConflictRecord(
                patient_id=uuid4(),
                concept_thread_id=item.concept_thread_id,
                event_a_id=event_id,
                event_b_id=uuid4(),
                conflict_type="contradictory_status",
                risk_level="high",
            )
        )
    return RetrievedContext(
        verified_context=VerifiedContext(
            conditions=[] if unverified else [item]
        ),
        unverified_information=[item] if unverified else [],
        conflicts=conflict_records,
    )


def make_request(*, document_type=DocumentType.SOAP_NOTE, context=None, event=None):
    return GenerateDocumentRequest(
        patient_id=uuid4(),
        encounter_id=uuid4(),
        document_type=document_type,
        current_consultation_events=[event or make_event()],
        retrieved_context=context or make_context(),
    )


class RecordingMemoryWriter:
    def __init__(self):
        self.payloads = []

    def submit(self, payload):
        self.payloads.append(payload)
        return {"accepted": True}


def test_soap_generation_is_a_draft_with_provenance():
    service = DocumentService()
    document = service.generate(make_request())

    assert document.document_type == DocumentType.SOAP_NOTE
    assert document.status.value == "draft"
    assert document.generator == "deterministic_mock"
    assert document.validation_result.passed is True
    assert document.sections.subjective
    assert document.sections.objective
    assert document.sections.assessment
    assert document.sections.plan
    mapped_sections = {entry.section for entry in document.provenance_map}
    assert {"subjective", "objective", "assessment", "plan"} <= mapped_sections


def test_discharge_summary_uses_its_contract_sections():
    service = DocumentService()
    document = service.generate(
        make_request(document_type=DocumentType.DISCHARGE_SUMMARY)
    )

    assert document.status.value == "draft"
    assert document.sections.patient_identification
    assert document.sections.reason_for_encounter
    assert document.sections.relevant_history
    assert document.sections.medications
    assert document.sections.allergies
    assert document.sections.follow_up
    assert document.sections.subjective is None


def test_unverified_and_conflicting_context_are_flagged_not_promoted():
    service = DocumentService()
    document = service.generate(
        make_request(context=make_context(unverified=True, conflict=True))
    )

    codes = {flag.code for flag in document.flags_for_physician_review}
    assert "UNVERIFIED_CONTEXT" in codes
    assert "UNRESOLVED_CONFLICT" in codes
    assert document.sections.assessment
    assert "Patient has Hypertension" not in document.sections.relevant_history


def test_validator_detects_missing_sections_and_unsupported_claims():
    service = DocumentService()
    document = service.generate(make_request())
    context = ContextAssembler().assemble(
        patient_id=document.patient_id,
        encounter_id=document.encounter_id,
        current_events=[make_event()],
        retrieved_context=make_context(),
    )
    invalid = document.model_copy(
        update={
            "sections": document.sections.model_copy(
                update={
                    "subjective": None,
                    "assessment": "Patient has Diabetes",
                }
            )
        }
    )

    result = DocumentValidator().validate(invalid, context)

    codes = {failure.code for failure in result.failures}
    assert result.passed is False
    assert "MISSING_REQUIRED_SECTION" in codes
    assert "UNSUPPORTED_CLINICAL_CLAIM" in codes


def test_accept_returns_memory_write_payload_and_uses_injected_handoff():
    writer = RecordingMemoryWriter()
    service = DocumentService(memory_write_client=writer)
    request = make_request()
    document = service.generate(request)

    response = service.finalize(
        document.document_id,
        FinalizeDocumentRequest(
            action=ReviewAction.ACCEPT,
            physician_id="doctor-123",
        ),
    )

    assert response.status.value == "finalized"
    assert response.memory_write_payload is not None
    assert response.memory_write_payload.source == MemorySource.PHYSICIAN_APPROVED_CONSULTATION
    assert writer.payloads == [response.memory_write_payload]
    assert service.get(document.document_id).status.value == "finalized"


def test_edit_action_revalidates_and_finalizes():
    service = DocumentService()
    document = service.generate(make_request())

    response = service.finalize(
        document.document_id,
        FinalizeDocumentRequest(
            action=ReviewAction.EDIT,
            physician_id="doctor-123",
            edited_sections=DocumentSections(
                plan="Plan: Follow-up with physician review.",
            ),
        ),
    )

    assert response.status.value == "finalized"
    assert response.memory_write_payload is not None


def test_reject_regenerate_returns_new_draft_without_memory_write():
    writer = RecordingMemoryWriter()
    service = DocumentService(memory_write_client=writer)
    document = service.generate(make_request())

    response = service.finalize(
        document.document_id,
        FinalizeDocumentRequest(
            action=ReviewAction.REJECT_REGENERATE,
            physician_id="doctor-123",
            regenerate_notes="Clarify the plan.",
        ),
    )

    assert response.status.value == "draft"
    assert response.document is not None
    assert response.document.document_id != document.document_id
    assert response.memory_write_payload is None
    assert writer.payloads == []
    assert any(
        flag.code == "REGENERATED_AFTER_REJECTION"
        for flag in response.document.flags_for_physician_review
    )


def test_production_generator_never_falls_back_silently():
    generator = ProductionLLMGenerator()
    try:
        generator.generate(None, document_type=DocumentType.SOAP_NOTE)
    except RuntimeError as exc:
        assert "configured" in str(exc)
    else:
        raise AssertionError("Expected unavailable production generator to fail")
