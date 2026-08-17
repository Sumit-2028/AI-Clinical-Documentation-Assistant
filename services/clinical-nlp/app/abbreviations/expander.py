from dataclasses import dataclass
import re

from ..preprocess import PreprocessedField


ABBREVIATIONS: dict[str, str] = {
    "htn": "hypertension",
    "dm": "diabetes mellitus",
    "sob": "shortness of breath",
    "bp": "blood pressure",
    "hr": "heart rate",
    "rr": "respiratory rate",
    "pt": "patient",
    "c/o": "complains of",
    "hx": "history",
    "dx": "diagnosis",
    "tx": "treatment",
    "meds": "medications",
}


@dataclass(frozen=True)
class ExpandedField:
    source: PreprocessedField
    processed_text: str
    replacements: tuple[tuple[str, str], ...]


def expand_abbreviations(text: str) -> str:
    expanded = text
    for abbreviation, replacement in sorted(
        ABBREVIATIONS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        expanded = re.sub(
            rf"(?<!\w){re.escape(abbreviation)}(?!\w)",
            replacement,
            expanded,
            flags=re.IGNORECASE,
        )
    return expanded


def expand_field(field: PreprocessedField) -> ExpandedField:
    expanded = expand_abbreviations(field.processed_text)
    replacements = tuple(
        (abbreviation, replacement)
        for abbreviation, replacement in ABBREVIATIONS.items()
        if re.search(
            rf"(?<!\w){re.escape(abbreviation)}(?!\w)",
            field.processed_text,
            flags=re.IGNORECASE,
        )
    )
    return ExpandedField(
        source=field,
        processed_text=expanded,
        replacements=replacements,
    )
