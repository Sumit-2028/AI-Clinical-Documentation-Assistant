import re
import unicodedata


HIGH_RISK_PATTERN = re.compile(
    r"\b(?:allerg(?:y|ies|ic)|penicillin|insulin|heparin|warfarin|"
    r"anticoagulant|dos(?:e|age)|mg|mcg|pregnan(?:t|cy)|suicid(?:e|al)|"
    r"stroke|seizure|anaphylaxis|critical)\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    lines = [" ".join(line.split()) for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def split_into_candidate_fields(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    candidates = re.split(r"\n+|(?<=[.!?])\s+", normalized)
    return [candidate.strip() for candidate in candidates if candidate.strip()]


def is_high_risk(text: str) -> bool:
    return bool(HIGH_RISK_PATTERN.search(text))


def decode_uploaded_text(content: bytes) -> str:
    return normalize_text(content.decode("utf-8", errors="replace"))
