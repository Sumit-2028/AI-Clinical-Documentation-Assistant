from datetime import timezone
from uuid import uuid4

import pytest

from services.object_storage import (
    InMemoryObjectStorage,
    ObjectStorageConfigurationError,
    ObjectStorageNotFoundError,
    ObjectStorageRequestError,
    ObjectStorageTimeoutError,
    S3ObjectStorage,
    build_object_storage,
    build_source_key,
    canonical_extension,
    download_filename,
)
from services.object_storage import s3 as s3_module
from services.object_storage.factory import configured_presign_expiry


class FakeClientError(Exception):
    """Stands in for botocore ClientError, which carries a response dict."""

    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.response = {
            "Error": {"Code": code},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        }


class FakeReadTimeout(Exception):
    pass


class FakeS3Client:
    def __init__(self, *, responses: dict | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[dict] = []

    def _resolve(self, operation: str, params: dict):
        self.calls.append({"operation": operation, "params": params})
        queued = self.responses.get(operation)
        if isinstance(queued, list):
            outcome = queued.pop(0) if queued else {}
        else:
            outcome = queued if queued is not None else {}
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def put_object(self, **params):
        return self._resolve("put_object", params)

    def head_object(self, **params):
        return self._resolve("head_object", params)

    def head_bucket(self, **params):
        return self._resolve("head_bucket", params)

    def create_bucket(self, **params):
        return self._resolve("create_bucket", params)

    def generate_presigned_url(self, operation, Params, ExpiresIn):  # noqa: N803
        self.calls.append(
            {
                "operation": "generate_presigned_url",
                "params": {"op": operation, "Params": Params, "ExpiresIn": ExpiresIn},
            }
        )
        return f"https://example.invalid/{Params['Key']}?expires={ExpiresIn}"


def make_s3(**overrides):
    sleeps: list[float] = []
    client = overrides.pop("client", FakeS3Client())
    storage = S3ObjectStorage(
        bucket="clinical-documents",
        client=client,
        sleep=sleeps.append,
        backoff_seconds=0.01,
        **overrides,
    )
    return storage, client, sleeps


# --- key construction -------------------------------------------------------


def test_source_key_contains_only_opaque_identifiers():
    patient_id = uuid4()
    document_id = uuid4()

    key = build_source_key(patient_id=patient_id, document_id=document_id, prefix="step1")

    assert key == f"step1/patients/{patient_id}/documents/{document_id}/source"
    assert "scan.png" not in key
    assert key.endswith("/source")


def test_source_key_is_stable_across_calls():
    patient_id = uuid4()
    document_id = uuid4()

    first = build_source_key(patient_id=patient_id, document_id=document_id)
    second = build_source_key(patient_id=patient_id, document_id=document_id)

    assert first == second


def test_key_prefix_is_configurable(monkeypatch):
    monkeypatch.setenv("S3_KEY_PREFIX", "archive")

    key = build_source_key(patient_id=uuid4(), document_id=uuid4())

    assert key.startswith("archive/patients/")


def test_download_filename_is_derived_from_document_id_not_upload():
    document_id = uuid4()

    assert download_filename(document_id, "image/png") == f"{document_id}.png"
    assert canonical_extension("application/pdf; charset=binary") == ".pdf"
    assert canonical_extension("application/x-msdownload") == ""


# --- mock backend -----------------------------------------------------------


def test_in_memory_storage_round_trips_content():
    storage = InMemoryObjectStorage()

    stored = storage.put(key="a/b/source", content=b"scan-bytes", content_type="image/png")

    assert stored.size_bytes == len(b"scan-bytes")
    assert storage.get_content(key="a/b/source") == b"scan-bytes"
    assert storage.head(key="a/b/source").content_type == "image/png"


def test_in_memory_storage_raises_not_found_for_unknown_key():
    storage = InMemoryObjectStorage()

    with pytest.raises(ObjectStorageNotFoundError):
        storage.head(key="missing")


def test_in_memory_presign_returns_timezone_aware_expiry():
    storage = InMemoryObjectStorage()
    storage.put(key="k", content=b"x", content_type="text/plain")

    presigned = storage.presign_get(key="k", expires_in=300, download_filename="doc.txt")

    assert presigned.expires_at.tzinfo is not None
    assert presigned.expires_at.astimezone(timezone.utc) == presigned.expires_at


# --- s3 backend -------------------------------------------------------------


def test_put_sends_bucket_key_and_content_type():
    storage, client, _ = make_s3()

    stored = storage.put(key="k", content=b"bytes", content_type="application/pdf")

    params = client.calls[0]["params"]
    assert params["Bucket"] == "clinical-documents"
    assert params["Key"] == "k"
    assert params["ContentType"] == "application/pdf"
    assert params["ContentLength"] == 5
    assert stored.storage_uri == "s3://clinical-documents/k"


def test_put_omits_encryption_params_when_sse_is_none():
    storage, client, _ = make_s3(sse="none")

    storage.put(key="k", content=b"x", content_type="text/plain")

    assert "ServerSideEncryption" not in client.calls[0]["params"]


def test_put_sends_kms_key_when_configured():
    storage, client, _ = make_s3(sse="aws:kms", sse_kms_key_id="key-1")

    storage.put(key="k", content=b"x", content_type="text/plain")

    params = client.calls[0]["params"]
    assert params["ServerSideEncryption"] == "aws:kms"
    assert params["SSEKMSKeyId"] == "key-1"


def test_server_errors_are_retried_then_raise_request_error():
    client = FakeS3Client(
        responses={
            "put_object": [
                FakeClientError("InternalError", 500),
                FakeClientError("InternalError", 500),
                FakeClientError("InternalError", 500),
            ]
        }
    )
    storage, client, sleeps = make_s3(client=client, max_retries=2)

    with pytest.raises(ObjectStorageRequestError):
        storage.put(key="k", content=b"x", content_type="text/plain")

    assert len(client.calls) == 3
    assert sleeps == [0.01, 0.02]


def test_access_denied_is_not_retried():
    client = FakeS3Client(responses={"put_object": FakeClientError("AccessDenied", 403)})
    storage, client, sleeps = make_s3(client=client, max_retries=2)

    with pytest.raises(ObjectStorageConfigurationError):
        storage.put(key="k", content=b"x", content_type="text/plain")

    assert len(client.calls) == 1
    assert sleeps == []


def test_timeouts_are_retried_then_raise_timeout_error(monkeypatch):
    monkeypatch.setattr(s3_module, "ReadTimeoutError", FakeReadTimeout)
    client = FakeS3Client(
        responses={"head_object": [FakeReadTimeout(), FakeReadTimeout()]}
    )
    storage, client, _ = make_s3(client=client, max_retries=1)

    with pytest.raises(ObjectStorageTimeoutError):
        storage.head(key="k")

    assert len(client.calls) == 2


def test_missing_object_raises_not_found():
    client = FakeS3Client(responses={"head_object": FakeClientError("404", 404)})
    storage, _, _ = make_s3(client=client)

    with pytest.raises(ObjectStorageNotFoundError):
        storage.head(key="k")


def test_presign_passes_disposition_and_content_type():
    client = FakeS3Client(
        responses={"head_object": {"ContentType": "image/png", "ContentLength": 12}}
    )
    storage, client, _ = make_s3(client=client)

    presigned = storage.presign_get(
        key="k", expires_in=300, download_filename="doc.png"
    )

    signed = next(
        call for call in client.calls if call["operation"] == "generate_presigned_url"
    )
    assert signed["params"]["Params"]["ResponseContentType"] == "image/png"
    assert (
        signed["params"]["Params"]["ResponseContentDisposition"]
        == 'attachment; filename="doc.png"'
    )
    assert presigned.size_bytes == 12
    assert presigned.expires_at.tzinfo is not None


def test_bucket_is_not_created_unless_explicitly_enabled():
    storage, client, _ = make_s3(create_bucket_if_missing=False)

    storage.put(key="k", content=b"x", content_type="text/plain")

    assert [call["operation"] for call in client.calls] == ["put_object"]


def test_bucket_is_created_once_when_enabled():
    client = FakeS3Client(
        responses={"head_bucket": [FakeClientError("404", 404), {}]}
    )
    storage, client, _ = make_s3(client=client, create_bucket_if_missing=True)

    storage.put(key="k", content=b"x", content_type="text/plain")
    storage.put(key="k2", content=b"y", content_type="text/plain")

    operations = [call["operation"] for call in client.calls]
    assert operations.count("create_bucket") == 1
    assert operations.count("head_bucket") == 1


def test_missing_boto3_raises_configuration_error(monkeypatch):
    monkeypatch.setattr(s3_module, "boto3", None)
    storage = S3ObjectStorage(bucket="clinical-documents")

    with pytest.raises(ObjectStorageConfigurationError):
        _ = storage.client


def test_empty_bucket_is_rejected():
    with pytest.raises(ObjectStorageConfigurationError):
        S3ObjectStorage(bucket="")


# --- factory ----------------------------------------------------------------


def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("STEP1_STORAGE_MODE", raising=False)

    assert isinstance(build_object_storage(), InMemoryObjectStorage)


def test_factory_returns_s3_when_selected(monkeypatch):
    monkeypatch.setenv("STEP1_STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_BUCKET", "bucket-a")

    storage = build_object_storage()

    assert isinstance(storage, S3ObjectStorage)
    assert storage.bucket == "bucket-a"


def test_factory_falls_back_to_mock_for_unknown_mode():
    assert isinstance(build_object_storage("gcs"), InMemoryObjectStorage)


def test_presign_expiry_is_clamped(monkeypatch):
    monkeypatch.setenv("S3_PRESIGN_EXPIRY_SECONDS", "999999")
    assert configured_presign_expiry() == 3600

    monkeypatch.setenv("S3_PRESIGN_EXPIRY_SECONDS", "5")
    assert configured_presign_expiry() == 60

    monkeypatch.setenv("S3_PRESIGN_EXPIRY_SECONDS", "not-a-number")
    assert configured_presign_expiry() == 300


# --- logging discipline -----------------------------------------------------


def test_storage_logs_never_contain_keys_or_identifiers(caplog):
    patient_id = uuid4()
    document_id = uuid4()
    key = build_source_key(patient_id=patient_id, document_id=document_id)
    storage, _, _ = make_s3()

    with caplog.at_level("INFO", logger="clinical_memory.storage"):
        storage.put(key=key, content=b"x", content_type="text/plain")

    emitted = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert key not in emitted
    assert str(patient_id) not in emitted
    assert str(document_id) not in emitted


# --- deployment configuration -----------------------------------------------


def test_minio_style_configuration_uses_path_addressing(monkeypatch):
    monkeypatch.setenv("STEP1_STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("S3_FORCE_PATH_STYLE", "true")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "minioadmin")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "minioadmin")

    storage = build_object_storage()

    assert storage.endpoint_url == "http://minio:9000"
    assert storage.force_path_style is True
    assert storage.access_key_id == "minioadmin"


def test_aws_style_configuration_drops_endpoint_and_static_credentials(monkeypatch):
    # Going to real AWS is configuration only: no endpoint override, virtual
    # host addressing, and credentials from the instance role.
    monkeypatch.setenv("STEP1_STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "")
    monkeypatch.setenv("S3_FORCE_PATH_STYLE", "false")
    monkeypatch.delenv("S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("S3_SSE", "aws:kms")
    monkeypatch.setenv("S3_SSE_KMS_KEY_ID", "arn:aws:kms:region:acct:key/id")

    storage = build_object_storage()

    assert storage.endpoint_url is None
    assert storage.force_path_style is False
    assert storage.access_key_id is None
    assert storage.sse == "aws:kms"


def test_bucket_creation_is_off_by_default(monkeypatch):
    monkeypatch.setenv("STEP1_STORAGE_MODE", "s3")
    monkeypatch.delenv("S3_CREATE_BUCKET_IF_MISSING", raising=False)

    assert build_object_storage().create_bucket_if_missing is False
