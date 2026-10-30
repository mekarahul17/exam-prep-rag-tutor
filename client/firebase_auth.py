
import logging

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException

PROJECT_ID = "taskflow-app-e6571"

logger = logging.getLogger(__name__)


def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        credential = credentials.ApplicationDefault()
        return firebase_admin.initialize_app(
            credential,
            {"projectId": PROJECT_ID}
        )


def verify_firebase_token(
    authorization: str | None = Header(default=None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication token"
        )

    token = authorization.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token is empty"
        )

    try:
        app = get_firebase_app()

        decoded_token = auth.verify_id_token(
            token,
            app=app,
            check_revoked=True,
            clock_skew_seconds=5
        )

        return decoded_token

    except Exception:
        logger.exception("Firebase ID token verification failed")

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )
