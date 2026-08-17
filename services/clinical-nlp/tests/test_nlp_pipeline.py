from uuid import uuid4

import pytest

from contracts.schemas import (
    ClinicalEvent,
    ClinicalEventValidationStatus,
    ConfidenceTier,
    ExtractedField,
    InputModality,
    ProcessingStatus,
    SourceTextSpan,
    Step1Output,
    VerificationState,
)
from services.clinical_nlp.app.abbreviations import expand_abbreviations
from services.clinical_nlp.app.contextualization import (
    detect_assertion,
    extract_temporal_context,
)
from services.clinical_nlp.app.ner import (
    BioClinicalBERTNERAdapter,
    MockClinicalNERAdapter,
    NLPModelUnavailableError,
)
from services.clinical_nlp.app.pipeline import ClinicalNLPPipeline
from services.clinical_nlp.app.preprocess import normalize_text
from services.clinical_nlp.app.service import (
    ClinicalNLPService,
    Step1InputError,
)
from services.clinical_nlp.app.terminology import normalize_terminology
from services.clinical_nlp.app.validation import (
    ClinicalEventValidationError,
    validate_event,
    validate_events,
)


def make_step1_output(
    *,
    text: str = "Patient has HTN and cough",
    status: ProcessingStatus = ProcessingStatus.COMPLETE,
    requires_review: bool = False,
) -> Step1Output:
    patient_id = uuid4()
    encounter_id = uuid4()
    return Step1Output(
        document_id=uuid4(),
        patient_id=patient_id,
        encounter_id=encounter_id,
        input_modality=InputModality.TYPED,
        source_language="en",
        extracted_fields=[
            ExtractedField(
                raw_text=text,
                standardized_text=text,
                extraction_confidence=0.96,
                is_high_risk_field=False,
                confidence_tier=(
                    ConfidenceTier.HUMAN_VERIFICATION_REQUIRED
                    if requires_review
                    else ConfidenceTier.AUTO_PASS
                ),
                requires_doctor_review_before_memory_write=requires_review,
            )
        ],
        translation_confidence=1.0,
        original_language_text=None,
        ocr_engine_used=None,
        vlm_model_used=None,
        processing_status=status,
        audit_log_id=uuid4(),
        verification_state=(
            VerificationState.PENDING
            if requires_review
            else VerificationState.NOT_REQUIRED
        ),
    )


def test_preprocessing_normalizes_unicode_and_whitespace():
    assert normalize_text("  Patient\n\thas  HTN  ") == "Patient has HTN"


def test_abbreviation_expansion():
    assert expand_abbreviations("Pt with HTN, DM and SOB") == (
        "patient with hypertension, diabetes mellitus and shortness of breath"
    )


def test_terminology_normalization():
    match = normalize_terminology("hypertension")

    assert match.concept == "Hypertension"
    assert match.snomed_ct_id == "38341003"
    assert match.clinical_domain == "cardiology"


def test_ner_extracts_multiple_entities():
    entities = MockClinicalNERAdapter().extract("Patient has hypertension and cough")

    assert [entity.text.casefold() for entity in entities] == [
        "hypertension",
        "cough",
    ]
    assert all(entity.confidence > 0 for entity in entities)


def test_assertion_detection():
    assert detect_assertion("Patient denies chest pain", "chest pain").assertion == "negated"
    assert detect_assertion("Patient has chest pain", "chest pain").assertion == "affirmed"


def test_temporal_extraction():
    current = extract_temporal_context("fever for 3 days")
    historical = extract_temporal_context("history of hypertension")

    assert current.temporal_context == "current"
    assert historical.temporal_context == "historical"


def test_pipeline_builds_provenance_preserving_events():
    step1 = make_step1_output()
    events = ClinicalNLPPipeline().process(step1)

    assert len(events) == 2
    hypertension = next(event for event in events if event.normalized_concept == "Hypertension")
    assert hypertension.source_document_id == step1.document_id
    assert hypertension.original_text == "Patient has HTN and cough"
    assert hypertension.processed_text == "Patient has hypertension and cough"
    assert hypertension.snomed_ct_id == "38341003"
    assert hypertension.input_modality == InputModality.TYPED
    assert hypertension.source_language == "en"
    assert hypertension.translation_confidence == 1.0
    assert hypertension.validation_status == ClinicalEventValidationStatus.VALID
    assert hypertension.source_text_span.end > hypertension.source_text_span.start


def test_event_contract_round_trip():
    step1 = make_step1_output(text="Patient has fever")
    event = ClinicalNLPPipeline().process(step1)[0]

    assert ClinicalEvent.model_validate(event.model_dump()) == event


def test_invalid_event_does_not_validate():
    step1 = make_step1_output(text="Patient has fever")
    event = ClinicalNLPPipeline().process(step1)[0].model_copy(
        update={"source_text_span": SourceTextSpan(start=0, end=999)}
    )

    result = validate_event(event, expected_source_document_id=step1.document_id)

    assert result.valid is False
    assert any(issue.field == "source_text_span" for issue in result.issues)
    with pytest.raises(ClinicalEventValidationError):
        validate_events([event], expected_source_document_id=step1.document_id)


def test_service_rejects_unverified_step1_output():
    step1 = make_step1_output(
        status=ProcessingStatus.PENDING_HUMAN_VERIFICATION,
        requires_review=True,
    )
    service = ClinicalNLPService()

    with pytest.raises(Step1InputError):
        service.process(
            document_id=step1.document_id,
            patient_id=step1.patient_id,
            encounter_id=step1.encounter_id,
            step1_output=step1,
        )


def test_production_model_adapter_does_not_fake_results():
    adapter = BioClinicalBERTNERAdapter()

    with pytest.raises(NLPModelUnavailableError):
        adapter.extract("Patient has fever")
