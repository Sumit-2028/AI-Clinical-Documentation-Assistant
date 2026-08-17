"""Reusable provenance mapping for generated document sections."""

from collections.abc import Sequence

from contracts.schemas import DocumentProvenanceEntry, TrustTier

from ..context import ContextSource


class DocumentProvenanceMapper:
    def map_section(
        self,
        *,
        section: str,
        generated_text: str,
        sources: Sequence[ContextSource],
        generator: str,
    ) -> DocumentProvenanceEntry:
        source_event_ids = tuple(
            event_id for source in sources for event_id in source.source_event_ids
        )
        source_document_ids = tuple(
            document_id for source in sources for document_id in source.source_document_ids
        )
        trust_tiers = {
            source.trust_tier for source in sources if source.trust_tier is not None
        }
        return DocumentProvenanceEntry(
            section=section,
            generated_text=generated_text,
            source_event_ids=list(dict.fromkeys(source_event_ids)),
            source_document_ids=list(dict.fromkeys(source_document_ids)),
            source_kind=(
                "+".join(dict.fromkeys(source.source_kind for source in sources))
                if sources
                else generator
            ),
            trust_tier=next(iter(trust_tiers)) if len(trust_tiers) == 1 else None,
            confidence=min((source.confidence for source in sources), default=0.0),
            is_inferred=not bool(sources),
        )


__all__ = ["DocumentProvenanceMapper"]
