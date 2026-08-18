from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.audit.logger import InMemoryAuditLogger
from app.main import create_app
from app.repository import InMemoryDocumentRepository
from app.service import InputProcessingService
from services.object_storage import (
    InMemoryObjectStorage,
    ObjectStorageRequestError,
    build_source_key,
)


class FailingObjectStorage:
    """Storage whose put always fails, to prove the failure is not swallowed."""

    backend_name = "failing"

    def __init__(self) -> None:
        self.put_calls = 0

    def put(self, *, key, content, content_type):
        self.put_calls += 1
        raise ObjectStorageRequestError("storage down")

    def head(self, *, key):
        raise ObjectStorageRequestError("storage down")

    def presign_get(self, *, key, expires_in, download_filename):
        raise ObjectStorageRequestError("storage down")


def make_client(storage=None):
    service = InputProcessingService(
        repository=InMemoryDocumentRepository(),
        audit_logger=InMemoryAuditLogger(),
    )
    storage = storage or InMemoryObjectStorage()
    return TestClient(create_app(service, storage=storage)), service, storage


def upload(client, *, patient_id, endpoint="typed", content=b"Patient has fever"):
    return client.post(
        f"/api/v1/step1/documents/{endpoint}",
        data={"patient_id": str(patient_id), "encounter_id": str(uuid4())},
        files={"file": ("note.txt", content, "text/plain")},
    )


def test_typed_upload_stores_the_original_bytes():
    client, _, storage = make_client()
    patient_id = uuid4()

    response = upload(client, patient_id=patient_id, content=b"Patient has fever")

    assert response.status_code == 200
    document_id = response.json()["document_id"]
    key = build_source_key(patient_id=patient_id, document_id=document_id)
    assert storage.get_content(key=key) == b"Patient has fever"
    assert storage.head(key=key).content_type == "text/plain"


def test_handwritten_upload_stores_the_original_bytes():
    client, _, storage = make_client()
    patient_id = uuid4()

    response = upload(client, patient_id=patient_id, endpoint="handwritten")

    assert response.status_code == 200
    key = build_source_key(
        patient_id=patient_id, document_id=response.json()["document_id"]
    )
    assert storage.head(key=key).size_bytes == len(b"Patient has fever")


def test_stored_key_is_derived_from_the_returned_document_id():
    client, _, storage = make_client()
    patient_id = uuid4()

    document_id = upload(client, patient_id=patient_id).json()["document_id"]

    # The key must be recomputable from the response alone; retrieval depends
    # on this and does not consult the repository for the key.
    expected = build_source_key(patient_id=patient_id, document_id=document_id)
    assert storage.head(key=expected).key == expected


def test_repository_records_the_stored_object():
    client, service, _ = make_client()

    document_id = upload(client, patient_id=uuid4()).json()["document_id"]

    stored = service.get_source_object(UUID(document_id))
    assert stored is not None
    assert stored.storage_uri.startswith("s3://")
    assert stored.checksum_sha256


def test_storage_failure_returns_503_not_a_failed_run():
    storage = FailingObjectStorage()
    client, service, _ = make_client(storage=storage)

    response = upload(client, patient_id=uuid4())

    # The service's broad exception handler would otherwise report this as a
    # 200 with processing_status=failed, which reads as an extraction problem.
    assert response.status_code == 503
    assert storage.put_calls == 1


def test_storage_failure_leaves_no_document_behind():
    client, service, _ = make_client(storage=FailingObjectStorage())

    upload(client, patient_id=uuid4())

    assert service.repository._documents == {}


def test_storage_failure_detail_does_not_leak_backend_information():
    client, _, _ = make_client(storage=FailingObjectStorage())

    response = upload(client, patient_id=uuid4())

    detail = response.json()["detail"]
    assert detail == "Document storage is unavailable."
    assert "storage down" not in detail


def test_multilingual_input_stores_nothing():
    client, service, storage = make_client()

    response = client.post(
        "/api/v1/step1/documents/multilingual",
        json={
            "patient_id": str(uuid4()),
            "encounter_id": str(uuid4()),
            "text_input": "Paciente con fiebre",
            "source_language": "es",
        },
    )

    assert response.status_code == 200
    # There is no uploaded file for this modality.
    assert service.get_source_object(UUID(response.json()["document_id"])) is None


def test_source_object_lookup_rejects_unknown_documents():
    _, service, _ = make_client()

    with pytest.raises(Exception):
        service.get_source_object(uuid4())


def test_service_still_works_without_a_caller_supplied_document_id():
    service = InputProcessingService(
        repository=InMemoryDocumentRepository(),
        audit_logger=InMemoryAuditLogger(),
    )

    output = service.process_typed(
        patient_id=uuid4(),
        encounter_id=uuid4(),
        content=b"Patient has fever",
        filename="note.txt",
    )

    assert output.document_id is not None
