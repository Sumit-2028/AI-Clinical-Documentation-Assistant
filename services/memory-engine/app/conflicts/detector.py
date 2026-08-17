from contracts.schemas import ConflictRecord, MemoryEvent


def _is_contradictory(left: MemoryEvent, right: MemoryEvent) -> bool:
    status_pair = {left.clinical_status, right.clinical_status}
    assertion_pair = {left.assertion, right.assertion}
    return (
        status_pair in ({"active", "inactive"}, {"active", "resolved"})
        or assertion_pair == {"affirmed", "negated"}
    )


def _risk_level(event: MemoryEvent) -> str:
    if event.entity_type in {"allergy", "medication"}:
        return "high"
    if event.clinical_domain in {"cardiology", "respiratory"}:
        return "high"
    return "medium"


def detect_conflict(
    candidate: MemoryEvent,
    existing_events: list[MemoryEvent],
    *,
    has_existing_pair,
) -> list[ConflictRecord]:
    conflicts: list[ConflictRecord] = []
    for existing in existing_events:
        if existing.concept_thread_id != candidate.concept_thread_id:
            continue
        if not _is_contradictory(existing, candidate):
            continue
        if has_existing_pair(existing.event_id, candidate.event_id):
            continue
        conflicts.append(
            ConflictRecord(
                patient_id=candidate.patient_id,
                concept_thread_id=candidate.concept_thread_id,
                event_a_id=existing.event_id,
                event_b_id=candidate.event_id,
                conflict_type="contradictory_clinical_status",
                risk_level=_risk_level(candidate),
            )
        )
    return conflicts


class ConflictDetector:
    def detect(
        self,
        candidate: MemoryEvent,
        existing_events: list[MemoryEvent],
        *,
        has_existing_pair,
    ) -> list[ConflictRecord]:
        return detect_conflict(
            candidate,
            existing_events,
            has_existing_pair=has_existing_pair,
        )
