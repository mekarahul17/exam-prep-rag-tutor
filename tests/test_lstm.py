"""
Tests for the DKT model architecture and topic vocabulary — lightweight
checks that don't require a trained model or real interaction data.
"""

import torch

from personalization_layer.lstm_model import DKTModel
from personalization_layer.topic_vocab import TopicVocab


def test_topic_vocab_assigns_stable_indices(tmp_path):
    vocab = TopicVocab(
        path=tmp_path / "vocab.json"
    )

    first = vocab.index_for(
        "Math",
        "fractions",
    )

    second = vocab.index_for(
        "Math",
        "fractions",
    )

    third = vocab.index_for(
        "Math",
        "algebra",
    )

    assert first == second
    assert third != first


def test_topic_vocab_is_case_and_whitespace_insensitive(tmp_path):
    vocab = TopicVocab(
        path=tmp_path / "vocab.json"
    )

    a = vocab.index_for(
        "Math",
        "Fractions",
    )

    b = vocab.index_for(
        "math",
        " fractions ",
    )

    assert a == b


def test_topic_vocab_persists_to_disk(tmp_path):
    vocab_path = tmp_path / "vocab.json"

    vocab = TopicVocab(
        path=vocab_path
    )

    vocab.index_for(
        "Science",
        "optics",
    )

    vocab.save()

    reloaded = TopicVocab(
        path=vocab_path
    )

    assert len(reloaded) == 1

    assert (
        reloaded.index_for(
            "Science",
            "optics",
            create_if_missing=False,
        )
        == 0
    )


def test_topic_vocab_missing_topic_returns_none_when_not_creating(tmp_path):
    vocab = TopicVocab(
        path=tmp_path / "vocab.json"
    )

    assert (
        vocab.index_for(
            "Math",
            "calculus",
            create_if_missing=False,
        )
        is None
    )


def test_dkt_model_output_shape():
    num_topics = 5

    model = DKTModel(
        num_topics=num_topics,
        hidden_size=8,
    )

    batch, seq_len = 1, 4

    dummy_input = torch.zeros(
        batch,
        seq_len,
        num_topics * 2,
    )

    output = model(dummy_input)

    assert output.shape == (
        batch,
        seq_len,
        num_topics,
    )


def test_dkt_model_outputs_are_probabilities():
    model = DKTModel(
        num_topics=3,
        hidden_size=4,
    )

    dummy_input = torch.rand(
        1,
        2,
        6,
    )

    output = model(dummy_input)

    assert torch.all(output >= 0)
    assert torch.all(output <= 1)