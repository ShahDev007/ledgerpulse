"""OCR provider interface and implementations.

Provider is selected by OCR_PROVIDER (mock | azure | textract). The mock provider
returns deterministic layout from fixtures so the demo and golden evals are stable.
"""
from services.ocr.base import OCRProvider, OCRResult, OCRWord

__all__ = ["OCRProvider", "OCRResult", "OCRWord"]
