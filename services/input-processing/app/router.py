from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from .schemas import HumanVerificationRequest, MultilingualDocumentRequest, Step1Output
from .service import (
    DocumentNotFoundError,
    FieldNotFoundError,
    InputDocumentError,
    InputProcessingService,
)
from .repository import EncounterPatientMismatchError
from .upload_security import UploadSecurityError, read_validated_upload


router = APIRouter(
    prefix="/step1/documents",
    tags=["Step 1 - Input Processing"],
)


def get_step1_service(request: Request) -> InputProcessingService:
    return request.app.state.step1_service


def _internal_patient_id(raw_patient_id, request: Request) -> UUID:
    resolved = getattr(request.state, "internal_patient_id", None)
    if resolved is not None:
        return resolved
    try:
        return UUID(str(raw_patient_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="A valid patient identifier is required.") from exc


@router.post("/typed", response_model=Step1Output)
async def process_typed_document(
    http_request: Request,
    patient_id: str = Form(...),
    encounter_id: UUID = Form(...),
    file: UploadFile = File(...),
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        return service.process_typed(
            patient_id=_internal_patient_id(patient_id, http_request),
            encounter_id=encounter_id,
            content=upload.content,
            filename=upload.filename,
            actor_id=getattr(http_request.state, "current_user_id", None),
        )
    except InputDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EncounterPatientMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/handwritten", response_model=Step1Output)
async def process_handwritten_document(
    http_request: Request,
    patient_id: str = Form(...),
    encounter_id: UUID = Form(...),
    file: UploadFile = File(...),
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        return service.process_handwritten(
            patient_id=_internal_patient_id(patient_id, http_request),
            encounter_id=encounter_id,
            content=upload.content,
            filename=upload.filename,
            actor_id=getattr(http_request.state, "current_user_id", None),
        )
    except EncounterPatientMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/multilingual", response_model=Step1Output)
def process_multilingual_document(
    request: MultilingualDocumentRequest,
    http_request: Request,
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        return service.process_multilingual(
            patient_id=_internal_patient_id(request.patient_id, http_request),
            encounter_id=request.encounter_id,
            text_input=request.text_input,
            source_language=request.source_language,
            actor_id=getattr(http_request.state, "current_user_id", None),
        )
    except EncounterPatientMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=Step1Output)
def get_document(
    document_id: UUID,
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        return service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc


@router.post("/{document_id}/human-verify", response_model=Step1Output)
def human_verify_document(
    document_id: UUID,
    payload: HumanVerificationRequest,
    http_request: Request,
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        return service.human_verify(
            document_id=document_id,
            field_id=payload.field_id,
            verified_text=payload.verified_text,
            reviewer_id=str(getattr(http_request.state, "current_user_id", payload.reviewer_id)),
            approved=payload.approved,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    except FieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Field not found.") from exc
