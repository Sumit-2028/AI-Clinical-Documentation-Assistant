from dataclasses import dataclass

from contracts.schemas import DocumentProvenanceEntry, DocumentSections, DocumentReviewFlag


@dataclass(frozen=True)
class GeneratedDraft:
    sections: DocumentSections
    provenance_map: tuple[DocumentProvenanceEntry, ...]
    flags: tuple[DocumentReviewFlag, ...]
    generator: str
