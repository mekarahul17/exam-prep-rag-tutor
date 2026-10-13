
"""
Sequence-aware mastery tracker using Deep Knowledge Tracing (DKT).

Loads the trained LSTM + persisted topic vocabulary, converts a student's
interaction history into one-hot (topic, correctness) vectors, and predicts
mastery for every topic. Falls back to the original EMA tracker when there
are fewer than MIN_INTERACTIONS_FOR_LSTM interactions or no trained model.
"""

from __future__ import annotations

from pathlib import Path

import torch

from common.config import DATA_PROCESSED_DIR, WEAK_TOPIC_THRESHOLD
from personalization_layer.database import get_session
from personalization_layer.lstm_model import DKTModel
from personalization_layer.models import InteractionLog
from personalization_layer.topic_vocab import TopicVocab
from personalization_layer.tracker import get_weak_topics

_MODEL_PATH = Path(DATA_PROCESSED_DIR) / "dkt_model.pt"
_MIN_INTERACTIONS_FOR_LSTM = 20


def _load_model_and_vocab():
    """Load the trained DKT model and vocabulary, or return None."""
    vocab = TopicVocab()

    if len(vocab) == 0 or not _MODEL_PATH.exists():
        return None

    checkpoint = torch.load(_MODEL_PATH, map_location="cpu")

    num_topics = len(vocab)
    model = DKTModel(num_topics=num_topics)

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    return model, vocab


def _get_interactions(student_id: str):
    """Return the student's interaction history in chronological order."""
    with get_session() as session:
        rows = (
            session.query(InteractionLog)
            .filter(InteractionLog.student_id == student_id)
            .order_by(InteractionLog.created_at.asc())
            .all()
        )

        return [
            {
                "subject": row.subject,
                "topic": row.topic,
                "correct": row.correct,
            }
            for row in rows
        ]


def _encode_interactions(interactions, vocab: TopicVocab):
    """Convert interactions into one-hot DKT input vectors."""
    num_topics = len(vocab)
    sequence = []

    for interaction in interactions:
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


def get_weak_topics_lstm(
    student_id: str,
    subject: str | None = None,
):
    """
    Predict weak topics using DKT.

    Falls back to the EMA tracker when DKT cannot be used.
    Optionally filters results by subject.
    """
    loaded = _load_model_and_vocab()

    if loaded is None:
        return get_weak_topics(student_id, subject=subject)

    model, vocab = loaded
    interactions = _get_interactions(student_id)

    if len(interactions) < _MIN_INTERACTIONS_FOR_LSTM:
        return get_weak_topics(student_id, subject=subject)

    x = _encode_interactions(interactions, vocab)

    if x is None:
        return get_weak_topics(student_id, subject=subject)

    with torch.no_grad():
        predictions = model(x)

    latest = predictions[0, -1]

    weak_topics = []

    for topic_subject, topic, idx in vocab.all_topics():

        if subject and topic_subject.lower() != subject.lower():
            continue

        mastery = float(latest[idx])

        if mastery < WEAK_TOPIC_THRESHOLD:
            weak_topics.append(
                {
                    "subject": topic_subject,
                    "topic": topic,
                    "mastery_score": round(mastery, 2),
                }
            )

    return sorted(
        weak_topics,
        key=lambda item: item["mastery_score"],
    )
