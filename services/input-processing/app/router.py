from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from services.object_storage import (
    ObjectStorage,
    ObjectStorageError,
    StoredObject,
    build_source_key,
)

from .schemas import HumanVerificationRequest, MultilingualDocumentRequest, Step1Output
from .service import (
    DocumentNotFoundError,
    FieldNotFoundError,
    InputProcessingService,
)
from .upload_security import UploadSecurityError, read_validated_upload


router = APIRouter(
    prefix="/step1/documents",
    tags=["Step 1 - Input Processing"],
)


def get_step1_service(request: Request) -> InputProcessingService:
    return request.app.state.step1_service


def get_object_storage(request: Request) -> ObjectStorage:
    return request.app.state.object_storage


def _store_source_document(
    storage: ObjectStorage,
    *,
    patient_id: UUID,
    document_id: UUID,
    content: bytes,
    content_type: str,
) -> StoredObject:
    """Persist the original upload before any extraction runs.

    Storing first means a document whose extraction fails still has its source
    available for review, which is exactly the case a reviewer needs it for.
    It also keeps storage failures out of the service, whose broad exception
    handler would report them as a successful request with a failed run.
    """

    key = build_source_key(patient_id=patient_id, document_id=document_id)
    try:
        return storage.put(key=key, content=content, content_type=content_type)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable.",
        ) from exc


@router.post("/typed", response_model=Step1Output)
async def process_typed_document(
    patient_id: UUID = Form(...),
    encounter_id: UUID = Form(...),
    file: UploadFile = File(...),
    service: InputProcessingService = Depends(get_step1_service),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    document_id = uuid4()
    stored = _store_source_document(
        storage,
        patient_id=patient_id,
        document_id=document_id,
        content=upload.content,
        content_type=upload.content_type,
    )
    return service.process_typed(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=upload.content,
        filename=upload.filename,
        document_id=document_id,
        source_object=stored,
    )


@router.post("/handwritten", response_model=Step1Output)
async def process_handwritten_document(
    patient_id: UUID = Form(...),
    encounter_id: UUID = Form(...),
    file: UploadFile = File(...),
    service: InputProcessingService = Depends(get_step1_service),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    document_id = uuid4()
    stored = _store_source_document(
        storage,
        patient_id=patient_id,
        document_id=document_id,
        content=upload.content,
        content_type=upload.content_type,
    )
    return service.process_handwritten(
        patient_id=patient_id,
        encounter_id=encounter_id,
        content=upload.content,
        filename=upload.filename,
        document_id=document_id,
        source_object=stored,
    )


@router.post("/multilingual", response_model=Step1Output)
def process_multilingual_document(
    request: MultilingualDocumentRequest,
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    return service.process_multilingual(
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        text_input=request.text_input,
        source_language=request.source_language,
    )


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
    request: HumanVerificationRequest,
    service: InputProcessingService = Depends(get_step1_service),
) -> Step1Output:
    try:
        return service.human_verify(
            document_id=document_id,
            field_id=request.field_id,
            verified_text=request.verified_text,
            reviewer_id=request.reviewer_id,
            approved=request.approved,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    except FieldNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Field not found.") from exc
