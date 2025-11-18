"""What's Next API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
import asyncpg

from api.dependencies import get_current_user_id, get_db
from api.services.whats_next_service import WhatsNextService

router = APIRouter(prefix="/api/v1/whats-next", tags=["whats-next"])


@router.get("")
async def get_whats_next(
    user_id: UUID = Depends(get_current_user_id),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get intelligent suggestions for what to do next.

    Analyzes your current situation and provides prioritized suggestions:
    - Overdue tasks (highest priority)
    - Upcoming events (next 2 hours)
    - Pending reminders
    - Tasks due today
    - High-priority tasks
    - AI-generated personalized recommendation

    Returns a prioritized list of suggestions with actionable items.

    Example response:
    ```json
    {
        "timestamp": "2025-01-15T10:30:00Z",
        "priority_score": 18,
        "suggestions": [
            {
                "type": "overdue_task",
                "priority": "urgent",
                "title": "You have 2 overdue task(s)",
                "description": "Focus on: Finish project proposal",
                "action": {
                    "type": "view_task",
                    "task_id": "..."
                },
                "tasks": [...]
            }
        ],
        "ai_suggestion": "Start with your overdue project proposal to clear urgent items...",
        "summary": "⚠️ You have 1 urgent item(s) that need attention"
    }
    ```
    """
    service = WhatsNextService()
    result = await service.get_whats_next(user_id, db)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", {}).get("message", "Failed to get what's next"),
        )

    return result.get("data")


@router.get("/summary")
async def get_whats_next_summary(
    user_id: UUID = Depends(get_current_user_id),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get a quick summary of what's next (lightweight version).

    Returns just the summary text and priority score without detailed suggestions.
    Useful for dashboard widgets or quick checks.
    """
    service = WhatsNextService()
    result = await service.get_whats_next(user_id, db)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", {}).get("message", "Failed to get summary"),
        )

    data = result.get("data", {})
    return {
        "summary": data.get("summary", ""),
        "priority_score": data.get("priority_score", 0),
        "suggestion_count": len(data.get("suggestions", [])),
    }
