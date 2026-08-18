"""Person B's NER stage — hybrid scispaCy + bc5cdr + regex + dictionary."""

from .base import (
    EXTRACTION_SOURCE_BC5CDR,
    EXTRACTION_SOURCE_DICTIONARY,
    EXTRACTION_SOURCE_REGEX,
    EXTRACTION_SOURCE_SCI,
    EntitySpan,
    NERAdapter,
)
from .hybrid import HybridNERAdapter, NLPModelUnavailableError, split_sentences

__all__ = [
    "EntitySpan",
    "EXTRACTION_SOURCE_BC5CDR",
    "EXTRACTION_SOURCE_DICTIONARY",
    "EXTRACTION_SOURCE_REGEX",
    "EXTRACTION_SOURCE_SCI",
    "HybridNERAdapter",
    "NERAdapter",
    "NLPModelUnavailableError",
    "split_sentences",
]
