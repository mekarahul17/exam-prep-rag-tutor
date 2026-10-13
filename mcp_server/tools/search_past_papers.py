"""
MCP tool: search_past_papers — retrieves matching questions from indexed
past examination papers.
"""

from __future__ import annotations

from knowledge_layer.retriever import format_results_for_llm, retrieve


def search_past_papers(
    subject: str,
    topic: str | None = None,
    year_range: str | None = None,
) -> str:
    """Search indexed past papers for a subject/topic.

    Args:
        subject: Subject to search within, e.g. "Science".
        topic: Optional topic to narrow the search, e.g. "photosynthesis".
        year_range: Currently informational only — per-year filtering can
            be added once past papers are tagged with a year in metadata.
    """

    query = topic or subject

    results = retrieve(
        query,
        subject=subject,
        source_type="past_paper",
    )

    return format_results_for_llm(results)