"""
Diagram explanation using a vision-capable LLM, grounded with matching
textbook content so the explanation stays curriculum-accurate rather than
a generic image caption.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from common.llm_client import call_gemini_with_image
from knowledge_layer.retriever import format_results_for_llm, retrieve

logger = logging.getLogger(__name__)

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _encode_image(image_path: Path) -> tuple[str, str]:
    media_type = _MEDIA_TYPES.get(image_path.suffix.lower())
    if media_type is None:
        raise ValueError(f"Unsupported image type: {image_path.suffix}")

    data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    return data, media_type


def explain_diagram(
    image_path: str | Path,
    subject: str | None = None,
) -> str:
    """Return a plain-language, curriculum-grounded explanation of a diagram."""

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_b64, media_type = _encode_image(image_path)

    grounding_query = f"{subject or ''} diagram".strip()

    context = format_results_for_llm(
        retrieve(
            grounding_query,
            subject=subject,
            top_k=3,
        )
    )

    prompt = (
        "A student has photographed this diagram from their textbook and wants "
        "it explained simply and accurately. Use the reference textbook excerpts "
        "below if they match what's in the image; ignore them if they don't.\n\n"
        f"Reference excerpts:\n{context}\n\n"
        "Explain what the diagram shows, label its key parts, and keep the "
        "language appropriate for a school student."
    )

    explanation = call_gemini_with_image(
        prompt=prompt,
        image_b64=image_b64,
        media_type=media_type,
    )

    logger.info(
        "Generated diagram explanation for %s",
        image_path.name,
    )

    return explanation