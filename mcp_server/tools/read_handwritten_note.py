"""
MCP tool: read_handwritten_note — wraps the OCR pipeline.
"""

from __future__ import annotations

from multimodal.ocr import read_handwritten_note as _read_handwritten_note


def read_handwritten_note(image_path: str) -> str:
    """Transcribe a photographed handwritten note to text.

    Args:
        image_path: Path to the photographed note (png/jpg/jpeg/webp).
    """

    return _read_handwritten_note(image_path)