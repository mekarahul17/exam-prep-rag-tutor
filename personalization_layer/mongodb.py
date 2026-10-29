import os
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "exam_prep_tutor"

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is missing from .env file")

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000
)

db = client[DATABASE_NAME]

students_collection = db["students"]
topic_mastery_collection = db["topic_mastery"]
interaction_logs_collection = db["interaction_logs"]
quiz_history_collection = db["quiz_history"]


def test_connection():
    try:
        client.admin.command("ping")
        logger.info("MongoDB Atlas connected successfully.")
        return True
    except PyMongoError as error:
        logger.error("MongoDB connection failed: %s", error)
        return False