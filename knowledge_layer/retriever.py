"""
Retrieval layer: embed a user query, search the vector store,
and format the results for the LLM.
"""

from __future__ import annotations

from common.config import DEFAULT_TOP_K
from knowledge_layer.embed import embed_query
from knowledge_layer.vector_store import SearchResult, VectorStore


_store = VectorStore()


def retrieve(
    query: str,
    subject: str | None = None,
    source_type: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[SearchResult]:
    """Retrieve the most relevant chunks for a query."""

    where = {}

    if subject and source_type:
        where = {
            "$and": [
                {"subject": {"$eq": subject}},
                {"source_type": {"$eq": source_type}},
            ]
        }
    elif subject:
        where["subject"] = {"$eq": subject}
    elif source_type:
        where["source_type"] = {"$eq": source_type}

    query_embedding = embed_query(query)

    return _store.search(
        query_embedding=query_embedding,
        top_k=top_k,
        where=where or None,
    )


def format_results_for_llm(results: list[SearchResult]) -> str:
    """Format retrieved chunks into context for the language model."""

    if not results:
        return "No relevant context was retrieved."

    parts = []

    for index, result in enumerate(results, start=1):
        source = result.metadata.get("source_file", "unknown")
        subject = result.metadata.get("subject", "unknown")
        source_type = result.metadata.get("source_type", "unknown")

        parts.append(
            f"[Context {index}]\n"
            f"Subject: {subject}\n"
            f"Source type: {source_type}\n"
            f"Source: {source}\n"
            f"Distance: {result.distance:.4f}\n"
            f"{result.text}"
        )

    return "\n\n".join(parts)