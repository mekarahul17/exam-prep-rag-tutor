"""
Step 2 of the RAG pipeline: turn text chunks into vector embeddings.
"""

from __future__ import annotations

import logging
import threading

from common.config import EMBEDDING_MODEL_NAME


logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazily load the embedding model once per process."""

    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Loading embedding model: %s",
                    EMBEDDING_MODEL_NAME,
                )

                _model = SentenceTransformer(
                    EMBEDDING_MODEL_NAME
                )

    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input string."""

    if not texts:
        return []

    model = _get_model()

    vectors = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""

    return embed_texts([query])[0]