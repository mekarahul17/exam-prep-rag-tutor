"""
Maps (subject, topic) pairs to a stable integer index, so free-text topic
names can be fed into the LSTM as one-hot vectors. Persisted to disk so
the mapping stays consistent between training and inference.
"""

from __future__ import annotations

import json
from pathlib import Path

from common.config import DATA_PROCESSED_DIR

_DEFAULT_VOCAB_PATH = Path(DATA_PROCESSED_DIR) / "topic_vocab.json"


class TopicVocab:
    """Persisted topic <-> index mapping.
    Pass ``path`` to point at a different file — tests use this so they
    never touch real project data.
    """

    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else _DEFAULT_VOCAB_PATH
        self._topic_to_index: dict[str, int] = {}
        if self._path.exists():
            self._topic_to_index = json.loads(self._path.read_text())

    @staticmethod
    def _key(subject: str, topic: str) -> str:
        return f"{subject.strip().lower()}::{topic.strip().lower()}"

    def index_for(
        self,
        subject: str,
        topic: str,
        create_if_missing: bool = True,
    ) -> int | None:
        key = self._key(subject, topic)
        if key not in self._topic_to_index:
            if not create_if_missing:
                return None
            self._topic_to_index[key] = len(self._topic_to_index)
        return self._topic_to_index[key]

    def all_topics(self) -> list[tuple[str, str, int]]:
        """Return (subject, topic, index) for every known topic."""
        result = []
        for key, idx in self._topic_to_index.items():
            subject, topic = key.split("::", 1)
            result.append((subject, topic, idx))
        return result

    def __len__(self) -> int:
        return len(self._topic_to_index)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._topic_to_index, indent=2))