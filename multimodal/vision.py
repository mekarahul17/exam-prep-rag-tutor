"""Vision-based textbook diagram explanation with automatic subject detection.

When the caller supplies Mathematics or Science, that selection is respected.
When it supplies Auto/None, Gemini first identifies the subject and topic from
 the image, then curriculum retrieval is filtered using the detected subject.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from common.llm_client import call_gemini_with_image
from knowledge_layer.retriever import format_results_for_llm, retrieve

logger = logging.getLogger(__name__)

VALID_SUBJECTS = {"Mathematics", "Science"}


def _encode_image(path: Path) -> tuple[str, str]:
    """Normalize supported image formats and EXIF orientation to PNG."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/png"


def _normalise_subject(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned in {"math", "maths", "mathematics"}:
        return "Mathematics"
    if cleaned in {"science", "physics", "chemistry", "biology", "environmental science"}:
        return "Science"
    return None


def _detect_image_subject(image_b64: str, media_type: str) -> tuple[str | None, str]:
    """Classify an image as Mathematics/Science and extract its main topic."""
    prompt = """You are classifying a school textbook or study image.
Inspect the image itself, including equations, labels, diagrams and text.
Return ONLY one valid JSON object with these keys:
{
  "subject": "Mathematics" or "Science" or "Other",
  "topic": "short topic name"
}
Use Mathematics for arithmetic, algebra, geometry, trigonometry, statistics,
calculus, equations and mathematical proofs. Use Science for physics,
chemistry, biology and general science diagrams or concepts. If the image is
not clearly a school Mathematics or Science item, use Other. Do not guess.
"""
    raw = call_gemini_with_image(
        prompt=prompt,
        image_b64=image_b64,
        media_type=media_type,
    )
    if not raw:
        logger.warning("Vision subject classifier returned an empty response")
        return None, "textbook diagram"

    candidate = raw.strip()
    # Tolerate code fences or brief surrounding text while still parsing JSON.
    match = re.search(r"\{.*?\}", candidate, flags=re.DOTALL)
    if match:
        candidate = match.group(0)
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse image subject classification: %r", raw[:300])
        return None, "textbook diagram"

    subject = _normalise_subject(str(payload.get("subject", "")))
    topic = str(payload.get("topic", "textbook diagram")).strip()
    if not topic or len(topic) > 120:
        topic = "textbook diagram"
    return subject, topic


def explain_diagram(
    image_path: str | Path,
    subject: str | None = None,
) -> str:
    """Explain a diagram, using automatic subject detection unless overridden."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    image_b64, media_type = _encode_image(path)
    requested_subject = _normalise_subject(subject)
    if requested_subject:
        detected_subject = requested_subject
        topic = "textbook diagram"
        subject_source = "user-selected"
    else:
        detected_subject, topic = _detect_image_subject(image_b64, media_type)
        subject_source = "AI-detected" if detected_subject else "not confidently identified"

    # Use a subject-filtered retrieval only when the image classifier is confident.
    # Otherwise search broadly using the topic so an uncertain classification
    # does not force the request into the wrong subject index.
    retrieval_query = f"{detected_subject or ''} {topic} diagram explanation".strip()
    retrieved = retrieve(retrieval_query, subject=detected_subject, top_k=3)
    context = format_results_for_llm(retrieved)

    prompt = f"""You are an accurate, student-friendly textbook tutor.
Explain the uploaded diagram/image. Read visible labels carefully; describe
its purpose, components, relationships and process step by step. Do not invent
labels or details that cannot be seen. If the reference passages do not match
the image, ignore them and say matching curriculum material was unavailable.

Detected subject: {detected_subject or 'Uncertain / not classified'}
Topic estimate: {topic}
Subject selection source: {subject_source}

Reference textbook excerpts (use only if relevant):
{context or 'No matching curriculum passages retrieved.'}

Format the answer as clean Markdown. Use $...$ for inline mathematics and
$$...$$ for displayed equations. Do not escape Markdown headings, bold
markers or list markers with backslashes.
"""
    answer = call_gemini_with_image(
        prompt=prompt,
        image_b64=image_b64,
        media_type=media_type,
    )
    if not answer or not answer.strip():
        raise RuntimeError("The vision model returned an empty explanation.")

    label = detected_subject or "Not confidently identified"
    logger.info(
        "Generated diagram explanation for %s (subject=%s, source=%s)",
        path.name,
        label,
        subject_source,
    )
    return f"**Detected subject:** {label}\n\n{answer.strip()}"
