"""Storage backend selection.

Mirrors ``build_adapter_bundle`` in the Step 1 adapters: the mode is read from
the environment, defaults to the deterministic mock, and never raises at
construction time.
"""

from __future__ import annotations

import logging

from .base import ObjectStorage
from .config import env_bool, env_clamped_int, env_int, env_value
from .mock import InMemoryObjectStorage
from .s3 import S3ObjectStorage


logger = logging.getLogger("clinical_memory.storage")

DEFAULT_PRESIGN_EXPIRY_SECONDS = 300
MIN_PRESIGN_EXPIRY_SECONDS = 60
MAX_PRESIGN_EXPIRY_SECONDS = 3600


def configured_presign_expiry() -> int:
    return env_clamped_int(
        "S3_PRESIGN_EXPIRY_SECONDS",
        DEFAULT_PRESIGN_EXPIRY_SECONDS,
        minimum=MIN_PRESIGN_EXPIRY_SECONDS,
        maximum=MAX_PRESIGN_EXPIRY_SECONDS,
    )


def build_object_storage(mode: str | None = None) -> ObjectStorage:
    selected_mode = (mode or env_value("STEP1_STORAGE_MODE", "mock") or "mock").lower()

    if selected_mode == "mock":
        return InMemoryObjectStorage()

    if selected_mode != "s3":
        logger.warning(
            "Unknown object storage mode; falling back to mock storage.",
            extra={"mode": selected_mode},
        )
        return InMemoryObjectStorage()

    return S3ObjectStorage(
        bucket=env_value("S3_BUCKET", "clinical-documents") or "clinical-documents",
        region=env_value("S3_REGION", "us-east-1") or "us-east-1",
        endpoint_url=env_value("S3_ENDPOINT_URL"),
        access_key_id=env_value("S3_ACCESS_KEY_ID"),
        secret_access_key=env_value("S3_SECRET_ACCESS_KEY"),
        force_path_style=env_bool("S3_FORCE_PATH_STYLE", True),
        sse=env_value("S3_SSE", "none") or "none",
        sse_kms_key_id=env_value("S3_SSE_KMS_KEY_ID"),
        create_bucket_if_missing=env_bool("S3_CREATE_BUCKET_IF_MISSING", False),
        send_checksum=env_bool("S3_SEND_CHECKSUM", True),
        timeout_seconds=env_int("S3_TIMEOUT_SECONDS", 10, minimum=1),
        max_retries=env_int("S3_MAX_RETRIES", 2),
    )


__all__ = [
    "DEFAULT_PRESIGN_EXPIRY_SECONDS",
    "MAX_PRESIGN_EXPIRY_SECONDS",
    "MIN_PRESIGN_EXPIRY_SECONDS",
    "build_object_storage",
    "configured_presign_expiry",
]
