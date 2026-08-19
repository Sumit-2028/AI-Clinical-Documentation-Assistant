import zlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.audit.logger import InMemoryAuditLogger
from app.main import create_app
from app.repository import InMemoryDocumentRepository
from app.service import InputProcessingService
from app.upload_security import looks_like_text, sniff_matches


def make_client():
    service = InputProcessingService(
        repository=InMemoryDocumentRepository(),
        audit_logger=InMemoryAuditLogger(),
    )
    return TestClient(create_app(service))


def png_bytes() -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return (
            len(payload).to_bytes(4, "big")
            + body
            + zlib.crc32(body).to_bytes(4, "big")
        )

    header = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 0, 0, 0, 0])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00"))
        + chunk(b"IEND", b"")
    )


JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 16
WEBP = b"RIFF" + (20).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 12
TIFF_LE = b"II*\x00" + b"\x08\x00\x00\x00" + b"\x00" * 16
TIFF_BE = b"MM\x00*" + b"\x00\x00\x00\x08" + b"\x00" * 16
def build_pdf(text: str = "Patient has hypertension") -> bytes:
    """A minimal but genuinely parseable PDF.

    The typed pipeline extracts PDF text with pypdf, so a stub PDF envelope is
    rejected as unreadable.  This builds a real one with a text operator.
    """

    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


PDF = build_pdf()


def upload(client, *, filename, content, content_type, endpoint="typed"):
    return client.post(
        f"/api/v1/step1/documents/{endpoint}",
        data={"patient_id": str(uuid4()), "encounter_id": str(uuid4())},
        files={"file": (filename, content, content_type)},
    )


@pytest.mark.parametrize(
    "filename,content,content_type",
    [
        ("scan.png", png_bytes(), "image/png"),
        ("scan.jpg", JPEG, "image/jpeg"),
        ("scan.webp", WEBP, "image/webp"),
        ("scan.tif", TIFF_LE, "image/tiff"),
        ("scan.tiff", TIFF_BE, "image/tiff"),
        ("report.pdf", PDF, "application/pdf"),
        ("note.txt", b"Patient has hypertension", "text/plain"),
    ],
)
def test_genuine_formats_are_accepted(filename, content, content_type):
    response = upload(
        make_client(), filename=filename, content=content, content_type=content_type
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "filename,content,content_type",
    [
        ("scan.png", PDF, "image/png"),
        ("report.pdf", png_bytes(), "application/pdf"),
        ("scan.jpg", png_bytes(), "image/jpeg"),
        ("note.txt", PDF, "text/plain"),
        ("note.txt", png_bytes(), "text/plain"),
        ("note.txt", b"MZ\x90\x00\x03\x00binary\x00payload", "text/plain"),
        ("note.txt", b"\xff\xfe\xfd invalid utf-8", "text/plain"),
    ],
)
def test_spoofed_content_is_rejected(filename, content, content_type):
    response = upload(
        make_client(), filename=filename, content=content, content_type=content_type
    )

    assert response.status_code == 415


def test_rejection_message_matches_the_mime_allowlist_message():
    client = make_client()

    spoofed = upload(
        client, filename="scan.png", content=PDF, content_type="image/png"
    )
    disallowed = upload(
        client,
        filename="note.exe",
        content=b"binary",
        content_type="application/x-msdownload",
    )

    assert spoofed.status_code == disallowed.status_code == 415
    assert spoofed.json()["detail"] == disallowed.json()["detail"]


def test_check_can_be_disabled_for_legacy_behaviour(monkeypatch):
    monkeypatch.setenv("UPLOAD_MAGIC_BYTE_CHECK", "false")

    response = upload(
        make_client(), filename="scan.png", content=PDF, content_type="image/png"
    )

    assert response.status_code == 200


def test_empty_upload_is_not_rejected_by_signature_check():
    response = upload(
        make_client(), filename="note.txt", content=b"", content_type="text/plain"
    )

    assert response.status_code == 200


def test_utf8_bom_and_whitespace_controls_are_valid_text():
    assert looks_like_text(b"\xef\xbb\xbfPatient notes\r\n\tindented\x0c")


def test_pdf_header_is_tolerated_after_leading_bytes():
    # The PDF spec allows bytes before the header; scanners sometimes emit them.
    assert sniff_matches(b"\n\n" + PDF, "application/pdf")
    assert not sniff_matches(b"x" * 2048 + PDF, "application/pdf")


def test_unknown_declared_types_are_not_sniffed():
    # The MIME allowlist rejects these earlier; the sniffer must not guess.
    assert sniff_matches(b"anything", "application/zip")
