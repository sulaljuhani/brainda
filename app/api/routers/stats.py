"""Statistics API Router

Provides analytics and statistics endpoints for the dashboard.
"""

from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import asyncpg
from api.dependencies import get_db, get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stats", tags=["statistics"])


class TaskStats(BaseModel):
    """Task statistics"""
    total: int
    active: int
    completed: int
    with_subtasks: int


class EventStats(BaseModel):
    """Event statistics"""
    total: int
    upcoming: int
    past: int
    recurring: int


class ReminderStats(BaseModel):
    """Reminder statistics"""
    total: int
    active: int
    completed: int
    recurring: int


class ChatStats(BaseModel):
    """Chat statistics"""
    total_conversations: int
    total_messages: int
    avg_messages_per_conversation: float


class OverviewStats(BaseModel):
    """Overview statistics"""
    tasks: TaskStats
    events: EventStats
    reminders: ReminderStats
    chat: ChatStats
    notes_count: int
    documents_count: int


@router.get("/overview", response_model=OverviewStats)
async def get_overview_stats(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get overview statistics for the current user"""

    # Get task stats
    task_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status IN ('active', 'completed', 'cancelled')) as total,
            COUNT(*) FILTER (WHERE status = 'active') as active,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(DISTINCT id) FILTER (WHERE parent_task_id IS NULL AND EXISTS(
                SELECT 1 FROM tasks sub WHERE sub.parent_task_id = tasks.id
            )) as with_subtasks
        FROM tasks
        WHERE user_id = $1
        """,
        user_id,
    )

    # Get event stats
    event_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE starts_at >= NOW()) as upcoming,
            COUNT(*) FILTER (WHERE starts_at < NOW()) as past,
            COUNT(*) FILTER (WHERE rrule IS NOT NULL) as recurring
        FROM calendar_events
        WHERE user_id = $1
        """,
        user_id,
    )

    # Get reminder stats
    reminder_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'active') as active,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE repeat_rrule IS NOT NULL) as recurring
        FROM reminders
        WHERE user_id = $1
        """,
        user_id,
    )

    # Get chat stats
    chat_row = await db.fetchrow(
        """
        SELECT
            COUNT(DISTINCT c.id) as total_conversations,
            COUNT(m.id) as total_messages,
            COALESCE(AVG(msg_counts.cnt), 0) as avg_messages_per_conversation
        FROM chat_conversations c
        LEFT JOIN chat_messages m ON m.conversation_id = c.id
        LEFT JOIN (
            SELECT conversation_id, COUNT(*) as cnt
            FROM chat_messages
            WHERE user_id = $1
            GROUP BY conversation_id
        ) msg_counts ON msg_counts.conversation_id = c.id
        WHERE c.user_id = $1
        """,
        user_id,
    )

    # Get notes count
    notes_count = await db.fetchval(
        "SELECT COUNT(*) FROM notes WHERE user_id = $1",
        user_id,
    )

    # Get documents count
    documents_count = await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE user_id = $1",
        user_id,
    )

    return OverviewStats(
        tasks=TaskStats(
            total=task_row['total'] or 0,
            active=task_row['active'] or 0,
            completed=task_row['completed'] or 0,
            with_subtasks=task_row['with_subtasks'] or 0,
        ),
        events=EventStats(
            total=event_row['total'] or 0,
            upcoming=event_row['upcoming'] or 0,
            past=event_row['past'] or 0,
            recurring=event_row['recurring'] or 0,
        ),
        reminders=ReminderStats(
            total=reminder_row['total'] or 0,
            active=reminder_row['active'] or 0,
            completed=reminder_row['completed'] or 0,
            recurring=reminder_row['recurring'] or 0,
        ),
        chat=ChatStats(
            total_conversations=chat_row['total_conversations'] or 0,
            total_messages=chat_row['total_messages'] or 0,
            avg_messages_per_conversation=float(chat_row['avg_messages_per_conversation'] or 0),
        ),
        notes_count=notes_count or 0,
        documents_count=documents_count or 0,
    )
