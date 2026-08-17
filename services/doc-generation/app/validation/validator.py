"""Deterministic safety validation for generated documentation."""

import re

from contracts.schemas import (
    DocumentValidationResult,
    GeneratedDocument,
    ValidationFailure,
)

from ..context import GenerationContext
from ..templates import TemplateRegistry


_CLAIM_RE = re.compile(
    r"\b(?:has|have|diagnosed with|history of|taking|allergic to|denies|"
    r"reports|requires|is|was|will)\s+"
    r"([A-Za-z][A-Za-z0-9 -]{1,60})",
    re.IGNORECASE,
)
_LABELLED_CLAIM_RE = re.compile(
    r"\b(?:diagnosis|condition|medication|allergy|procedure)\s*[:\-]\s*"
    r"([A-Za-z][A-Za-z0-9 -]{1,60})",
    re.IGNORECASE,
)


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


class DocumentValidator:
    def validate(
        self,
        document: GeneratedDocument,
        context: GenerationContext,
    ) -> DocumentValidationResult:
        failures: list[ValidationFailure] = []
        template = TemplateRegistry.get(document.document_type)
        provenance_sections = {entry.section for entry in document.provenance_map}

        for section in template.required_sections:
            value = getattr(document.sections, section)
            if not value or not value.strip():
                failures.append(
                    ValidationFailure(
                        code="MISSING_REQUIRED_SECTION",
                        message=f"Required section '{section}' is missing.",
                        section=section,
                    )
                )

        for section in self._nonempty_sections(document):
            if section not in provenance_sections:
                failures.append(
                    ValidationFailure(
                        code="MISSING_PROVENANCE",
                        message=f"No provenance mapping covers section '{section}'.",
                        section=section,
                    )
                )

        supported_text = _normalized(context.supported_text)
        for section in self._nonempty_sections(document):
            value = getattr(document.sections, section) or ""
            matches = [
                *_CLAIM_RE.finditer(value),
                *_LABELLED_CLAIM_RE.finditer(value),
            ]
            for match in matches:
                claimed = _normalized(match.group(1)).strip()
                if claimed and claimed not in supported_text:
                    failures.append(
                        ValidationFailure(
                            code="UNSUPPORTED_CLINICAL_CLAIM",
                            message=(
                                f"Section '{section}' contains unsupported clinical claim: "
                                f"{match.group(0).strip()}"
                            ),
                            section=section,
                        )
                    )

        conflict_concepts = self._conflict_concepts(context)
        if conflict_concepts:
            for section in self._nonempty_sections(document):
                value = (getattr(document.sections, section) or "").casefold()
                if any(
                    concept.casefold() in value
                    for concept in conflict_concepts
                ) and not any(
                    marker in value for marker in ("uncertain", "conflict", "pending physician")
                ):
                    failures.append(
                        ValidationFailure(
                            code="UNRESOLVED_CONFLICT_CLAIM",
                            message=(
                                f"Section '{section}' states information associated with an unresolved conflict "
                                "without an uncertainty marker."
                            ),
                            section=section,
                        )
                    )

        return DocumentValidationResult(
            passed=not failures,
            failures=failures,
            auto_regeneration_attempts=0,
        )

    @staticmethod
    def _nonempty_sections(document: GeneratedDocument) -> list[str]:
        return [
            name
            for name in type(document.sections).model_fields
            if (getattr(document.sections, name) or "").strip()
        ]

    @staticmethod
    def _conflict_concepts(context: GenerationContext) -> set[str]:
        conflict_ids = context.conflict_event_ids
        return {
            source.concept or source.text
            for source in context.unverified_sources
            if set(source.source_event_ids) & conflict_ids
        }


def validate_document(
    document: GeneratedDocument,
    context: GenerationContext,
) -> DocumentValidationResult:
    return DocumentValidator().validate(document, context)


__all__ = ["DocumentValidator", "validate_document"]
