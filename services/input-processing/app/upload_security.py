"""Safe, bounded upload handling for Step 1."""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import UploadFile


DEFAULT_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_ALLOWED_MIME_TYPES = frozenset(
    {
        "text/plain",
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/tiff",
    }
)
MIME_EXTENSIONS = {
    "text/plain": {".txt", ".text"},
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
    "image/tiff": {".tif", ".tiff"},
}


class UploadSecurityError(ValueError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    content: bytes
    filename: str
    content_type: str


def configured_max_upload_size() -> int:
    raw = os.getenv("MAX_UPLOAD_SIZE_BYTES")
    try:
        value = int(raw) if raw else DEFAULT_MAX_UPLOAD_SIZE_BYTES
    except ValueError:
        value = DEFAULT_MAX_UPLOAD_SIZE_BYTES
    return max(value, 1)


def configured_mime_types() -> frozenset[str]:
    raw = os.getenv("ALLOWED_UPLOAD_MIME_TYPES")
    if not raw:
        return DEFAULT_ALLOWED_MIME_TYPES
    values = frozenset(
        value.strip().casefold().split(";", 1)[0]
        for value in raw.split(",")
        if value.strip()
    )
    return values or DEFAULT_ALLOWED_MIME_TYPES


def validate_upload_metadata(
    *,
    filename: str | None,
    content_type: str | None,
    allowed_mime_types: frozenset[str] | None = None,
) -> tuple[str, str]:
    if not filename or not filename.strip():
        raise UploadSecurityError(
            "A safe filename is required.",
            status_code=400,
        )
    clean_filename = filename.strip()
    if (
        len(clean_filename) > 255
        or "\x00" in clean_filename
        or "/" in clean_filename
        or "\\" in clean_filename
        or clean_filename in {".", ".."}
        or clean_filename.startswith("..")
    ):
        raise UploadSecurityError(
            "Unsafe filename.",
            status_code=400,
        )

    normalized_type = (content_type or "").split(";", 1)[0].strip().casefold()
    allowed = allowed_mime_types or configured_mime_types()
    if normalized_type not in allowed:
        raise UploadSecurityError(
            "Unsupported upload type.",
            status_code=415,
        )

    extension = os.path.splitext(clean_filename)[1].casefold()
    expected_extensions = MIME_EXTENSIONS.get(normalized_type)
    if extension and expected_extensions and extension not in expected_extensions:
        raise UploadSecurityError(
            "Filename extension does not match the upload type.",
            status_code=415,
        )
    return clean_filename, normalized_type


async def read_validated_upload(upload: UploadFile) -> ValidatedUpload:
    filename, content_type = validate_upload_metadata(
        filename=upload.filename,
        content_type=upload.content_type,
    )
    max_bytes = configured_max_upload_size()
    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > max_bytes:
        raise UploadSecurityError(
            "Uploaded file is too large.",
            status_code=413,
        )

    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadSecurityError(
                "Uploaded file is too large.",
                status_code=413,
            )
        chunks.append(chunk)

    return ValidatedUpload(
        content=b"".join(chunks),
        filename=filename,
        content_type=content_type,
    )


__all__ = [
    "DEFAULT_ALLOWED_MIME_TYPES",
    "DEFAULT_MAX_UPLOAD_SIZE_BYTES",
    "UploadSecurityError",
    "ValidatedUpload",
    "configured_max_upload_size",
    "configured_mime_types",
    "read_validated_upload",
    "validate_upload_metadata",
]
