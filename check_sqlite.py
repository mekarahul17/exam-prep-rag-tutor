from sqlalchemy import func
from personalization_layer.database import get_session
from personalization_layer.models import (
    Student,
    TopicMastery,
    InteractionLog
)

with get_session() as session:
    print("SQLite Database Statistics")
    print("--------------------------")

    print("Students:", session.query(func.count(Student.id)).scalar())

    print(
        "Topic Mastery Records:",
        session.query(func.count(TopicMastery.id)).scalar()
    )

    print(
        "Interaction Logs:",
        session.query(func.count(InteractionLog.id)).scalar()
    )

    print("\nStudent IDs:")

    students = session.query(Student).all()

    for student in students:
        print(student.id)