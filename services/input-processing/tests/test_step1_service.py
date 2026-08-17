from uuid import uuid4

import pytest

from app.adapters import AdapterBundle, MockTranslationAdapter
from app.audit import InMemoryAuditLogger
from app.confidence import decide_confidence_gate
from app.ocr import MockOCRAdapter
from app.repository import InMemoryDocumentRepository
from app.service import InputProcessingService
from app.vlm import MockVLMAdapter
from contracts.schemas import (
    ConfidenceTier,
    InputModality,
    ProcessingStatus,
    Step1Output,
    VerificationState,
)


@pytest.fixture
def identifiers():
    return uuid4(), uuid4()


@pytest.fixture
def service():
    return InputProcessingService(
        repository=InMemoryDocumentRepository(),
        audit_logger=InMemoryAuditLogger(),
    )


def test_typed_input_is_normalized_and_auto_passes(service, identifiers):
    patient_id, encounter_id = identifiers

    output = service.process_typed(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"Patient has hypertension.\nContinue follow-up.",
        filename="typed.txt",
    )

    assert output.input_modality == InputModality.TYPED
    assert output.processing_status == ProcessingStatus.COMPLETE
    assert output.verification_state == VerificationState.NOT_REQUIRED
    assert output.ocr_engine_used is None
    assert output.vlm_model_used is None
    assert all(field.confidence_tier == ConfidenceTier.AUTO_PASS for field in output.extracted_fields)
    assert all(
        not field.requires_doctor_review_before_memory_write
        for field in output.extracted_fields
    )
    assert output.patient_id == patient_id
    assert output.encounter_id == encounter_id


def test_handwritten_high_risk_input_is_gated_and_records_provenance(service, identifiers):
    patient_id, encounter_id = identifiers

    output = service.process_handwritten(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"Patient has penicillin allergy",
        filename="handwritten.png",
    )

    field = output.extracted_fields[0]
    assert output.input_modality == InputModality.HANDWRITTEN
    assert output.processing_status == ProcessingStatus.PENDING_HUMAN_VERIFICATION
    assert output.verification_state == VerificationState.PENDING
    assert output.ocr_engine_used == "mock-ocr"
    assert output.vlm_model_used == "mock-vlm"
    assert field.is_high_risk_field is True
    assert field.confidence_tier == ConfidenceTier.HUMAN_VERIFICATION_REQUIRED
    assert field.requires_doctor_review_before_memory_write is True
    assert field.dual_run_result.triggered is True


def test_multilingual_input_preserves_original_language_and_gates_translation(service, identifiers):
    patient_id, encounter_id = identifiers

    output = service.process_multilingual(
        patient_id=patient_id,
        encounter_id=encounter_id,
        text_input="रोगी को बुखार है",
        source_language="hi",
    )

    assert output.input_modality == InputModality.MULTILINGUAL
    assert output.source_language == "hi"
    assert output.original_language_text == "रोगी को बुखार है"
    assert output.translation_confidence == 0.86
    assert output.processing_status == ProcessingStatus.PENDING_HUMAN_VERIFICATION
    assert output.verification_state == VerificationState.PENDING


@pytest.mark.parametrize(
    ("confidence", "high_risk", "dual", "agreement", "tier", "review"),
    [
        (0.96, False, False, None, ConfidenceTier.AUTO_PASS, False),
        (0.80, False, True, True, ConfidenceTier.DUAL_RUN, False),
        (0.80, False, True, False, ConfidenceTier.HUMAN_VERIFICATION_REQUIRED, True),
        (0.96, True, False, None, ConfidenceTier.HUMAN_VERIFICATION_REQUIRED, True),
        (0.40, False, False, None, ConfidenceTier.HUMAN_VERIFICATION_REQUIRED, True),
    ],
)
def test_confidence_gate(
    confidence,
    high_risk,
    dual,
    agreement,
    tier,
    review,
):
    decision = decide_confidence_gate(
        confidence,
        high_risk=high_risk,
        dual_run_triggered=dual,
        dual_run_agreement=agreement,
    )

    assert decision.tier == tier
    assert decision.requires_review is review


def test_human_verification_clears_memory_write_gate(service, identifiers):
    patient_id, encounter_id = identifiers
    output = service.process_handwritten(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"Patient has penicillin allergy",
        filename="handwritten.png",
    )
    field_id = output.extracted_fields[0].field_id

    verified = service.human_verify(
        document_id=output.document_id,
        field_id=field_id,
        verified_text="Patient has confirmed penicillin allergy",
        reviewer_id="doctor-123",
        approved=True,
    )

    field = verified.extracted_fields[0]
    assert verified.processing_status == ProcessingStatus.COMPLETE
    assert verified.verification_state == VerificationState.VERIFIED
    assert field.standardized_text == "Patient has confirmed penicillin allergy"
    assert field.confidence_tier == ConfidenceTier.VERIFIED
    assert field.requires_doctor_review_before_memory_write is False


def test_rejected_human_verification_cannot_become_trusted(service, identifiers):
    patient_id, encounter_id = identifiers
    output = service.process_handwritten(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"Patient has penicillin allergy",
    )
    field_id = output.extracted_fields[0].field_id

    rejected = service.human_verify(
        document_id=output.document_id,
        field_id=field_id,
        verified_text="Not confirmed",
        reviewer_id="doctor-123",
        approved=False,
    )

    assert rejected.processing_status == ProcessingStatus.FAILED
    assert rejected.verification_state == VerificationState.REJECTED
    assert rejected.extracted_fields[0].requires_doctor_review_before_memory_write is True


def test_empty_input_is_stored_as_failed_state(service, identifiers):
    patient_id, encounter_id = identifiers

    output = service.process_typed(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"",
    )

    assert output.processing_status == ProcessingStatus.FAILED
    assert service.get_document(output.document_id) == output


def test_step1_output_round_trips_through_contract_validation(service, identifiers):
    patient_id, encounter_id = identifiers
    output = service.process_typed(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=b"Patient has hypertension",
    )

    validated = Step1Output.model_validate(output.model_dump())

    assert validated == output


def test_mock_adapters_are_explicitly_labeled():
    adapters = AdapterBundle(
        ocr=MockOCRAdapter(),
        vlm=MockVLMAdapter(),
        translation=MockTranslationAdapter(),
    )

    assert adapters.ocr.engine_name == "mock-ocr"
    assert adapters.vlm.model_name == "mock-vlm"
    assert adapters.translation.provider_name == "mock-translation"
