from .base import OCRResult


class MockOCRAdapter:
    """Deterministic development OCR; provenance explicitly says it is mock."""

    engine_name = "mock-ocr"

    def extract(self, content: bytes, *, filename: str | None = None) -> OCRResult:
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
            )

        lowered = text.lower()
        confidence = 0.78
        if "illegible" in lowered or "unclear" in lowered:
            confidence = 0.45

        return OCRResult(
            text=text,
            confidence=confidence,
            engine=self.engine_name,
        )
