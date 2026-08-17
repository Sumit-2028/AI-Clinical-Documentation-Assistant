"""Document-type templates and required section definitions."""

from dataclasses import dataclass

from contracts.schemas import DocumentType


@dataclass(frozen=True)
class TemplateDefinition:
    document_type: DocumentType
    required_sections: tuple[str, ...]


SOAP_TEMPLATE = TemplateDefinition(
    document_type=DocumentType.SOAP_NOTE,
    required_sections=("subjective", "objective", "assessment", "plan"),
)

DISCHARGE_TEMPLATE = TemplateDefinition(
    document_type=DocumentType.DISCHARGE_SUMMARY,
    required_sections=(
        "patient_identification",
        "reason_for_encounter",
        "relevant_history",
        "medications",
        "allergies",
        "follow_up",
    ),
)


class TemplateRegistry:
    _templates = {
        DocumentType.SOAP_NOTE: SOAP_TEMPLATE,
        DocumentType.DISCHARGE_SUMMARY: DISCHARGE_TEMPLATE,
    }

    @classmethod
    def get(cls, document_type: DocumentType) -> TemplateDefinition:
        return cls._templates[document_type]


__all__ = [
    "DISCHARGE_TEMPLATE",
    "SOAP_TEMPLATE",
    "TemplateDefinition",
    "TemplateRegistry",
]
