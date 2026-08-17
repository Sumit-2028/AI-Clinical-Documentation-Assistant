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


@router.post("/step3/memory/events", response_model=MemoryWriteResponse)
def write_memory_events(
    request: MemoryWriteRequest,
    service: MemoryEngineService = Depends(get_memory_service),
) -> MemoryWriteResponse:
    return service.write_events(request)


@router.get(
    "/step3/memory/{patient_id}/events",
    response_model=MemoryEventHistory,
)
def get_patient_events(
    patient_id: UUID,
    service: MemoryEngineService = Depends(get_memory_service),
) -> MemoryEventHistory:
    return service.get_events(patient_id)


@router.get(
    "/step3/memory/{patient_id}/current-state",
    response_model=CurrentPatientState,
)
def get_current_patient_state(
    patient_id: UUID,
    service: MemoryEngineService = Depends(get_memory_service),
) -> CurrentPatientState:
    return service.get_current_state(patient_id)


@router.post("/step3/memory/retrieve", response_model=RetrievedContext)
def retrieve_memory_context(
    request: MemoryRetrieveRequest,
    service: MemoryEngineService = Depends(get_memory_service),
) -> RetrievedContext:
    return service.retrieve(request)


@router.get("/step3/conflicts", response_model=list[ConflictRecord])
def list_conflicts(
    patient_id: UUID | None = None,
    status_filter: ConflictStatus | None = Query(default=None, alias="status"),
    risk_level: str | None = None,
    service: MemoryEngineService = Depends(get_memory_service),
) -> list[ConflictRecord]:
    return service.list_conflicts(
        patient_id=patient_id,
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
    service: MemoryEngineService = Depends(get_memory_service),
) -> ResolveConflictResponse:
    try:
        return service.resolve_conflict(
            conflict_id=conflict_id,
            action=request.resolution_action,
            physician_id=request.physician_id,
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
    service: MemoryEngineService = Depends(get_memory_service),
) -> TierReviewResponse:
    try:
        return service.approve_tier3(
            event_id=event_id,
            physician_id=request.physician_id,
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
    service: MemoryEngineService = Depends(get_memory_service),
) -> TierReviewResponse:
    try:
        return service.reject_tier3(
            event_id=event_id,
            physician_id=request.physician_id,
        )
    except MemoryEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory event not found.") from exc
    except TierReviewError as exc:
        raise HTTPException(status_code=409, detail="Tier review cannot be applied in its current state.") from exc
