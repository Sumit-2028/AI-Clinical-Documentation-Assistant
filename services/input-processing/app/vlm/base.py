from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VLMResult:
    text: str
    confidence: float
    model: str


class VLMAdapter(Protocol):
    model_name: str

    def analyze(
        self,
        content: bytes,
        *,
        ocr_text: str,
        filename: str | None = None,
    ) -> VLMResult:
        ...
