"""
Tests for the personalization layer's mastery-tracking logic.

Uses a throw-away file-based SQLite database, reassigned directly onto the
database module so these tests need no external setup and don't depend on
import order.
"""

import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import personalization_layer.database as db_module
from personalization_layer.tracker import (
    get_student_profile,
    get_weak_topics,
    log_result,
)


@pytest.fixture(autouse=True)
def _isolated_test_database():
    """Point the personalization layer at a fresh SQLite file for each test."""

    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".db",
        delete=False,
    )

    db_module._engine = create_engine(
        f"sqlite:///{tmp_file.name}",
        future=True,
    )

    db_module._SessionLocal = sessionmaker(
        bind=db_module._engine,
        expire_on_commit=False,
    )

    db_module.init_db()

    yield


def test_correct_answer_raises_mastery():
    first = log_result(
        "student_1",
        "Math",
        "fractions",
        correct=True,
    )

    second = log_result(
        "student_1",
        "Math",
        "fractions",
        correct=True,
    )

    assert second > first


def test_incorrect_answer_lowers_mastery():
    log_result(
        "student_2",
        "Math",
        "algebra",
        correct=True,
    )

    score_before = log_result(
        "student_2",
        "Math",
        "algebra",
        correct=True,
    )

    score_after = log_result(
        "student_2",
        "Math",
        "algebra",
        correct=False,
    )

    assert score_after < score_before


def test_weak_topics_surfaces_low_scores():
    for _ in range(4):
        log_result(
            "student_3",
            "Science",
            "optics",
            correct=False,
        )

    log_result(
        "student_3",
        "Science",
        "genetics",
        correct=True,
    )

    weak_topics = [
        w["topic"]
        for w in get_weak_topics(
            "student_3",
            subject="Science",
        )
    ]

    assert "optics" in weak_topics
    assert "genetics" not in weak_topics


def test_get_student_profile_returns_all_tracked_topics():
    log_result(
        "student_4",
        "Math",
        "geometry",
        correct=True,
    )

    profile = get_student_profile("student_4")

    assert profile["student_id"] == "student_4"

    assert any(
        t["topic"] == "geometry"
        for t in profile["topics"]
    )