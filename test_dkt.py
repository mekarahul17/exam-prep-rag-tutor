from personalization_layer.sequence_tracker import get_weak_topics_lstm

students = ["test_student", "dkt_demo_student"]

for student_id in students:
    print("\nStudent:", student_id)

    try:
        result = get_weak_topics_lstm(student_id)
        print("Predicted weak topics:", result)
    except Exception as e:
        print("ERROR:", repr(e))