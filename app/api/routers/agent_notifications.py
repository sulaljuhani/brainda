"""Agent notifications API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import Optional

from api.dependencies import get_current_user_id
from api.services.agent_notification_service import AgentNotificationService

router = APIRouter(prefix="/api/v1/agent-notifications", tags=["agent-notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user_id: UUID = Depends(get_current_user_id),
):
    """
    List agent notifications for the current user.

    Query params:
    - unread_only: Only return unread notifications
    - limit: Maximum number of notifications to return (default: 50, max: 100)
    """
    if limit > 100:
        limit = 100

    service = AgentNotificationService()
    result = await service.list_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", {}).get("message", "Failed to list notifications"),
        )

    return {
        "notifications": result.get("data", []),
        "count": result.get("count", 0),
    }


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    """Mark a notification as read."""
    service = AgentNotificationService()
    result = await service.mark_as_read(notification_id, user_id)

    if not result.get("success"):
        error = result.get("error", {})
        if error.get("code") == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="Notification not found")
        raise HTTPException(status_code=500, detail=error.get("message", "Failed to mark as read"))

    return result.get("data")


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    """Mark a notification as dismissed."""
    service = AgentNotificationService()
    result = await service.mark_as_dismissed(notification_id, user_id)

    if not result.get("success"):
        error = result.get("error", {})
        if error.get("code") == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="Notification not found")
        raise HTTPException(status_code=500, detail=error.get("message", "Failed to dismiss"))

    return result.get("data")


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    """Delete a notification permanently."""
    service = AgentNotificationService()
    result = await service.delete_notification(notification_id, user_id)

    if not result.get("success"):
        error = result.get("error", {})
        if error.get("code") == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="Notification not found")
        raise HTTPException(status_code=500, detail=error.get("message", "Failed to delete"))

    return {"success": True, "id": notification_id}


@router.get("/unread/count")
async def get_unread_count(
    user_id: UUID = Depends(get_current_user_id),
):
    """Get count of unread notifications."""
    service = AgentNotificationService()
    result = await service.list_notifications(
        user_id=user_id,
        unread_only=True,
        limit=1000,  # High limit to count all
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail="Failed to get unread count")

    return {"count": result.get("count", 0)}
