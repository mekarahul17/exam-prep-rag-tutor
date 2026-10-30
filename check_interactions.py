from personalization_layer.database import get_session
from personalization_layer.models import Student, InteractionLog

with get_session() as session:
    print("Students:", session.query(Student).count())
    print("Total interactions:", session.query(InteractionLog).count())

    print("\nInteractions per student:")

    for student in session.query(Student).all():
        count = session.query(InteractionLog).filter_by(
            student_id=student.id
        ).count()

        print(student.id, count)