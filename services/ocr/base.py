"""OCR provider contract. Implementations live in services/ocr/providers/."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

BBox = tuple[float, float, float, float]  # normalized (x0,y0,x1,y1) in [0,1]


@dataclass
class OCRWord:
    text: str
    page: int
    bbox: BBox
    confidence: float


@dataclass
class OCRResult:
    pages: int
    words: list[OCRWord] = field(default_factory=list)
    full_text: str = ""
    provider: str = "mock"


@runtime_checkable
class OCRProvider(Protocol):
    name: str

    def extract_text(self, file_bytes: bytes, content_type: str) -> OCRResult: ...
