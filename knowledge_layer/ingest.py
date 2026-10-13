"""
Step 1 of the RAG pipeline: parse raw PDFs into metadata-tagged text chunks.

Expected directory layout under data/raw/:

data/raw/ncert/<subject>/<any_name>.pdf
data/raw/past_papers/<subject>/<any_name>.pdf
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single retrieval-sized piece of text plus its provenance."""

    text: str
    subject: str
    source_type: str
    source_file: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    def to_metadata_dict(self) -> dict:
        """Flatten fields into the dict shape Chroma expects for metadata."""

        return {
            "subject": self.subject,
            "source_type": self.source_type,
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
            **self.metadata,
        }


def load_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from a single PDF, page by page."""

    reader = PdfReader(str(pdf_path))

    pages_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as exc:
            logger.warning(
                "Failed to extract page %d of %s: %s",
                page_number,
                pdf_path.name,
                exc,
            )

    return "\n".join(pages_text)


def chunk_text(
    text: str,
    chunk_size_words: int = 220,
    overlap_words: int = 40,
) -> list[str]:
    """Split text into overlapping word-count-bounded chunks."""

    words = text.split()

    if not words:
        return []

    if overlap_words >= chunk_size_words:
        raise ValueError(
            "overlap_words must be smaller than chunk_size_words"
        )

    step = chunk_size_words - overlap_words

    chunks = []

    for start in range(0, len(words), step):
        window = words[start:start + chunk_size_words]

        if not window:
            break

        chunks.append(" ".join(window))

        if start + chunk_size_words >= len(words):
            break

    return chunks


def _discover_pdfs(root: Path) -> list[tuple[Path, str]]:
    """Return PDF paths and their subject names."""

    pairs = []

    if not root.exists():
        logger.warning("Source directory does not exist: %s", root)
        return pairs

    for subject_dir in sorted(
        p for p in root.iterdir() if p.is_dir()
    ):
        for pdf_path in sorted(subject_dir.glob("*.pdf")):
            pairs.append((pdf_path, subject_dir.name))

    return pairs


def ingest_directory(
    raw_dir: Path,
    chunk_size_words: int = 220,
    overlap_words: int = 40,
) -> list[Chunk]:
    """Extract text from PDFs and return metadata-tagged chunks."""

    raw_dir = Path(raw_dir)

    all_chunks: list[Chunk] = []

    for source_type, folder_name in (
        ("ncert", "ncert"),
        ("past_paper", "past_papers"),
    ):
        for pdf_path, subject in _discover_pdfs(
            raw_dir / folder_name
        ):
            logger.info(
                "Parsing %s (%s / %s)",
                pdf_path.name,
                source_type,
                subject,
            )

            text = load_pdf_text(pdf_path)

            for index, piece in enumerate(
                chunk_text(
                    text,
                    chunk_size_words,
                    overlap_words,
                )
            ):
                all_chunks.append(
                    Chunk(
                        text=piece,
                        subject=subject,
                        source_type=source_type,
                        source_file=pdf_path.name,
                        chunk_index=index,
                    )
                )

    logger.info(
        "Ingested %d chunks from %s",
        len(all_chunks),
        raw_dir,
    )

    return all_chunks