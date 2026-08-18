from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from contracts.schemas import (
    DocumentReviewResponse,
    FinalizeDocumentRequest,
    GenerateDocumentRequest,
    GeneratedDocument,
)

from .review import (
    DocumentNotFoundError,
    DocumentReviewError,
    MemoryWriteHandoffError,
)
from .service import DocumentGenerationError, DocumentService


router = APIRouter(tags=["step4-documentation"])


def get_document_service(request: Request) -> DocumentService:
    return request.app.state.document_service


def _internal_patient_id(raw_patient_id, request: Request) -> UUID:
    resolved = getattr(request.state, "internal_patient_id", None)
    if resolved is not None:
        return resolved
    try:
        return UUID(str(raw_patient_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="A valid patient identifier is required.") from exc


@router.post(
    "/step4/documents/generate",
    response_model=GeneratedDocument,
    response_model_exclude_none=True,
)
def generate_document(
    request: GenerateDocumentRequest,
    http_request: Request,
    service: DocumentService = Depends(get_document_service),
) -> GeneratedDocument:
    try:
        return service.generate(
            request.model_copy(
                update={"patient_id": _internal_patient_id(request.patient_id, http_request)}
            )
        )
    except DocumentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/step4/documents/{document_id}/finalize",
    response_model=DocumentReviewResponse,
    response_model_exclude_none=True,
)
def finalize_document(
    document_id: UUID,
    request: FinalizeDocumentRequest,
    http_request: Request,
    service: DocumentService = Depends(get_document_service),
) -> DocumentReviewResponse:
    try:
        # The body field remains part of the public contract for compatibility,
        # but the authenticated actor is authoritative for audit/provenance.
        return service.finalize(
            document_id,
            request.model_copy(
                update={
                    "physician_id": str(
                        getattr(http_request.state, "current_user_id", request.physician_id)
                    )
                }
            ),
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc
    except MemoryWriteHandoffError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory write handoff failed safely; document remains a draft.",
        ) from exc
    except DocumentReviewError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


__all__ = ["router"]
