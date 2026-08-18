import re
import io
import unicodedata


HIGH_RISK_PATTERN = re.compile(
    r"\b(?:allerg(?:y|ies|ic)|penicillin|insulin|heparin|warfarin|"
    r"anticoagulant|dos(?:e|age)|mg|mcg|pregnan(?:t|cy)|suicid(?:e|al)|"
    r"stroke|seizure|anaphylaxis|critical)\b",
    re.IGNORECASE,
)


class DocumentTextExtractionError(ValueError):
    """Raised when a typed document has no safely extractable text."""


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


def decode_uploaded_text(content: bytes, *, filename: str | None = None) -> str:
    """Extract text from typed uploads without treating PDF bytes as UTF-8.

    ``pypdf`` is the production parser.  The small operator parser is retained
    as a dependency-free fallback for simple synthetic text PDFs used in local
    smoke tests; it only returns text operators from a valid PDF envelope and
    never treats arbitrary binary bytes as clinical text.
    """

    looks_like_pdf = content.startswith(b"%PDF-") or (filename or "").casefold().endswith(".pdf")
    if not looks_like_pdf:
        return normalize_text(content.decode("utf-8", errors="replace"))

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        extracted = normalize_text("\n".join(pages))
        if extracted:
            return extracted
    except ImportError:
        pass
    except Exception as exc:
        raise DocumentTextExtractionError(
            "The uploaded PDF could not be parsed safely."
        ) from exc

    extracted = _extract_simple_pdf_text(content)
    if not extracted:
        raise DocumentTextExtractionError(
            "The uploaded PDF contains no extractable text. Use a text-based PDF or choose handwritten processing for a scanned document."
        )
    return normalize_text(extracted)


def _extract_simple_pdf_text(content: bytes) -> str:
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content:
        raise DocumentTextExtractionError("The uploaded file is not a complete PDF.")

    raw = content.decode("latin-1", errors="ignore")
    blocks = re.findall(r"BT(.*?)ET", raw, flags=re.DOTALL)
    strings: list[str] = []
    for block in blocks:
        for token in re.findall(r"\((?:\\.|[^\\)])*\)", block):
            value = token[1:-1]
            value = re.sub(r"\\([\\()])", r"\1", value)
            value = re.sub(r"\\[nrt]", " ", value)
            if value.strip():
                strings.append(value)
    return " ".join(strings)
