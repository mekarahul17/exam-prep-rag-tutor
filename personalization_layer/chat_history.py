
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from client.firebase_auth import verify_firebase_token
from personalization_layer.mongodb import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat History"])

conversations_collection = db["conversations"]
chat_messages_collection = db["chat_messages"]

_indexes_ready = False


def ensure_indexes() -> None:
    """Create indexes once, on the first history request."""
    global _indexes_ready

    if _indexes_ready:
        return

    conversations_collection.create_index(
        [("student_id", 1), ("updated_at", DESCENDING)],
        name="student_conversations_updated",
    )

    chat_messages_collection.create_index(
        [("conversation_id", 1), ("created_at", 1)],
        name="conversation_messages_order",
    )

    chat_messages_collection.create_index(
        [("student_id", 1), ("conversation_id", 1)],
        name="student_conversation_messages",
    )

    _indexes_ready = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_conversation(document: dict) -> dict:
    return {
        "conversation_id": str(document["_id"]),
        "title": document.get("title", "New chat"),
        "created_at": document["created_at"].isoformat(),
        "updated_at": document["updated_at"].isoformat(),
        "message_count": document.get("message_count", 0),
    }


def serialize_message(document: dict) -> list[dict]:
    created_at = document["created_at"].isoformat()
    metadata = document.get("metadata", {})
    turn_id = str(document["_id"])

    return [
        {
            "message_id": f"{turn_id}:user",
            "role": "user",
            "content": document["user_message"],
            "created_at": created_at,
            "metadata": metadata,
        },
        {
            "message_id": f"{turn_id}:assistant",
            "role": "assistant",
            "content": document["assistant_message"],
            "created_at": created_at,
            "metadata": metadata,
        },
    ]


def get_owned_conversation(conversation_id: str, student_id: str) -> dict:
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID.",
        )

    conversation = conversations_collection.find_one({
        "_id": ObjectId(conversation_id),
        "student_id": student_id,
    })

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return conversation


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=120)


class SaveTurnRequest(BaseModel):
    user_message: str = Field(min_length=1, max_length=15000)
    assistant_message: str = Field(min_length=1, max_length=30000)
    metadata: dict = Field(default_factory=dict)


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]
    now = utc_now()
    title = request.title.strip() or "New chat"

    result = conversations_collection.insert_one({
        "student_id": student_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    })

    conversation = conversations_collection.find_one({
        "_id": result.inserted_id,
        "student_id": student_id,
    })

    return serialize_conversation(conversation)


@router.get("/conversations")
async def list_conversations(
    search: Optional[str] = Query(default=None, max_length=100),
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]
    query = {"student_id": student_id}

    if search and search.strip():
        query["title"] = {
            "$regex": re.escape(search.strip()),
            "$options": "i",
        }

    cursor = conversations_collection.find(query).sort(
        "updated_at", DESCENDING
    ).limit(100)

    return {
        "conversations": [
            serialize_conversation(item) for item in cursor
        ]
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]

    conversation = get_owned_conversation(
        conversation_id,
        student_id,
    )

    cursor = chat_messages_collection.find({
        "conversation_id": conversation_id,
        "student_id": student_id,
    }).sort([
        ("created_at", 1),
        ("_id", 1),
    ])

    return {
        "conversation": serialize_conversation(conversation),
        "messages": [
            message
            for item in cursor
            for message in serialize_message(item)
        ],
    }


@router.post("/conversations/{conversation_id}/turn")
async def save_conversation_turn(
    conversation_id: str,
    request: SaveTurnRequest,
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]

    conversation = get_owned_conversation(
        conversation_id,
        student_id,
    )

    user_text = request.user_message.strip()
    assistant_text = request.assistant_message.strip()

    if not user_text or not assistant_text:
        raise HTTPException(
            status_code=422,
            detail="Both user and assistant messages are required.",
        )

    now = utc_now()

    chat_messages_collection.insert_one({
        "student_id": student_id,
        "conversation_id": conversation_id,
        "role": "turn",
        "user_message": user_text,
        "assistant_message": assistant_text,
        "created_at": now,
        "metadata": request.metadata,
    })

    update_fields = {
        "updated_at": now,
        "message_count": int(
            conversation.get("message_count", 0)
        ) + 2,
    }

    if int(conversation.get("message_count", 0)) == 0:
        update_fields["title"] = user_text[:60]

    conversations_collection.update_one(
        {
            "_id": ObjectId(conversation_id),
            "student_id": student_id,
        },
        {"$set": update_fields},
    )

    return {
        "success": True,
        "saved": True,
    }


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]

    get_owned_conversation(
        conversation_id,
        student_id,
    )

    title = request.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Title cannot be empty.",
        )

    conversations_collection.update_one(
        {
            "_id": ObjectId(conversation_id),
            "student_id": student_id,
        },
        {
            "$set": {
                "title": title,
                "updated_at": utc_now(),
            }
        },
    )

    return {
        "success": True,
        "title": title,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(verify_firebase_token),
):
    ensure_indexes()

    student_id = current_user["uid"]

    get_owned_conversation(
        conversation_id,
        student_id,
    )

    chat_messages_collection.delete_many({
        "conversation_id": conversation_id,
        "student_id": student_id,
    })

    conversations_collection.delete_one({
        "_id": ObjectId(conversation_id),
        "student_id": student_id,
    })

    return {
        "success": True,
        "deleted": True,
    }
