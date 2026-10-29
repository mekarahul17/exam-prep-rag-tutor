
"""
Trains the DKT (Deep Knowledge Tracing) LSTM using student
interaction history stored in MongoDB Atlas.

The LSTM remains experimental until sufficient real student
interaction data is collected.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from common.config import DATA_PROCESSED_DIR, configure_logging
from personalization_layer.mongodb import (
    students_collection,
    interaction_logs_collection,
)
from personalization_layer.lstm_model import DKTModel
from personalization_layer.topic_vocab import TopicVocab

configure_logging()
logger = logging.getLogger(__name__)

_MODEL_PATH = DATA_PROCESSED_DIR / "dkt_model.pt"
_EPOCHS = 20
_HIDDEN_SIZE = 64
_LEARNING_RATE = 1e-3


def _load_all_sequences() -> tuple[list[list[tuple[str, str, bool]]], TopicVocab]:
    vocab = TopicVocab()
    sequences = []

    student_ids = [
        student["_id"]
        for student in students_collection.find({}, {"_id": 1})
    ]

    logger.info("Found %d students in MongoDB.", len(student_ids))

    for student_id in student_ids:
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

        sequence = [
            (row["subject"], row["topic"], bool(row["correct"]))
            for row in rows
        ]

        for subject, topic, _ in sequence:
            vocab.index_for(
                subject,
                topic,
                create_if_missing=True,
            )

        if len(sequence) >= 2:
            sequences.append(sequence)

    vocab.save()

    return sequences, vocab


class InteractionSequenceDataset(Dataset):
    """Each item represents one student's interaction sequence."""

    def __init__(
        self,
        sequences: list[list[tuple[str, str, bool]]],
        vocab: TopicVocab,
    ):
        self.sequences = sequences
        self.vocab = vocab
        self.num_topics = len(vocab)

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int):
        sequence = self.sequences[idx]

        input_steps = []
        target_indices = []
        target_correct = []

        for subject, topic, correct in sequence[:-1]:
            index = self.vocab.index_for(
                subject,
                topic,
                create_if_missing=False,
            )

            vec = torch.zeros(self.num_topics * 2)
            vec[index if correct else self.num_topics + index] = 1.0
            input_steps.append(vec)

        for subject, topic, correct in sequence[1:]:
            index = self.vocab.index_for(
                subject,
                topic,
                create_if_missing=False,
            )

            target_indices.append(index)
            target_correct.append(1.0 if correct else 0.0)

        return (
            torch.stack(input_steps),
            torch.tensor(target_indices),
            torch.tensor(target_correct),
        )


def _collate(batch):
    return batch[0]


def main() -> None:
    sequences, vocab = _load_all_sequences()

    if not sequences:
        logger.warning(
            "No student sequences with at least two interactions "
            "were found in MongoDB. Nothing to train on."
        )
        return

    total_interactions = sum(len(sequence) for sequence in sequences)

    logger.info(
        "Training on %d student sequences, %d interactions, "
        "and %d topics.",
        len(sequences),
        total_interactions,
        len(vocab),
    )

    dataset = InteractionSequenceDataset(sequences, vocab)

    loader = DataLoader(
        dataset,
        batch_size=1,
        shuffle=True,
        collate_fn=_collate,
    )

    model = DKTModel(
        num_topics=len(vocab),
        hidden_size=_HIDDEN_SIZE,
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=_LEARNING_RATE,
    )

    loss_fn = nn.BCELoss()
    model.train()

    for epoch in range(1, _EPOCHS + 1):
        total_loss = 0.0

        for inputs, target_indices, target_correct in loader:
            if inputs.shape[0] == 0:
                continue

            optimizer.zero_grad()

            predictions = model(inputs.unsqueeze(0))[0]

            predicted_for_target = predictions[
                torch.arange(len(target_indices)),
                target_indices,
            ]

            loss = loss_fn(
                predicted_for_target,
                target_correct,
            )

            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        logger.info(
            "Epoch %d/%d - loss: %.4f",
            epoch,
            _EPOCHS,
            total_loss / max(len(loader), 1),
        )

    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        model.state_dict(),
        _MODEL_PATH,
    )

    logger.info("Model saved to %s", _MODEL_PATH)


if __name__ == "__main__":
    main()
