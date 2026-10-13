"""
MCP tool: explain_diagram — wraps the multimodal vision pipeline.
"""

from __future__ import annotations

from multimodal.vision import explain_diagram as _explain_diagram


def explain_diagram(
    image_path: str,
    subject: str | None = None,
) -> str:
    """Explain a photographed diagram, grounded in matching textbook content.

    Args:
        image_path: Path to the photographed diagram (png/jpg/jpeg/webp).
        subject: Optional subject hint to improve grounding, e.g. "Science".
    """

    return _explain_diagram(
        image_path,
        subject=subject,
    )