"""
Thin wrapper around a persistent ChromaDB collection.
Keeping Chroma-specific calls isolated here means the rest of the codebase
only depends on the small interface below, not on ChromaDB's API directly,
so the vector database could later be swapped (e.g. for FAISS or pgvector)
by rewriting only this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from common.config import VECTOR_DB_PATH

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "curriculum_chunks"


@dataclass
class SearchResult:
    text: str
    metadata: dict
    distance: float


class VectorStore:
    """Persistent vector store for curriculum/past-paper chunks."""

    def __init__(self, path=None, collection_name: str = _COLLECTION_NAME):
        import chromadb

        self._client = chromadb.PersistentClient(
            path=str(path or VECTOR_DB_PATH)
        )
        self._collection = self._client.get_or_create_collection(
            collection_name
        )

    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """Insert (or overwrite, by id) a batch of chunks."""
        if not ids:
            return

        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "Upserted %d chunks into '%s'",
            len(ids),
            self._collection.name,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Return the top_k closest chunks to query_embedding."""
        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where or None,
        )

        results = []

        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        for text, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            results.append(
                SearchResult(
                    text=text,
                    metadata=metadata,
                    distance=distance,
                )
            )

        return results

    def count(self) -> int:
        return self._collection.count()