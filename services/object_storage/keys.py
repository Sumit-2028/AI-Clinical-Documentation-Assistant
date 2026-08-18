"""Object key construction for stored source documents.

The key layout is a versioned contract.  It is a pure function of
``(patient_id, document_id)``, which is what allows a stored object to be
located again without a database lookup.  Changing the layout or the prefix
after objects exist silently orphans every previously stored document.

Keys deliberately contain no protected health information: no original
filename, no patient name, no encounter detail, and no timestamp.  Keys travel
into logs, audit records, and presigned URLs, so only opaque identifiers
belong in them.
"""

from __future__ import annotations

from uuid import UUID

from .config import env_value


DEFAULT_KEY_PREFIX = "step1"

# Canonical download extension per validated content type.  Used only to name
# the file the browser saves; never to build a key.
CANONICAL_EXTENSIONS = {
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/tiff": ".tif",
}


def configured_key_prefix() -> str:
    raw = env_value("S3_KEY_PREFIX", DEFAULT_KEY_PREFIX) or DEFAULT_KEY_PREFIX
    return raw.strip("/") or DEFAULT_KEY_PREFIX


def build_source_key(
    *,
    patient_id: UUID,
    document_id: UUID,
    prefix: str | None = None,
) -> str:
    """Return the key for a document's original uploaded bytes."""

    resolved_prefix = (prefix or configured_key_prefix()).strip("/")
    return (
        f"{resolved_prefix}/patients/{patient_id}"
        f"/documents/{document_id}/source"
    )


def canonical_extension(content_type: str | None) -> str:
    if not content_type:
        return ""
    normalized = content_type.split(";", 1)[0].strip().casefold()
    return CANONICAL_EXTENSIONS.get(normalized, "")


def download_filename(document_id: UUID, content_type: str | None) -> str:
    """Name the browser should save the file as.

    Derived from the document id rather than the uploaded filename, which may
    itself carry patient identifiers.
    """

    return f"{document_id}{canonical_extension(content_type)}"


__all__ = [
    "CANONICAL_EXTENSIONS",
    "DEFAULT_KEY_PREFIX",
    "build_source_key",
    "canonical_extension",
    "configured_key_prefix",
    "download_filename",
]
