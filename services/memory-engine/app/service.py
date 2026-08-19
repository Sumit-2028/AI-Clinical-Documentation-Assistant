from datetime import datetime, timezone
from uuid import UUID

from contracts.schemas import (
    ConflictResolutionAction,
    ConflictRecord,
    ConflictStatus,
    CurrentPatientState,
    MemoryEvent,
    MemoryEventHistory,
    MemoryRetrieveRequest,
    MemorySource,
    MemoryWriteRequest,
    MemoryWriteResponse,
    ResolveConflictResponse,
    ReviewedStatus,
    RetrievedContext,
    TierReviewResponse,
    TrustTier,
)

from .retrieval import RetrievalService
from .stores import InMemoryMemoryStore
from .vector import VectorStore
from .write_gate import MemoryWriteGate


class MemoryEventNotFoundError(LookupError):
    pass


class ConflictNotFoundError(LookupError):
    pass


class ConflictResolutionError(ValueError):
    pass


class TierReviewError(ValueError):
    pass


class MemoryEngineService:
    def __init__(
        self,
        *,
        store: InMemoryMemoryStore | None = None,
        write_gate: MemoryWriteGate | None = None,
        retrieval_service: RetrievalService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        if store is None and write_gate is not None:
            store = write_gate.store
        self.store = store or InMemoryMemoryStore()
        self.write_gate = write_gate or MemoryWriteGate(self.store)
        self.retrieval_service = retrieval_service or RetrievalService(
            store=self.store,
            vector_store=vector_store,
        )

    def write_events(
        self,
        request: MemoryWriteRequest,
        *,
        actor_id: str | None = None,
    ) -> MemoryWriteResponse:
        return self.write_gate.write(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            source=request.source,
            clinical_events=request.clinical_events,
            actor_id=actor_id or request.actor_id,
        )

    def get_events(self, patient_id: UUID) -> MemoryEventHistory:
        return MemoryEventHistory(
            patient_id=patient_id,
            events=self.store.list_events(patient_id),
        )

    def get_current_state(self, patient_id: UUID) -> CurrentPatientState:
        return self.store.get_current_state(patient_id)

    def retrieve(self, request: MemoryRetrieveRequest) -> RetrievedContext:
        return self.retrieval_service.retrieve(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            query_concepts=request.query_concepts,
        )

    def list_conflicts(
        self,
        *,
        patient_id: UUID | None = None,
        status: ConflictStatus | None = None,
        risk_level: str | None = None,
    ) -> list[ConflictRecord]:
        return self.store.list_conflicts(
            patient_id=patient_id,
            status=status.value if status else None,
            risk_level=risk_level,
        )

    def resolve_conflict(
        self,
        *,
        conflict_id: UUID,
        action: ConflictResolutionAction,
        physician_id: str,
    ) -> ResolveConflictResponse:
        conflict = self.store.get_conflict(conflict_id)
        if conflict is None:
            raise ConflictNotFoundError(str(conflict_id))
        if conflict.status == ConflictStatus.RESOLVED:
            raise ConflictResolutionError("Conflict is already resolved.")

        resolution = self.store.record_conflict_resolution(
            conflict_id=conflict_id,
            physician_id=physician_id,
            action=action.value,
        )
        if action == ConflictResolutionAction.KEEP_UNRESOLVED:
            updated = conflict.model_copy(
                update={
                    "resolution_action": action,
                    "physician_id": physician_id,
                }
            )
            self.store.update_conflict(updated)
            return ResolveConflictResponse(
                conflict_id=conflict_id,
                status=ConflictStatus.UNRESOLVED,
                new_event_id=None,
            )

        selected_event_id = (
            conflict.event_a_id
            if action == ConflictResolutionAction.CONFIRM_EVENT_A
            else conflict.event_b_id
        )
        rejected_event_id = (
            conflict.event_b_id
            if action == ConflictResolutionAction.CONFIRM_EVENT_A
            else conflict.event_a_id
        )
        selected_event = self.store.get_event(selected_event_id)
        rejected_event = self.store.get_event(rejected_event_id)
        if rejected_event is not None and rejected_event.current_trust_tier != TrustTier.UNVERIFIED:
            self.store.record_tier_review(
                event_id=rejected_event_id,
                physician_id=physician_id,
                new_tier=TrustTier.UNVERIFIED,
                reviewed_status=ReviewedStatus.RESOLUTION_CONFIRMED,
            )
            self.store.update_thread_trust(self.store.get_event(rejected_event_id))
        if selected_event is not None and selected_event.current_trust_tier == TrustTier.UNVERIFIED:
            self.store.record_tier_review(
                event_id=selected_event_id,
                physician_id=physician_id,
                new_tier=TrustTier.PHYSICIAN_REVIEWED,
                reviewed_status=ReviewedStatus.RESOLUTION_CONFIRMED,
            )
            self.store.update_thread_trust(self.store.get_event(selected_event_id))
        selected_event = self.store.get_event(selected_event_id)
        if selected_event is not None:
            self.store.set_thread_current_event(selected_event)

        updated = conflict.model_copy(
            update={
                "status": ConflictStatus.RESOLVED,
                "resolution_action": action,
                "physician_id": physician_id,
                "resolved_event_id": resolution.resolution_id,
                "resolved_at": datetime.now(timezone.utc),
            }
        )
        self.store.update_conflict(updated)
        return ResolveConflictResponse(
            conflict_id=conflict_id,
            status=ConflictStatus.RESOLVED,
            new_event_id=resolution.resolution_id,
        )

    def approve_tier3(
        self,
        *,
        event_id: UUID,
        physician_id: str,
    ) -> TierReviewResponse:
        event = self.store.get_event(event_id)
        if event is None:
            raise MemoryEventNotFoundError(str(event_id))
        if event.current_trust_tier != TrustTier.UNVERIFIED:
            raise TierReviewError("Only tier-3 events can be approved.")

        review = self.store.record_tier_review(
            event_id=event_id,
            physician_id=physician_id,
            new_tier=TrustTier.PHYSICIAN_REVIEWED,
            reviewed_status=ReviewedStatus.REVIEWED_APPROVED,
        )
        reviewed_event = self.store.get_event(event_id)
        self.store.update_thread_trust(reviewed_event)
        return TierReviewResponse(
            event_id=event_id,
            new_trust_tier=TrustTier.PHYSICIAN_REVIEWED,
            trust_tier_change_event_id=review.review_id,
            reviewed_status=ReviewedStatus.REVIEWED_APPROVED,
        )

    def reject_tier3(
        self,
        *,
        event_id: UUID,
        physician_id: str,
    ) -> TierReviewResponse:
        event = self.store.get_event(event_id)
        if event is None:
            raise MemoryEventNotFoundError(str(event_id))
        if event.current_trust_tier != TrustTier.UNVERIFIED:
            raise TierReviewError("Only tier-3 events can be rejected.")

        review = self.store.record_tier_review(
            event_id=event_id,
            physician_id=physician_id,
            new_tier=TrustTier.UNVERIFIED,
            reviewed_status=ReviewedStatus.REVIEWED_REJECTED,
        )
        return TierReviewResponse(
            event_id=event_id,
            new_trust_tier=TrustTier.UNVERIFIED,
            trust_tier_change_event_id=review.review_id,
            reviewed_status=ReviewedStatus.REVIEWED_REJECTED,
        )
