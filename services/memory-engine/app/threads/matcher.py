from dataclasses import dataclass
import re
from uuid import UUID, uuid4

from contracts.schemas import (
    ClinicalEvent,
    ConceptThreadState,
    ThreadMatchConfidence,
    ThreadMatchMethod,
)


@dataclass(frozen=True)
class ThreadMatch:
    concept_thread_id: UUID
    confidence: ThreadMatchConfidence
    method: ThreadMatchMethod
    is_new_thread: bool


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


def match_concept_thread(
    event: ClinicalEvent,
    threads: list[ConceptThreadState],
) -> ThreadMatch:
    for thread in threads:
        if event.snomed_ct_id and event.snomed_ct_id == thread.snomed_ct_id:
            return ThreadMatch(
                concept_thread_id=thread.concept_thread_id,
                confidence=ThreadMatchConfidence.HIGH,
                method=ThreadMatchMethod.CODE_SYSTEM,
                is_new_thread=False,
            )
    for thread in threads:
        if event.normalized_concept.casefold() == thread.normalized_concept.casefold():
            return ThreadMatch(
                concept_thread_id=thread.concept_thread_id,
                confidence=ThreadMatchConfidence.HIGH,
                method=ThreadMatchMethod.NORMALIZED_CONCEPT,
                is_new_thread=False,
            )
    event_tokens = _tokens(event.normalized_concept)
    for thread in threads:
        thread_tokens = _tokens(thread.normalized_concept)
        if event_tokens and thread_tokens:
            overlap = len(event_tokens & thread_tokens) / len(event_tokens | thread_tokens)
            if overlap >= 0.5:
                return ThreadMatch(
                    concept_thread_id=thread.concept_thread_id,
                    confidence=ThreadMatchConfidence.MEDIUM,
                    method=ThreadMatchMethod.TEXT_SIMILARITY,
                    is_new_thread=False,
                )
    return ThreadMatch(
        concept_thread_id=uuid4(),
        confidence=ThreadMatchConfidence.LOW,
        method=ThreadMatchMethod.NEW_THREAD,
        is_new_thread=True,
    )


class ConceptThreadMatcher:
    def match(
        self,
        event: ClinicalEvent,
        threads: list[ConceptThreadState],
    ) -> ThreadMatch:
        return match_concept_thread(event, threads)
