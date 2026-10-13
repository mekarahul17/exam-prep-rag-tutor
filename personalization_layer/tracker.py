"""
Reads and updates a student's per-topic mastery based on quiz/interaction
results. This is the core of the personalization layer.

Update rule: an exponential moving average nudges a topic's mastery score
towards 1.0 on a correct answer and towards 0.0 on an incorrect one, with
MASTERY_LEARNING_RATE controlling how much weight a single new result
carries against the existing score.
"""

from __future__ import annotations

import logging

from common.config import MASTERY_LEARNING_RATE, WEAK_TOPIC_THRESHOLD
from personalization_layer.database import get_session
from personalization_layer.models import (
    InteractionLog,
    Student,
    TopicMastery,
)

logger = logging.getLogger(__name__)

_DEFAULT_STARTING_MASTERY = 0.5


def _get_or_create_student(session, student_id: str) -> Student:
    student = session.get(Student, student_id)

    if student is None:
        student = Student(id=student_id)
        session.add(student)
        session.flush()

    return student


def log_result(
    student_id: str,
    subject: str,
    topic: str,
    correct: bool,
) -> float:
    """Record one interaction and return the topic's updated mastery score."""

    with get_session() as session:
        _get_or_create_student(session, student_id)

        session.add(
            InteractionLog(
                student_id=student_id,
                subject=subject,
                topic=topic,
                correct=correct,
            )
        )

        record = (
            session.query(TopicMastery)
            .filter_by(
                student_id=student_id,
                subject=subject,
                topic=topic,
            )
            .one_or_none()
        )

        if record is None:
            record = TopicMastery(
                student_id=student_id,
                subject=subject,
                topic=topic,
                mastery_score=_DEFAULT_STARTING_MASTERY,
            )
            session.add(record)

        target = 1.0 if correct else 0.0

        record.mastery_score = (
            record.mastery_score
            + MASTERY_LEARNING_RATE
            * (target - record.mastery_score)
        )

        record.mastery_score = max(
            0.0,
            min(1.0, record.mastery_score),
        )

        session.flush()

        new_score = record.mastery_score

        logger.info(
            "Updated mastery: student=%s subject=%s topic=%s -> %.2f",
            student_id,
            subject,
            topic,
            new_score,
        )

        return new_score


def get_weak_topics(
    student_id: str,
    subject: str | None = None,
    threshold: float = WEAK_TOPIC_THRESHOLD,
) -> list[dict]:
    """Return topics where mastery is below threshold, weakest first."""

    with get_session() as session:
        query = (
            session.query(TopicMastery)
            .filter(
                TopicMastery.student_id == student_id,
                TopicMastery.mastery_score < threshold,
            )
        )

        if subject:
            query = query.filter(
                TopicMastery.subject == subject
            )

        records = query.order_by(
            TopicMastery.mastery_score.asc()
        ).all()

        return [
            {
                "subject": record.subject,
                "topic": record.topic,
                "mastery_score": round(
                    record.mastery_score,
                    2,
                ),
            }
            for record in records
        ]


def get_student_profile(student_id: str) -> dict:
    """Return every tracked topic and mastery score for a student."""

    with get_session() as session:
        student = session.get(Student, student_id)

        if student is None:
            return {
                "student_id": student_id,
                "grade": None,
                "topics": [],
            }

        topics = [
            {
                "subject": record.subject,
                "topic": record.topic,
                "mastery_score": round(
                    record.mastery_score,
                    2,
                ),
            }
            for record in session.query(TopicMastery)
            .filter_by(student_id=student_id)
            .all()
        ]

        return {
            "student_id": student_id,
            "grade": student.grade,
            "topics": topics,
        }