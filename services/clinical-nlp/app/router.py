import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .schemas import ClinicalEventBatch, Step2ProcessRequest
from .service import (
    ClinicalEventBatchNotFoundError,
    ClinicalNLPProcessingError,
    ClinicalNLPService,
    Step1InputError,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/step2",
    tags=["Step 2 - Clinical NLP"],
)


def get_nlp_service(request: Request) -> ClinicalNLPService:
    return request.app.state.clinical_nlp_service


def _internal_patient_id(raw_patient_id, request: Request) -> UUID:
    resolved = getattr(request.state, "internal_patient_id", None)
    if resolved is not None:
        return resolved
    try:
        return UUID(str(raw_patient_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="A valid patient identifier is required.") from exc


@router.post("/process", response_model=ClinicalEventBatch)
def process_step1_output(
    request: Step2ProcessRequest,
    http_request: Request,
    service: ClinicalNLPService = Depends(get_nlp_service),
) -> ClinicalEventBatch:
    try:
        return service.process(
            document_id=request.document_id,
            patient_id=_internal_patient_id(request.patient_id, http_request),
            encounter_id=request.encounter_id,
            step1_output=request.step1_output,
        )
    except Step1InputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ClinicalNLPProcessingError as exc:
        logger.error(
            "Clinical NLP processing failed",
            extra={"error_type": exc.cause_type},
        )
        raise HTTPException(
            status_code=503,
            detail="Clinical NLP processing failed.",
        ) from exc


@router.get("/process/{document_id}", response_model=ClinicalEventBatch)
def get_processed_events(
    document_id: UUID,
    service: ClinicalNLPService = Depends(get_nlp_service),
) -> ClinicalEventBatch:
    try:
        return service.get(document_id)
    except ClinicalEventBatchNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Clinical events have not been processed for this document.",
        ) from exc
