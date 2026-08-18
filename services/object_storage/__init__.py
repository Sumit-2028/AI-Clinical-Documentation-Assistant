"""Object storage transport for original uploaded documents.

Service layers depend on the ``ObjectStorage`` protocol only.  This package
provides transport, configuration, key construction, and failure handling; it
contains no clinical business logic.
"""

from .base import ObjectStorage, PresignedURL, StoredObject, storage_uri_for
from .errors import (
    ObjectStorageConfigurationError,
    ObjectStorageError,
    ObjectStorageNotFoundError,
    ObjectStorageRequestError,
    ObjectStorageTimeoutError,
)
from .factory import build_object_storage, configured_presign_expiry
from .keys import build_source_key, canonical_extension, download_filename
from .mock import InMemoryObjectStorage
from .s3 import S3ObjectStorage


__all__ = [
    "InMemoryObjectStorage",
    "ObjectStorage",
    "ObjectStorageConfigurationError",
    "ObjectStorageError",
    "ObjectStorageNotFoundError",
    "ObjectStorageRequestError",
    "ObjectStorageTimeoutError",
    "PresignedURL",
    "S3ObjectStorage",
    "StoredObject",
    "build_object_storage",
    "build_source_key",
    "canonical_extension",
    "configured_presign_expiry",
    "download_filename",
    "storage_uri_for",
]
