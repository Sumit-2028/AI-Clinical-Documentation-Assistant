from dataclasses import dataclass
import re

from ..abbreviations import ExpandedField


@dataclass(frozen=True)
class TerminologyMatch:
    concept: str
    snomed_ct_id: str | None
    clinical_domain: str
    matched_text: str


TERMINOLOGY: tuple[tuple[str, str, str | None, str], ...] = (
    ("penicillin allergy", "Allergy to penicillin", "91936005", "allergy"),
    ("hypertension", "Hypertension", "38341003", "cardiology"),
    ("high blood pressure", "Hypertension", "38341003", "cardiology"),
    ("diabetes mellitus", "Diabetes mellitus", "73211009", "endocrinology"),
    ("shortness of breath", "Dyspnea", "267036007", "respiratory"),
    ("fever", "Fever", "386661006", "general medicine"),
    ("cough", "Cough", "49727002", "respiratory"),
    ("chest pain", "Chest pain", "29857009", "cardiology"),
    ("metformin", "Metformin", None, "medication"),
    ("insulin", "Insulin", None, "medication"),
)


def normalize_terminology(text: str) -> TerminologyMatch:
    lowered = text.casefold()
    for phrase, concept, code, domain in sorted(
        TERMINOLOGY,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered):
            return TerminologyMatch(
                concept=concept,
                snomed_ct_id=code,
                clinical_domain=domain,
                matched_text=phrase,
            )

    return TerminologyMatch(
        concept=text.strip().capitalize(),
        snomed_ct_id=None,
        clinical_domain="general medicine",
        matched_text=text.strip(),
    )


def normalize_field(field: ExpandedField) -> TerminologyMatch:
    return normalize_terminology(field.processed_text)
