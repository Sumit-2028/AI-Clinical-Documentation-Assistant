from dataclasses import dataclass
import re
import unicodedata

from contracts.schemas import ExtractedField, SourceTextSpan, Step1Output


@dataclass(frozen=True)
class PreprocessedField:
    source_field: ExtractedField
    original_text: str
    processed_text: str
    source_text_span: SourceTextSpan


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def preprocess_field(field: ExtractedField) -> PreprocessedField:
    original_text = field.raw_text.strip()
    return PreprocessedField(
        source_field=field,
        original_text=original_text,
        processed_text=normalize_text(field.standardized_text),
        source_text_span=SourceTextSpan(start=0, end=len(original_text)),
    )


def preprocess_step1_output(step1_output: Step1Output) -> list[PreprocessedField]:
    return [preprocess_field(field) for field in step1_output.extracted_fields]
