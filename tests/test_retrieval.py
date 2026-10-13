"""
Tests for the chunking logic and result-formatting helper. Neither needs
ChromaDB or the embedding model installed, since both are imported lazily
inside their respective classes/functions — these tests exercise pure
Python logic only.
"""

from knowledge_layer.ingest import chunk_text
from knowledge_layer.retriever import format_results_for_llm
from knowledge_layer.vector_store import SearchResult


def test_chunk_text_respects_size_and_overlap():
    words = [f"word{i}" for i in range(50)]
    text = " ".join(words)

    chunks = chunk_text(
        text,
        chunk_size_words=20,
        overlap_words=5,
    )

    assert len(chunks) > 1

    first_chunk_words = chunks[0].split()

    assert len(first_chunk_words) == 20

    # the overlap region should reappear at the start of the next chunk
    assert first_chunk_words[-5:] == chunks[1].split()[:5]


def test_chunk_text_handles_empty_string():
    assert chunk_text("") == []


def test_chunk_text_rejects_overlap_ge_size():
    import pytest

    with pytest.raises(ValueError):
        chunk_text(
            "some words here",
            chunk_size_words=10,
            overlap_words=10,
        )


def test_format_results_for_llm_handles_empty_list():
    assert "No relevant context was retrieved." in format_results_for_llm([])


def test_format_results_for_llm_includes_citation():
    results = [
        SearchResult(
            text="Photosynthesis converts light to energy.",
            metadata={
                "subject": "Science",
                "source_file": "ch4.pdf",
            },
            distance=0.1,
        )
    ]

    rendered = format_results_for_llm(results)

    assert "Science" in rendered
    assert "ch4.pdf" in rendered