"""
Shared configuration for the Exam Prep RAG Tutor.

Values are loaded from environment variables (via a .env file) with
sensible defaults for local development. Import this module instead of
reading os.environ directly elsewhere in the codebase.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# --- Pilot scope -------------------------------------------------------------

SUBJECTS: list[str] = os.getenv(
    "SUBJECTS",
    "Math,Science",
).split(",")

GRADE: str = os.getenv(
    "GRADE",
    "Class 10",
)


# --- Paths -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = Path(
    os.getenv(
        "DATA_RAW_DIR",
        str(BASE_DIR / "data" / "raw"),
    )
)

DATA_PROCESSED_DIR = Path(
    os.getenv(
        "DATA_PROCESSED_DIR",
        str(BASE_DIR / "data" / "processed"),
    )
)

VECTOR_DB_PATH = Path(
    os.getenv(
        "VECTOR_DB_PATH",
        str(DATA_PROCESSED_DIR / "vector_store"),
    )
)


# --- Database ----------------------------------------------------------------

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./personalization.db",
)


# --- LLM ---------------------------------------------------------------------

# --- LLM ---------------------------------------------------------------------

GEMINI_API_KEY: str = os.getenv(
    "GEMINI_API_KEY",
    "",
)

GEMINI_MODEL: str = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)


# --- Embeddings ---------------------------------------------------------------

EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "all-MiniLM-L6-v2",
)


# --- Retrieval ----------------------------------------------------------------

CHUNK_SIZE_WORDS: int = int(
    os.getenv(
        "CHUNK_SIZE_WORDS",
        "220",
    )
)

CHUNK_OVERLAP_WORDS: int = int(
    os.getenv(
        "CHUNK_OVERLAP_WORDS",
        "40",
    )
)

DEFAULT_TOP_K: int = int(
    os.getenv(
        "DEFAULT_TOP_K",
        "5",
    )
)


# --- Personalization ----------------------------------------------------------

MASTERY_LEARNING_RATE: float = float(
    os.getenv(
        "MASTERY_LEARNING_RATE",
        "0.25",
    )
)

WEAK_TOPIC_THRESHOLD: float = float(
    os.getenv(
        "WEAK_TOPIC_THRESHOLD",
        "0.5",
    )
)


def configure_logging(level: int = logging.INFO) -> None:
    """Set up a consistent logging format across the whole project."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )