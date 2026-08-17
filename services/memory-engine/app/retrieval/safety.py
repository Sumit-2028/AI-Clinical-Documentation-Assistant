"""Safety classification for memory retrieval candidates."""

from dataclasses import dataclass
from uuid import UUID

from contracts.schemas import MemoryEvent

from ..stores import InMemoryMemoryStore
from ..trust import is_established


@dataclass(frozen=True)
class SafetyDecision:
    verified: bool
    reason: str


class RetrievalSafetyFilter:
    """Prevents low-trust and unresolved-conflict facts entering verified context."""

    def __init__(self, store: InMemoryMemoryStore) -> None:
        self.store = store

    def unresolved_event_ids(self, patient_id: UUID) -> set[UUID]:
        return {
            event_id
            for conflict in self.store.list_conflicts(
                patient_id=patient_id,
                status="unresolved",
            )
            for event_id in (conflict.event_a_id, conflict.event_b_id)
        }

    def classify(
        self,
        event: MemoryEvent,
        *,
        unresolved_event_ids: set[UUID] | None = None,
    ) -> SafetyDecision:
        conflicted = unresolved_event_ids or set()
        if event.event_id in conflicted:
            return SafetyDecision(False, "unresolved_conflict")
        if not is_established(event.current_trust_tier):
            return SafetyDecision(False, "trust_tier_unverified")
        return SafetyDecision(True, "established")


__all__ = ["RetrievalSafetyFilter", "SafetyDecision"]
