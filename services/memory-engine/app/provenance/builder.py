from datetime import datetime, timezone

from contracts.schemas import ClinicalEvent, MemorySource, ProvenanceRecord


def build_provenance(event: ClinicalEvent, *, actor_id: str | None = None) -> ProvenanceRecord:
    return ProvenanceRecord(
        source_document_id=event.source_document_id,
        source_event_id=event.event_local_id,
        actor_id=actor_id,
        source_text_span=event.source_text_span,
        input_modality=event.input_modality,
        source_language=event.source_language,
        confidence=min(
            event.bioclinicalbert_confidence,
            event.gemini_contextualization_confidence,
            event.translation_confidence,
        ),
        captured_at=datetime.now(timezone.utc),
    )


class ProvenanceBuilder:
    def build(self, event: ClinicalEvent, *, actor_id: str | None = None) -> ProvenanceRecord:
        return build_provenance(event, actor_id=actor_id)
