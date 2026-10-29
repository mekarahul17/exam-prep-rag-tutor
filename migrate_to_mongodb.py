
from datetime import datetime, timezone
from sqlalchemy import func

from personalization_layer.database import get_session
from personalization_layer.models import (
    Student,
    TopicMastery,
    InteractionLog,
)
from personalization_layer.mongodb import (
    test_connection,
    students_collection,
    topic_mastery_collection,
    interaction_logs_collection,
)

def migrate():
    print("Starting SQLite to MongoDB migration...")

    if not test_connection():
        raise RuntimeError("MongoDB Atlas connection failed.")

    with get_session() as session:
        students = session.query(Student).all()
        mastery_records = session.query(TopicMastery).all()
        interactions = session.query(InteractionLog).all()

        student_docs = [
            {
                "_id": student.id,
                "grade": student.grade,
                "preferred_language": student.preferred_language,
            }
            for student in students
        ]

        mastery_docs = [
            {
                "_id": record.id,
                "student_id": record.student_id,
                "subject": record.subject,
                "topic": record.topic,
                "mastery_score": record.mastery_score,
                "updated_at": record.updated_at,
            }
            for record in mastery_records
        ]

        interaction_docs = [
            {
                "_id": record.id,
                "student_id": record.student_id,
                "subject": record.subject,
                "topic": record.topic,
                "correct": record.correct,
                "created_at": record.created_at,
            }
            for record in interactions
        ]

    collections = [
        (students_collection, student_docs, "students"),
        (topic_mastery_collection, mastery_docs, "topic_mastery"),
        (interaction_logs_collection, interaction_docs, "interaction_logs"),
    ]

    for collection, documents, name in collections:
        for document in documents:
            collection.replace_one(
                {"_id": document["_id"]},
                document,
                upsert=True,
            )
        print(f"{name}: migrated {len(documents)} records")

    print("\nVerifying MongoDB records...")

    expected = [
        (students_collection, len(student_docs), "Students"),
        (topic_mastery_collection, len(mastery_docs), "Topic mastery"),
        (interaction_logs_collection, len(interaction_docs), "Interactions"),
    ]

    for collection, expected_count, name in expected:
        actual_count = collection.count_documents({})
        print(f"{name}: {actual_count}/{expected_count}")

        if actual_count != expected_count:
            raise RuntimeError(f"{name} migration verification failed.")

    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
