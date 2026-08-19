from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID, uuid4

from contracts.schemas import (
    ConflictRecord,
    ConceptThreadState,
    CurrentPatientState,
    MemoryEvent,
    ReviewedStatus,
    TrustTier,
    PhysicianApproval,
)


@dataclass(frozen=True)
class TierReviewRecord:
    review_id: UUID
    event_id: UUID
    physician_id: str
    previous_tier: TrustTier
    new_tier: TrustTier
    reviewed_status: ReviewedStatus
    created_at: datetime


@dataclass(frozen=True)
class ConflictResolutionRecord:
    resolution_id: UUID
    conflict_id: UUID
    physician_id: str
    action: str
    created_at: datetime


class InMemoryMemoryStore:
    """Thread-safe append-oriented store used by the standalone service."""

    def __init__(self) -> None:
        self._events: dict[UUID, MemoryEvent] = {}
        self._threads: dict[UUID, ConceptThreadState] = {}
        self._conflicts: dict[UUID, ConflictRecord] = {}
        self._tier_reviews: list[TierReviewRecord] = []
        self._conflict_resolutions: list[ConflictResolutionRecord] = []
        self._lock = RLock()

    def list_events(self, patient_id: UUID) -> list[MemoryEvent]:
        with self._lock:
            return sorted(
                [event for event in self._events.values() if event.patient_id == patient_id],
                key=lambda event: event.created_at,
            )

    def get_event(self, event_id: UUID) -> MemoryEvent | None:
        with self._lock:
            return self._events.get(event_id)

    def _append_event(self, event: MemoryEvent) -> MemoryEvent:
        with self._lock:
            if event.event_id in self._events:
                raise ValueError(f"Memory event {event.event_id} already exists.")
            self._events[event.event_id] = event
        return event

    def list_threads(self, patient_id: UUID) -> list[ConceptThreadState]:
        with self._lock:
            return [
                thread
                for thread in self._threads.values()
                if thread.patient_id == patient_id
            ]

    def create_thread(
        self,
        *,
        patient_id: UUID,
        normalized_concept: str,
        snomed_ct_id: str | None,
        clinical_domain: str,
        event: MemoryEvent,
    ) -> ConceptThreadState:
        thread = ConceptThreadState(
            concept_thread_id=event.concept_thread_id,
            patient_id=patient_id,
            normalized_concept=normalized_concept,
            snomed_ct_id=snomed_ct_id,
            clinical_domain=clinical_domain,
            current_status=event.clinical_status,
            current_trust_tier=event.current_trust_tier,
            latest_event_id=event.event_id,
            event_count=1,
            updated_at=event.created_at,
        )
        with self._lock:
            self._threads[thread.concept_thread_id] = thread
        return thread

    def update_thread(self, event: MemoryEvent) -> ConceptThreadState:
        with self._lock:
            thread = self._threads[event.concept_thread_id]
            updated = thread.model_copy(
                update={
                    "current_status": event.clinical_status,
                    "current_trust_tier": event.current_trust_tier,
                    "latest_event_id": event.event_id,
                    "event_count": thread.event_count + 1,
                    "updated_at": event.created_at,
                }
            )
            self._threads[event.concept_thread_id] = updated
            return updated

    def update_thread_trust(self, event: MemoryEvent) -> ConceptThreadState:
        with self._lock:
            thread = self._threads[event.concept_thread_id]
            updated = thread.model_copy(
                update={"current_trust_tier": event.current_trust_tier}
            )
            self._threads[event.concept_thread_id] = updated
            return updated

    def set_thread_current_event(self, event: MemoryEvent) -> ConceptThreadState:
        with self._lock:
            thread = self._threads[event.concept_thread_id]
            updated = thread.model_copy(
                update={
                    "current_status": event.clinical_status,
                    "current_trust_tier": event.current_trust_tier,
                    "latest_event_id": event.event_id,
                }
            )
            self._threads[event.concept_thread_id] = updated
            return updated

    def get_current_state(self, patient_id: UUID) -> CurrentPatientState:
        unresolved_thread_ids = {
            conflict.concept_thread_id
            for conflict in self.list_conflicts(
                patient_id=patient_id,
                status="unresolved",
            )
        }
        threads = [
            thread.model_copy(update={"current_status": "conflicted"})
            if thread.concept_thread_id in unresolved_thread_ids
            else thread
            for thread in self.list_threads(patient_id)
        ]
        return CurrentPatientState(
            patient_id=patient_id,
            concept_threads=sorted(
                threads,
                key=lambda thread: thread.normalized_concept,
            ),
        )

    def list_conflicts(
        self,
        *,
        patient_id: UUID | None = None,
        status: str | None = None,
        risk_level: str | None = None,
    ) -> list[ConflictRecord]:
        with self._lock:
            conflicts = list(self._conflicts.values())
        if patient_id is not None:
            conflicts = [conflict for conflict in conflicts if conflict.patient_id == patient_id]
        if status is not None:
            conflicts = [conflict for conflict in conflicts if conflict.status.value == status]
        if risk_level is not None:
            conflicts = [
                conflict for conflict in conflicts if conflict.risk_level == risk_level
            ]
        return sorted(conflicts, key=lambda conflict: conflict.created_at)

    def add_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict
        return conflict

    def get_conflict(self, conflict_id: UUID) -> ConflictRecord | None:
        with self._lock:
            return self._conflicts.get(conflict_id)

    def update_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        with self._lock:
            if conflict.conflict_id not in self._conflicts:
                raise KeyError(str(conflict.conflict_id))
            self._conflicts[conflict.conflict_id] = conflict
        return conflict

    def has_conflict_pair(self, event_a_id: UUID, event_b_id: UUID) -> bool:
        pair = {event_a_id, event_b_id}
        return any(
            {conflict.event_a_id, conflict.event_b_id} == pair
            for conflict in self._conflicts.values()
        )

    def record_tier_review(
        self,
        *,
        event_id: UUID,
        physician_id: str,
        new_tier: TrustTier,
        reviewed_status: ReviewedStatus,
    ) -> TierReviewRecord:
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise KeyError(str(event_id))
            record = TierReviewRecord(
                review_id=uuid4(),
                event_id=event_id,
                physician_id=physician_id,
                previous_tier=event.current_trust_tier,
                new_tier=new_tier,
                reviewed_status=reviewed_status,
                created_at=datetime.now(timezone.utc),
            )
            self._tier_reviews.append(record)
            approval = PhysicianApproval(
                physician_id=physician_id,
                action=reviewed_status.value,
            )
            self._events[event_id] = event.model_copy(
                update={
                    "current_trust_tier": new_tier,
                    "reviewed_status": reviewed_status,
                    "provenance": event.provenance.model_copy(
                        update={"physician_approval": approval}
                    ),
                }
            )
            return record

    def list_tier_reviews(self, event_id: UUID) -> list[TierReviewRecord]:
        with self._lock:
            return [record for record in self._tier_reviews if record.event_id == event_id]

    def record_conflict_resolution(
        self,
        *,
        conflict_id: UUID,
        physician_id: str,
        action: str,
    ) -> ConflictResolutionRecord:
        record = ConflictResolutionRecord(
            resolution_id=uuid4(),
            conflict_id=conflict_id,
            physician_id=physician_id,
            action=action,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._conflict_resolutions.append(record)
        return record


class SqlAlchemyMemoryStore:
    """Durable adapter using the shared clinical_events/patient_memory/conflicts tables."""

    def __init__(self, db) -> None:
        self.db = db

    def list_events(self, patient_id: UUID) -> list[MemoryEvent]:
        from database.models import PatientMemoryRecord

        records = (
            self.db.query(PatientMemoryRecord)
            .filter(PatientMemoryRecord.patient_id == patient_id)
            .order_by(PatientMemoryRecord.created_at.asc())
            .all()
        )
        return [MemoryEvent.model_validate(record.memory_payload) for record in records]

    def get_event(self, event_id: UUID) -> MemoryEvent | None:
        from database.models import PatientMemoryRecord

        record = (
            self.db.query(PatientMemoryRecord)
            .filter(PatientMemoryRecord.id == event_id)
            .first()
        )
        return MemoryEvent.model_validate(record.memory_payload) if record else None

    def _append_event(self, event: MemoryEvent) -> MemoryEvent:
        from database.models import PatientMemoryRecord

        if self.get_event(event.event_id) is not None:
            raise ValueError(f"Memory event {event.event_id} already exists.")
        try:
            self.db.add(
                PatientMemoryRecord(
                    id=event.event_id,
                    patient_id=event.patient_id,
                    encounter_id=event.encounter_id,
                    clinical_event_id=None,
                    concept_thread_id=event.concept_thread_id,
                    memory_payload=event.model_dump(mode="json"),
                    trust_tier=str(int(event.trust_tier)),
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return event

    def list_threads(self, patient_id: UUID) -> list[ConceptThreadState]:
        events = self.list_events(patient_id)
        grouped: dict[UUID, list[MemoryEvent]] = {}
        for event in events:
            grouped.setdefault(event.concept_thread_id, []).append(event)
        return [
            ConceptThreadState(
                concept_thread_id=thread_id,
                patient_id=patient_id,
                normalized_concept=group[0].normalized_concept,
                snomed_ct_id=group[0].snomed_ct_id,
                clinical_domain=group[0].clinical_domain,
                current_status=group[-1].clinical_status,
                current_trust_tier=group[-1].current_trust_tier,
                latest_event_id=group[-1].event_id,
                event_count=len(group),
                updated_at=group[-1].created_at,
            )
            for thread_id, group in grouped.items()
        ]

    def create_thread(self, **kwargs) -> ConceptThreadState:
        for thread in self.list_threads(kwargs["patient_id"]):
            if thread.concept_thread_id == kwargs["event"].concept_thread_id:
                return thread
        event = kwargs["event"]
        return ConceptThreadState(
            concept_thread_id=event.concept_thread_id,
            patient_id=kwargs["patient_id"],
            normalized_concept=kwargs["normalized_concept"],
            snomed_ct_id=kwargs["snomed_ct_id"],
            clinical_domain=kwargs["clinical_domain"],
            current_status=event.clinical_status,
            current_trust_tier=event.current_trust_tier,
            latest_event_id=event.event_id,
            event_count=1,
            updated_at=event.created_at,
        )

    def update_thread(self, event: MemoryEvent) -> ConceptThreadState:
        return next(
            thread
            for thread in self.list_threads(event.patient_id)
            if thread.concept_thread_id == event.concept_thread_id
        )

    def update_thread_trust(self, event: MemoryEvent) -> ConceptThreadState:
        return self.update_thread(event)

    def set_thread_current_event(self, event: MemoryEvent) -> ConceptThreadState:
        return self.update_thread(event)

    def get_current_state(self, patient_id: UUID) -> CurrentPatientState:
        unresolved = {
            conflict.concept_thread_id
            for conflict in self.list_conflicts(patient_id=patient_id, status="unresolved")
        }
        threads = [
            thread.model_copy(update={"current_status": "conflicted"})
            if thread.concept_thread_id in unresolved
            else thread
            for thread in self.list_threads(patient_id)
        ]
        return CurrentPatientState(patient_id=patient_id, concept_threads=threads)

    def list_conflicts(self, *, patient_id=None, status=None, risk_level=None):
        from database.models import ConflictRecord as ConflictRecordModel

        query = self.db.query(ConflictRecordModel)
        if patient_id is not None:
            query = query.filter(ConflictRecordModel.patient_id == patient_id)
        if status is not None:
            query = query.filter(ConflictRecordModel.status == status)
        if risk_level is not None:
            query = query.filter(ConflictRecordModel.risk_level == risk_level)
        return [ConflictRecord.model_validate(record.conflict_payload) for record in query.all()]

    def add_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        from database.models import ConflictRecord as ConflictRecordModel

        try:
            self.db.add(
                ConflictRecordModel(
                    id=conflict.conflict_id,
                    patient_id=conflict.patient_id,
                    status=conflict.status.value,
                    risk_level=conflict.risk_level,
                    conflict_payload=conflict.model_dump(mode="json"),
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return conflict

    def get_conflict(self, conflict_id: UUID) -> ConflictRecord | None:
        from database.models import ConflictRecord as ConflictRecordModel

        record = self.db.query(ConflictRecordModel).filter(ConflictRecordModel.id == conflict_id).first()
        return ConflictRecord.model_validate(record.conflict_payload) if record else None

    def update_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        from database.models import ConflictRecord as ConflictRecordModel

        record = self.db.query(ConflictRecordModel).filter(ConflictRecordModel.id == conflict.conflict_id).first()
        if record is None:
            raise KeyError(str(conflict.conflict_id))
        try:
            record.status = conflict.status.value
            record.risk_level = conflict.risk_level
            record.conflict_payload = conflict.model_dump(mode="json")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return conflict

    def has_conflict_pair(self, event_a_id: UUID, event_b_id: UUID) -> bool:
        return any(
            {conflict.event_a_id, conflict.event_b_id} == {event_a_id, event_b_id}
            for conflict in self.list_conflicts()
        )

    def record_tier_review(self, *, event_id, physician_id, new_tier, reviewed_status):
        event = self.get_event(event_id)
        if event is None:
            raise KeyError(str(event_id))
        from database.models import PatientMemoryRecord

        record = self.db.query(PatientMemoryRecord).filter(PatientMemoryRecord.id == event_id).first()
        review = TierReviewRecord(
            review_id=uuid4(),
            event_id=event_id,
            physician_id=physician_id,
            previous_tier=event.current_trust_tier,
            new_tier=new_tier,
            reviewed_status=reviewed_status,
            created_at=datetime.now(timezone.utc),
        )
        updated = event.model_copy(
            update={
                "current_trust_tier": new_tier,
                "reviewed_status": reviewed_status,
                "provenance": event.provenance.model_copy(
                    update={
                        "physician_approval": PhysicianApproval(
                            physician_id=physician_id,
                            action=reviewed_status.value,
                        )
                    }
                ),
            }
        )
        try:
            record.memory_payload = updated.model_dump(mode="json")
            record.trust_tier = str(int(event.trust_tier))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return review

    def record_conflict_resolution(self, *, conflict_id, physician_id, action):
        return ConflictResolutionRecord(
            resolution_id=uuid4(),
            conflict_id=conflict_id,
            physician_id=physician_id,
            action=action,
            created_at=datetime.now(timezone.utc),
        )


class SessionScopedSqlAlchemyMemoryStore:
    """Durable memory store facade using one short-lived session per call."""

    _METHODS = {
        "list_events",
        "get_event",
        "_append_event",
        "list_threads",
        "create_thread",
        "update_thread",
        "update_thread_trust",
        "set_thread_current_event",
        "get_current_state",
        "list_conflicts",
        "add_conflict",
        "get_conflict",
        "update_conflict",
        "has_conflict_pair",
        "record_tier_review",
        "list_tier_reviews",
        "record_conflict_resolution",
    }

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def __getattr__(self, name):
        if name not in self._METHODS:
            raise AttributeError(name)

        def invoke(*args, **kwargs):
            with self.session_factory() as db:
                return getattr(SqlAlchemyMemoryStore(db), name)(*args, **kwargs)

        return invoke
