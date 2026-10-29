
"""
Sequence-aware mastery tracker using Deep Knowledge Tracing (DKT).

Reads student interaction history from MongoDB Atlas and uses the
trained LSTM model to predict topic mastery.
"""

from __future__ import annotations

import re
from pathlib import Path

import torch

from common.config import DATA_PROCESSED_DIR, WEAK_TOPIC_THRESHOLD
from personalization_layer.mongodb import interaction_logs_collection
from personalization_layer.lstm_model import DKTModel
from personalization_layer.topic_vocab import TopicVocab
from personalization_layer.tracker import get_weak_topics

_MODEL_PATH = Path(DATA_PROCESSED_DIR) / "dkt_model.pt"
_MIN_INTERACTIONS_FOR_LSTM = 20

_GENERIC_TOPIC_NAMES = {
    "science",
    "math",
    "maths",
    "mathematics",
    "general",
    "general science",
    "general mathematics",
    "unknown",
    "other",
    "others",
}


def _normalize(value: str) -> str:
    """Normalize subject/topic labels for consistent comparison."""
    return re.sub(r"[\s_-]+", " ", str(value).strip().lower())


def _is_valid_topic(topic: str) -> bool:
    """Reject empty or generic topic labels."""
    normalized = _normalize(topic)

    return bool(normalized) and normalized not in _GENERIC_TOPIC_NAMES


def _load_model_and_vocab():
    vocab = TopicVocab()

    if len(vocab) == 0 or not _MODEL_PATH.exists():
        return None

    try:
        checkpoint = torch.load(
            _MODEL_PATH,
            map_location="cpu",
            weights_only=True,
        )

        num_topics = len(vocab)
        model = DKTModel(num_topics=num_topics)

        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
        else:
            model.load_state_dict(checkpoint)

        model.eval()

        return model, vocab

    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        print(f"DKT model could not be loaded: {error}")
        return None


def _get_interactions(student_id: str):
    rows = interaction_logs_collection.find(
        {"student_id": student_id},
        {
            "_id": 0,
            "subject": 1,
            "topic": 1,
            "correct": 1,
            "created_at": 1,
        },
    ).sort("created_at", 1)

    return [
        {
            "subject": row["subject"],
            "topic": row["topic"],
            "correct": row["correct"],
        }
        for row in rows
        if row.get("subject")
        and row.get("topic")
        and isinstance(row.get("correct"), bool)
    ]


def _encode_interactions(interactions, vocab: TopicVocab):
    num_topics = len(vocab)
    sequence = []

    for interaction in interactions:
        if not _is_valid_topic(interaction["topic"]):
            continue

        idx = vocab.index_for(
            interaction["subject"],
            interaction["topic"],
            create_if_missing=False,
        )

        if idx is None:
            continue

        vector = torch.zeros(num_topics * 2)

        if interaction["correct"]:
            vector[idx] = 1.0
        else:
            vector[num_topics + idx] = 1.0

        sequence.append(vector)

    if not sequence:
        return None

    return torch.stack(sequence).unsqueeze(0)


def _filter_topics_by_subject(topics, subject: str | None = None):
    """Filter generic topics and optionally restrict results to one subject."""
    filtered = []

    for item in topics:
        topic = item.get("topic", "")
        topic_subject = item.get("subject", "")

        if not _is_valid_topic(topic):
            continue

        if subject and _normalize(topic_subject) != _normalize(subject):
            continue

        filtered.append(item)

    return filtered


def get_weak_topics_lstm(
    student_id: str,
    subject: str | None = None,
):
    loaded = _load_model_and_vocab()

    if loaded is None:
        return _filter_topics_by_subject(
            get_weak_topics(student_id, subject=subject),
            subject,
        )

    model, vocab = loaded
    interactions = _get_interactions(student_id)

    if len(interactions) < _MIN_INTERACTIONS_FOR_LSTM:
        return _filter_topics_by_subject(
            get_weak_topics(student_id, subject=subject),
            subject,
        )

    x = _encode_interactions(interactions, vocab)

    if x is None:
        return _filter_topics_by_subject(
            get_weak_topics(student_id, subject=subject),
            subject,
        )

    with torch.no_grad():
        predictions = model(x)

    latest = predictions[0, -1]
    weak_topics = []

    for topic_subject, topic, idx in vocab.all_topics():

        if not _is_valid_topic(topic):
            continue

        if subject and _normalize(topic_subject) != _normalize(subject):
            continue

        mastery = float(latest[idx])

        if mastery < WEAK_TOPIC_THRESHOLD:
            weak_topics.append({
                "subject": topic_subject,
                "topic": topic,
                "mastery_score": round(mastery, 2),
            })

    return sorted(
        weak_topics,
        key=lambda item: item["mastery_score"],
    )
