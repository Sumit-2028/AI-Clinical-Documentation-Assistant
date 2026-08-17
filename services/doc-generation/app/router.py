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


@router.post(
    "/step4/documents/generate",
    response_model=GeneratedDocument,
    response_model_exclude_none=True,
)
def generate_document(
    request: GenerateDocumentRequest,
    service: DocumentService = Depends(get_document_service),
) -> GeneratedDocument:
    try:
        return service.generate(request)
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
    service: DocumentService = Depends(get_document_service),
) -> DocumentReviewResponse:
    try:
        return service.finalize(document_id, request)
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
