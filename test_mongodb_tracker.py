
from personalization_layer.tracker import (
    log_result,
    get_student_profile,
    get_all_topics_by_mastery,
)
from personalization_layer.sequence_tracker import (
    _get_interactions,
    get_weak_topics_lstm,
)
from personalization_layer.mongodb import (
    students_collection,
    topic_mastery_collection,
    interaction_logs_collection,
)

TEST_ID = "mongodb_tracker_test"

try:
    print("1. Testing interaction logging...")

    score = log_result(
        student_id=TEST_ID,
        subject="Science",
        topic="Photosynthesis",
        correct=True,
    )
    print("Mastery score:", score)

    print("\n2. Testing student profile...")
    profile = get_student_profile(TEST_ID)
    print(profile)

    print("\n3. Testing mastery records...")
    topics = get_all_topics_by_mastery(TEST_ID)
    print(topics)

    print("\n4. Testing interaction history...")
    interactions = _get_interactions(TEST_ID)
    print("Interactions found:", len(interactions))
    print(interactions)

    print("\n5. Testing DKT prediction...")
    predictions = get_weak_topics_lstm(TEST_ID, subject="Science")
    print("Weak topics:", predictions)

    print("\nAll tracker tests completed.")

finally:
    print("\nCleaning up test data...")
    students_collection.delete_one({"_id": TEST_ID})
    topic_mastery_collection.delete_many({"student_id": TEST_ID})
    interaction_logs_collection.delete_many({"student_id": TEST_ID})
    print("Test data cleaned up.")

