"""Content fingerprints for immutability + duplicate detection.

- SHA-256: exact-content identity of the stored original (integrity + exact-dup key).
- Perceptual hash (pHash): near-duplicate signal for images. PDFs need a rasterizer
  (poppler) that isn't in the base image, so PDF pHash is left None for now and duplicate
  detection (Phase 4) treats it as an optional signal.
"""
from __future__ import annotations

import hashlib
import io


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def perceptual_hash(data: bytes, content_type: str) -> str | None:
    """64-bit difference-hash (dHash) as a 16-char hex string.

    Pillow-only (no scipy/imagehash) so it stays light enough for a serverless bundle. dHash
    resizes to 9x8 grayscale and encodes whether each pixel is brighter than its right neighbor.
    """
    if not content_type.startswith("image/"):
        return None
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("L").resize((9, 8), Image.LANCZOS)
        px = list(img.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                left = px[row * 9 + col]
                right = px[row * 9 + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return f"{bits:016x}"
    except Exception:
        return None
