"""
Deep Knowledge Tracing (DKT) model: an LSTM that reads a student's
sequence of (topic, correct/incorrect) interactions and predicts their
mastery probability for every tracked topic — capturing patterns across
repeated questions that a single per-topic average can't. Two students
who are both "60% on fractions" can be on very different trajectories
(improving vs. stuck), and a sequence model can tell them apart where an
average can't.
Reference: Piech et al., "Deep Knowledge Tracing" (NeurIPS 2015).
"""

from __future__ import annotations

import torch
import torch.nn as nn


class DKTModel(nn.Module):
    """One-hot (topic, correctness) sequence -> LSTM -> per-topic mastery probabilities."""

    def __init__(
        self,
        num_topics: int,
        hidden_size: int = 64,
        num_layers: int = 1,
    ):
        super().__init__()
        self.num_topics = num_topics

        self.input_size = num_topics * 2

        self.lstm = nn.LSTM(
            self.input_size,
            hidden_size,
            num_layers,
            batch_first=True,
        )
        self.output_layer = nn.Linear(hidden_size, num_topics)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, input_size) -> (batch, seq_len, num_topics)
        predicted mastery probability for every topic, at every point in
        the sequence."""
        lstm_out, _ = self.lstm(x)
        logits = self.output_layer(lstm_out)
        return torch.sigmoid(logits)