from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from contracts.schemas import (
    ConflictResolutionAction,
    ConflictRecord,
    ConflictStatus,
    CurrentPatientState,
    MemoryEventHistory,
    MemoryRetrieveRequest,
    MemoryWriteRequest,
    MemoryWriteResponse,
    ResolveConflictRequest,
    ResolveConflictResponse,
    RetrievedContext,
    TierReviewRequest,
    TierReviewResponse,
)

from .service import (
    ConflictNotFoundError,
    ConflictResolutionError,
    MemoryEngineService,
    MemoryEventNotFoundError,
    TierReviewError,
)


router = APIRouter(tags=["Step 3 - Patient Memory"])


def get_memory_service(request: Request) -> MemoryEngineService:
    return request.app.state.memory_engine_service


def _internal_patient_id(raw_patient_id, request: Request) -> UUID:
    resolved = getattr(request.state, "internal_patient_id", None)
    if resolved is not None:
        return resolved
    try:
        return UUID(str(raw_patient_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="A valid patient identifier is required.") from exc


@router.post("/step3/memory/events", response_model=MemoryWriteResponse)
def write_memory_events(
    request: MemoryWriteRequest,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> MemoryWriteResponse:
    return service.write_events(
        request.model_copy(update={"patient_id": _internal_patient_id(request.patient_id, http_request)}),
        actor_id=getattr(http_request.state, "current_user_id", request.actor_id),
    )


@router.get(
    "/step3/memory/{patient_id}/events",
    response_model=MemoryEventHistory,
)
def get_patient_events(
    patient_id: str,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> MemoryEventHistory:
    return service.get_events(_internal_patient_id(patient_id, http_request))


@router.get(
    "/step3/memory/{patient_id}/current-state",
    response_model=CurrentPatientState,
)
def get_current_patient_state(
    patient_id: str,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> CurrentPatientState:
    return service.get_current_state(_internal_patient_id(patient_id, http_request))


@router.post("/step3/memory/retrieve", response_model=RetrievedContext)
def retrieve_memory_context(
    request: MemoryRetrieveRequest,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> RetrievedContext:
    return service.retrieve(
        request.model_copy(update={"patient_id": _internal_patient_id(request.patient_id, http_request)})
    )


@router.get("/step3/conflicts", response_model=list[ConflictRecord])
def list_conflicts(
    http_request: Request,
    patient_id: str | None = None,
    status_filter: ConflictStatus | None = Query(default=None, alias="status"),
    risk_level: str | None = None,
    service: MemoryEngineService = Depends(get_memory_service),
) -> list[ConflictRecord]:
    return service.list_conflicts(
        patient_id=(
            _internal_patient_id(patient_id, http_request)
            if patient_id is not None
            else None
        ),
        status=status_filter,
        risk_level=risk_level,
    )


@router.post(
    "/step3/conflicts/{conflict_id}/resolve",
    response_model=ResolveConflictResponse,
)
def resolve_conflict(
    conflict_id: UUID,
    request: ResolveConflictRequest,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> ResolveConflictResponse:
    try:
        return service.resolve_conflict(
            conflict_id=conflict_id,
            action=request.resolution_action,
            physician_id=str(getattr(http_request.state, "current_user_id", request.physician_id)),
        )
    except ConflictNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conflict not found.") from exc
    except ConflictResolutionError as exc:
        raise HTTPException(status_code=409, detail="Conflict cannot be resolved in its current state.") from exc


@router.post(
    "/step3/tier3/{event_id}/approve",
    response_model=TierReviewResponse,
)
def approve_tier3(
    event_id: UUID,
    request: TierReviewRequest,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> TierReviewResponse:
    try:
        return service.approve_tier3(
            event_id=event_id,
            physician_id=str(getattr(http_request.state, "current_user_id", request.physician_id)),
        )
    except MemoryEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory event not found.") from exc
    except TierReviewError as exc:
        raise HTTPException(status_code=409, detail="Tier review cannot be applied in its current state.") from exc


@router.post(
    "/step3/tier3/{event_id}/reject",
    response_model=TierReviewResponse,
)
def reject_tier3(
    event_id: UUID,
    request: TierReviewRequest,
    http_request: Request,
    service: MemoryEngineService = Depends(get_memory_service),
) -> TierReviewResponse:
    try:
        return service.reject_tier3(
            event_id=event_id,
            physician_id=str(getattr(http_request.state, "current_user_id", request.physician_id)),
        )
    except MemoryEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory event not found.") from exc
    except TierReviewError as exc:
        raise HTTPException(status_code=409, detail="Tier review cannot be applied in its current state.") from exc
