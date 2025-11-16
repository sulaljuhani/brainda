"""Chat Conversations API Router

Provides endpoints for managing chat conversations and message history.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg
from api.dependencies import get_db, get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessageModel(BaseModel):
    """Chat message model"""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


class ConversationModel(BaseModel):
    """Conversation model"""
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0


class CreateMessageRequest(BaseModel):
    """Create message request"""
    conversation_id: Optional[UUID] = None
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None


class UpdateTitleRequest(BaseModel):
    """Update conversation title request"""
    title: str = Field(..., min_length=1, max_length=500)


class ConversationWithMessages(BaseModel):
    """Conversation with messages"""
    conversation: ConversationModel
    messages: List[ChatMessageModel]


@router.get("/conversations", response_model=List[ConversationModel])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """List all conversations for the current user

    Returns conversations ordered by most recently updated first.
    """
    try:
        rows = await db.fetch(
            """
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                COUNT(m.id) as message_count
            FROM chat_conversations c
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            WHERE c.user_id = $1
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

        return [ConversationModel(**dict(row)) for row in rows]

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get a conversation with all its messages"""
    try:
        # Get conversation
        conv_row = await db.fetchrow(
            """
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                COUNT(m.id) as message_count
            FROM chat_conversations c
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            WHERE c.id = $1 AND c.user_id = $2
            GROUP BY c.id
            """,
            conversation_id,
            user_id,
        )

        if not conv_row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get messages
        msg_rows = await db.fetch(
            """
            SELECT
                id,
                conversation_id,
                role,
                content,
                tool_calls,
                citations,
                created_at
            FROM chat_messages
            WHERE conversation_id = $1 AND user_id = $2
            ORDER BY created_at ASC
            """,
            conversation_id,
            user_id,
        )

        return ConversationWithMessages(
            conversation=ConversationModel(**dict(conv_row)),
            messages=[ChatMessageModel(**dict(row)) for row in msg_rows],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@router.post("/messages", response_model=ChatMessageModel)
async def create_message(
    message: CreateMessageRequest,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Create a new chat message

    If conversation_id is not provided, a new conversation will be created.
    """
    try:
        async with db.transaction():
            conversation_id = message.conversation_id

            # Create new conversation if needed
            if not conversation_id:
                conv_row = await db.fetchrow(
                    """
                    INSERT INTO chat_conversations (user_id)
                    VALUES ($1)
                    RETURNING id
                    """,
                    user_id,
                )
                conversation_id = conv_row['id']

            # Verify conversation belongs to user
            exists = await db.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM chat_conversations
                    WHERE id = $1 AND user_id = $2
                )
                """,
                conversation_id,
                user_id,
            )

            if not exists:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Insert message
            row = await db.fetchrow(
                """
                INSERT INTO chat_messages (
                    conversation_id,
                    user_id,
                    role,
                    content,
                    tool_calls,
                    citations
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, conversation_id, role, content, tool_calls, citations, created_at
                """,
                conversation_id,
                user_id,
                message.role,
                message.content,
                message.tool_calls,
                message.citations,
            )

            return ChatMessageModel(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating message: {e}")
        raise HTTPException(status_code=500, detail="Failed to create message")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Delete a conversation and all its messages"""
    try:
        result = await db.execute(
            """
            DELETE FROM chat_conversations
            WHERE id = $1 AND user_id = $2
            """,
            conversation_id,
            user_id,
        )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"success": True, "message": "Conversation deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.patch("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: UUID,
    payload: UpdateTitleRequest,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Update conversation title"""
    try:
        result = await db.execute(
            """
            UPDATE chat_conversations
            SET title = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3
            """,
            payload.title,
            conversation_id,
            user_id,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"success": True, "title": payload.title}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation title: {e}")
        raise HTTPException(status_code=500, detail="Failed to update title")
