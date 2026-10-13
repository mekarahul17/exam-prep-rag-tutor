"""
MCP tools: get_student_profile, log_interaction — wrap the personalization
tracker.
"""

from __future__ import annotations

import json

from personalization_layer.tracker import get_student_profile as _get_profile
from personalization_layer.tracker import log_result


def get_student_profile(student_id: str) -> str:
    """Return a student's tracked topics and mastery scores as JSON.

    Args:
        student_id: Unique identifier for the student.
    """

    return json.dumps(_get_profile(student_id))


def log_interaction(
    student_id: str,
    subject: str,
    topic: str,
    correct: bool,
) -> str:
    """Record a quiz/question outcome and update the topic's mastery score.

    Args:
        student_id: Unique identifier for the student.
        subject: Subject the interaction belongs to, e.g. "Math".
        topic: Specific topic, e.g. "quadratic equations".
        correct: Whether the student answered correctly.
    """

    new_score = log_result(student_id, subject, topic, correct)

    return json.dumps(
        {
            "subject": subject,
            "topic": topic,
            "mastery_score": round(new_score, 2),
        }
    )