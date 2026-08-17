from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float
    engine: str


class OCRAdapter(Protocol):
    engine_name: str

    def extract(self, content: bytes, *, filename: str | None = None) -> OCRResult:
        ...
