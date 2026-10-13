"""
MCP tool: search_curriculum — retrieves curriculum content for a student's
question from the Knowledge Layer, flagged when the topic is a known weak
point so the LLM can slow down and explain from first principles instead
of giving the same depth of answer it would to a topic the student already
knows well.
"""

from __future__ import annotations

from knowledge_layer.retriever import format_results_for_llm, retrieve
from personalization_layer.sequence_tracker import get_weak_topics_lstm


def search_curriculum(
    query: str,
    subject: str | None = None,
    grade: str | None = None,
    student_id: str | None = None,
) -> str:
    """Search NCERT/open-textbook content for the given query.

    Args:
        query: The student's question or topic in natural language.
        subject: Optional subject filter, e.g. "Math".
        grade: Currently informational only — the pilot indexes one grade
            at a time, so this is reserved for when multiple grades share
            an index.
        student_id: Optional — when provided, the result is flagged if this
            looks like a recurring weak topic for that student.
    """

    results = retrieve(
        query,
        subject=subject,
        source_type="ncert",
    )

    content = format_results_for_llm(results)

    if student_id:
        # Simple keyword match against known weak topics for now — this is
        # a deliberately cheap heuristic to start with; swapping in
        # embedding similarity between `query` and each weak topic name
        # would catch paraphrased repeats ("what's a fraction" vs "explain
        # fractions") that plain substring matching misses.
        weak_topics = {
            w["topic"].lower()
            for w in get_weak_topics_lstm(
                student_id,
            )
        }

        query_lower = query.lower()

        if any(topic in query_lower for topic in weak_topics):
            content = (
                "[Note: this is a recurring weak point for this student — "
                "explain from first principles, use a concrete example, "
                "and check understanding before moving on.]\n\n"
                + content
            )

    return content