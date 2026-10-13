"""
One-off script: parse every PDF under data/raw/, chunk it, embed the
chunks, and store everything in the vector database.

Usage:
    python scripts/build_index.py
"""

from __future__ import annotations

import logging

from common.config import DATA_RAW_DIR, configure_logging
from knowledge_layer.embed import embed_texts
from knowledge_layer.ingest import ingest_directory
from knowledge_layer.vector_store import VectorStore


configure_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    chunks = ingest_directory(DATA_RAW_DIR)

    if not chunks:
        logger.warning(
            "No chunks were produced — check that PDFs exist under %s",
            DATA_RAW_DIR,
        )
        return

    texts = [c.text for c in chunks]

    embeddings = embed_texts(texts)

    ids = [
        f"{c.source_type}:{c.source_file}:{c.chunk_index}"
        for c in chunks
    ]

    metadatas = [
        c.to_metadata_dict()
        for c in chunks
    ]

    store = VectorStore()

    store.add(
        ids=ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info(
        "Index build complete. Total chunks in store: %d",
        store.count(),
    )


if __name__ == "__main__":
    main()