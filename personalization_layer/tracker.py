from __future__ import annotations

import logging
from datetime import datetime, timezone
from bson import ObjectId

from common.config import MASTERY_LEARNING_RATE, WEAK_TOPIC_THRESHOLD
from personalization_layer.mongodb import (
    students_collection,
    topic_mastery_collection,
    interaction_logs_collection,
)

logger = logging.getLogger(__name__)
_DEFAULT_STARTING_MASTERY = 0.5


def _is_valid_topic(subject: str, topic: str) -> bool:
    if not isinstance(topic, str) or not topic.strip():
        return False
    normalized_subject = subject.strip().lower()
    normalized_topic = topic.strip().lower()
    return normalized_topic not in {
        normalized_subject, "science", "math", "mathematics"
    }


def _get_or_create_student(student_id: str):
    students_collection.update_one(
        {"_id": student_id},
        {"$setOnInsert": {
            "grade": "",
            "preferred_language": "en",
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def log_result(student_id: str, subject: str, topic: str, correct: bool) -> float:
    if not _is_valid_topic(subject,topic):
        raise ValueError(f"Invalid topic:{topic}")
    _get_or_create_student(student_id)
    now = datetime.now(timezone.utc)
    interaction_logs_collection.insert_one({
        "_id": ObjectId(), "student_id": student_id,
        "subject": subject, "topic": topic,
        "correct": bool(correct), "created_at": now,
    })
    record = topic_mastery_collection.find_one({
        "student_id": student_id, "subject": subject, "topic": topic,
    })
    old_score = float(record.get("mastery_score", _DEFAULT_STARTING_MASTERY)) if record else _DEFAULT_STARTING_MASTERY
    target = 1.0 if correct else 0.0
    new_score = max(0.0, min(1.0, old_score + MASTERY_LEARNING_RATE * (target - old_score)))
    if record is None:
        topic_mastery_collection.insert_one({
            "_id": ObjectId(), "student_id": student_id,
            "subject": subject, "topic": topic,
            "mastery_score": new_score, "updated_at": now,
        })
    else:
        topic_mastery_collection.update_one(
            {"_id": record["_id"]},
            {"$set": {"mastery_score": new_score, "updated_at": now}},
        )
    logger.info(
        "Logged result: student=%s subject=%s topic=%s correct=%s mastery=%.2f",
        student_id, subject, topic, correct, new_score,
    )
    return new_score


def get_weak_topics(student_id: str, subject: str | None = None,
                    threshold: float = WEAK_TOPIC_THRESHOLD) -> list[dict]:
    query = {"student_id": student_id, "mastery_score": {"$lt": threshold}}
    if subject:
        query["subject"] = subject
    records = topic_mastery_collection.find(query).sort("mastery_score", 1)
    return [{"subject": r["subject"], "topic": r["topic"],
             "mastery_score": round(float(r["mastery_score"]), 2)}
            for r in records if _is_valid_topic(r["subject"], r["topic"])]


def get_all_topics_by_mastery(student_id: str, subject: str | None = None) -> list[dict]:
    query = {"student_id": student_id}
    if subject:
        query["subject"] = subject
    records = topic_mastery_collection.find(query).sort("mastery_score", 1)
    topics = []
    for record in records:
        if not _is_valid_topic(record.get("subject", ""), record.get("topic", "")):
            continue
        topic_filter = {
            "student_id": student_id,
            "subject": record["subject"],
            "topic": record["topic"],
        }
        attempts = interaction_logs_collection.count_documents(topic_filter)
        topics.append({
            "subject": record["subject"],
            "topic": record["topic"],
            "mastery_score": round(float(record.get("mastery_score", 0.0)), 2),
            "attempt_count": attempts,
        })
    return topics


def get_student_profile(student_id: str) -> dict:
    student = students_collection.find_one({"_id": student_id})
    topics = get_all_topics_by_mastery(student_id)
    total_attempts = interaction_logs_collection.count_documents({"student_id": student_id})
    strongest = max(topics, key=lambda item: item["mastery_score"], default=None)
    weakest = min(topics, key=lambda item: item["mastery_score"], default=None)
    return {
        "student_id": student_id,
        "grade": student.get("grade") if student else None,
        "total_attempts": total_attempts,
        "topics": topics,
        "strongest_topic": strongest,
        "weakest_topic": weakest,
        "recommended_topic": weakest,
    }
