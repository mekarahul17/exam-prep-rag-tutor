"""Handwritten-note transcription with vision-first OCR and Tesseract fallback."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".bmp": "image/png", ".tif": "image/png",
    ".tiff": "image/png",
}


def _image_payload(path: Path) -> tuple[str, str]:
    from PIL import Image
    with Image.open(path) as image:
        image = image.convert("RGB")
        from io import BytesIO
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/png"


def _gemini_transcription(path: Path) -> str:
    from common.llm_client import call_gemini_with_image
    image_b64, media_type = _image_payload(path)
    prompt = """Transcribe this student's handwritten study notes faithfully.
Return ONLY the transcription, with no introduction or explanation.
Preserve headings, bullet points, line order, numbers, signs, subscripts and
mathematical expressions. Convert clear mathematical expressions to valid LaTeX
inside $...$ or $$...$$. In particular distinguish + from -, x from ×, 2 from
z, superscripts such as x², square-root signs, fractions, braces and parentheses.
Do not invent unreadable text. Mark genuinely unclear spans as [unclear].
Do not solve or explain the notes; transcribe them."""
    result = call_gemini_with_image(
        prompt=prompt, image_b64=image_b64, media_type=media_type
    )
    return (result or "").strip()


def _tesseract_fallback(path: Path) -> str:
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    import pytesseract

    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        if image.width < 1400:
            scale = min(3, max(2, 1400 // max(1, image.width)))
            image = image.resize((image.width * scale, image.height * scale))
        gray = ImageOps.grayscale(image)
        gray = ImageEnhance.Contrast(gray).enhance(1.7)
        variants = [gray, gray.filter(ImageFilter.SHARPEN),
                    gray.point(lambda p: 255 if p > 155 else 0)]
        candidates = []
        for variant in variants:
            for psm in (6, 11):
                value = pytesseract.image_to_string(
                    variant, config=f"--oem 3 --psm {psm}"
                ).strip()
                if value:
                    candidates.append(value)
        if not candidates:
            return ""
        return max(candidates, key=lambda value: (len(value), sum(ch.isalnum() for ch in value)))


def read_handwritten_note(image_path: str | Path) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    try:
        text = _gemini_transcription(path)
        if text and len(text) >= 5:
            logger.info("Vision OCR extracted %d characters from %s", len(text), path.name)
            return text
    except Exception:
        logger.exception("Vision OCR failed; falling back to Tesseract")

    text = _tesseract_fallback(path)
    if not text:
        raise ValueError("No readable text was detected. Try a sharper, well-lit image.")
    logger.info("Tesseract fallback extracted %d characters from %s", len(text), path.name)
    return text
