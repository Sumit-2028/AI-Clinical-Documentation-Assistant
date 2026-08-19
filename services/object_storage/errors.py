"""Storage errors shared by all object storage implementations."""


class ObjectStorageError(RuntimeError):
    """Base class for expected object storage failures."""


class ObjectStorageConfigurationError(ObjectStorageError):
    """The storage backend cannot be used with the current configuration."""


class ObjectStorageTimeoutError(ObjectStorageError):
    """The storage backend did not respond within the configured timeout."""


class ObjectStorageRequestError(ObjectStorageError):
    """The storage backend rejected the request or could not be reached."""


class ObjectStorageNotFoundError(ObjectStorageError):
    """The requested object does not exist."""


__all__ = [
    "ObjectStorageConfigurationError",
    "ObjectStorageError",
    "ObjectStorageNotFoundError",
    "ObjectStorageRequestError",
    "ObjectStorageTimeoutError",
]
