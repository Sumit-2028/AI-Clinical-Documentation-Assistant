from contracts.schemas import (
    ExtractedField,
    ProcessingStatus,
    Step1Output,
    VerificationState,
)


def apply_document_gate(
    output: Step1Output,
    *,
    verification_state: VerificationState | None = None,
) -> Step1Output:
    requires_review = any(
        field.requires_doctor_review_before_memory_write
        for field in output.extracted_fields
    )

    resolved_state = verification_state
    if resolved_state is None:
        resolved_state = (
            VerificationState.PENDING
            if requires_review
            else VerificationState.NOT_REQUIRED
        )

    if output.processing_status == ProcessingStatus.FAILED:
        return output.model_copy(update={"verification_state": resolved_state})

    return output.model_copy(
        update={
            "processing_status": (
                ProcessingStatus.PENDING_HUMAN_VERIFICATION
                if requires_review
                else ProcessingStatus.COMPLETE
            ),
            "verification_state": resolved_state,
        }
    )


def replace_field(output: Step1Output, updated_field: ExtractedField) -> Step1Output:
    fields = [
        updated_field if field.field_id == updated_field.field_id else field
        for field in output.extracted_fields
    ]
    return output.model_copy(update={"extracted_fields": fields})
