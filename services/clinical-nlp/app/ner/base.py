from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EntitySpan:
    text: str
    start: int
    end: int
    entity_type: str
    confidence: float


class NERAdapter(Protocol):
    model_name: str

    def extract(self, text: str) -> list[EntitySpan]:
        ...
