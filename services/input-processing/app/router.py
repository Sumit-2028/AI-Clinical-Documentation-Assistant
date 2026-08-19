from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from services.object_storage import (
    ObjectStorage,
    ObjectStorageError,
    ObjectStorageNotFoundError,
    StoredObject,
    build_source_key,
    configured_presign_expiry,
    download_filename,
)

from .schemas import (
    DocumentSourceResponse,
    HumanVerificationRequest,
    MultilingualDocumentRequest,
    Step1Output,
)
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
    storage: ObjectStorage = Depends(get_object_storage),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # Resolve the internal identifier before building the key: retrieval derives
    # the same key from the same internal id, so the two must agree.
    internal_patient_id = _internal_patient_id(patient_id, http_request)
    document_id = uuid4()
    stored = _store_source_document(
        storage,
        patient_id=internal_patient_id,
        document_id=document_id,
        content=upload.content,
        content_type=upload.content_type,
    )
    try:
        return service.process_typed(
            patient_id=internal_patient_id,
            encounter_id=encounter_id,
            content=upload.content,
            filename=upload.filename,
            actor_id=getattr(http_request.state, "current_user_id", None),
            document_id=document_id,
            source_object=stored,
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
    storage: ObjectStorage = Depends(get_object_storage),
) -> Step1Output:
    try:
        upload = await read_validated_upload(file)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    internal_patient_id = _internal_patient_id(patient_id, http_request)
    document_id = uuid4()
    stored = _store_source_document(
        storage,
        patient_id=internal_patient_id,
        document_id=document_id,
        content=upload.content,
        content_type=upload.content_type,
    )
    try:
        return service.process_handwritten(
            patient_id=internal_patient_id,
            encounter_id=encounter_id,
            content=upload.content,
            filename=upload.filename,
            actor_id=getattr(http_request.state, "current_user_id", None),
            document_id=document_id,
            source_object=stored,
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


@router.get("/{document_id}/source", response_model=DocumentSourceResponse)
def get_document_source(
    document_id: UUID,
    service: InputProcessingService = Depends(get_step1_service),
    storage: ObjectStorage = Depends(get_object_storage),
) -> DocumentSourceResponse:
    """Return a short-lived link to the document's original bytes.

    The link is a bearer credential for its lifetime: anyone holding it can
    fetch the document without presenting a token, so the expiry is kept short.
    """

    try:
        stored = service.get_source_object(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc

    if stored is None:
        # The document exists but has no stored file: multilingual input, or an
        # upload predating object storage.  Distinct message from the above so
        # the two cases are tellable apart.
        raise HTTPException(status_code=404, detail="No stored source document.")

    try:
        # A durable repository records only the storage URI, so the content
        # type comes from the object store rather than the document row.
        content_type = stored.content_type or storage.head(key=stored.key).content_type
        presigned = storage.presign_get(
            key=stored.key,
            expires_in=configured_presign_expiry(),
            download_filename=download_filename(document_id, content_type),
        )
    except ObjectStorageNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="No stored source document."
        ) from exc
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable.",
        ) from exc

    return DocumentSourceResponse(
        document_id=document_id,
        download_url=presigned.url,
        expires_at=presigned.expires_at,
        content_type=presigned.content_type,
        size_bytes=presigned.size_bytes,
    )


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
