"""
Handwriting/scanned-note OCR.

Baseline implementation uses Tesseract via pytesseract, with light image
preprocessing (grayscale + threshold) to improve accuracy on photographed
notebook pages. Tesseract's handwriting accuracy is limited; if accuracy
on real student handwriting proves too low, swap this implementation for
a fine-tuned model such as TrOCR without changing the function signature.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _preprocess(image):
    """Grayscale + threshold to make faint pencil/pen strokes more legible."""
    from PIL import ImageOps

    gray = ImageOps.grayscale(image)

    return gray.point(lambda p: 255 if p > 150 else 0)


def read_handwritten_note(image_path: str | Path) -> str:
    """Return the best-effort transcription of a photographed handwritten note."""
    from PIL import Image
    import pytesseract

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as image:
        processed = _preprocess(image)
        text = pytesseract.image_to_string(processed)

    cleaned = "\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )

    logger.info(
        "OCR extracted %d characters from %s",
        len(cleaned),
        image_path.name,
    )

    return cleaned