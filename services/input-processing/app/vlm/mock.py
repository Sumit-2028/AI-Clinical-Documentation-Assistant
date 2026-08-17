from .base import VLMResult


class MockVLMAdapter:
    """Deterministic development VLM; provenance explicitly says it is mock."""

    model_name = "mock-vlm"

    def analyze(
        self,
        content: bytes,
        *,
        ocr_text: str,
        filename: str | None = None,
    ) -> VLMResult:
        text = ocr_text.strip()
        return VLMResult(
            text=text,
            confidence=0.88 if text else 0.0,
            model=self.model_name,
        )
