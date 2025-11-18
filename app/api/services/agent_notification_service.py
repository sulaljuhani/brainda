"""Agent notification service - Manage notifications from autonomous agents."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog

from api.tools.db_helper import get_db_connection

logger = structlog.get_logger()


class AgentNotificationService:
    """Service for managing agent-generated notifications."""

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: str,
        priority: str = "normal",
        action_url: Optional[str] = None,
    ) -> dict:
        """
        Create an agent notification.

        Args:
            user_id: User UUID
            title: Notification title
            body: Notification body/content
            notification_type: Type of notification (morning_briefing, evening_review, etc.)
            priority: Priority level (low, normal, high, urgent)
            action_url: Optional URL for notification action

        Returns:
            dict with success status and notification data
        """
        try:
            async with get_db_connection() as db:
                notification = await db.fetchrow(
                    """
                    INSERT INTO agent_notifications (
                        user_id, title, body, type, priority, action_url, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, user_id, title, body, type, priority, action_url, created_at, read_at
                    """,
                    user_id,
                    title,
                    body,
                    notification_type,
                    priority,
                    action_url,
                    datetime.now(timezone.utc),
                )

                logger.info(
                    "agent_notification_created",
                    user_id=str(user_id),
                    notification_id=str(notification["id"]),
                    type=notification_type,
                    priority=priority,
                )

                return {
                    "success": True,
                    "data": {
                        "id": str(notification["id"]),
                        "user_id": str(notification["user_id"]),
                        "title": notification["title"],
                        "body": notification["body"],
                        "type": notification["type"],
                        "priority": notification["priority"],
                        "action_url": notification["action_url"],
                        "created_at": notification["created_at"].isoformat(),
                        "read_at": notification["read_at"].isoformat() if notification["read_at"] else None,
                    },
                }

        except Exception as exc:
            logger.error("agent_notification_creation_failed", error=str(exc))
            return {
                "success": False,
                "error": {"code": "CREATION_FAILED", "message": str(exc)},
            }

    async def list_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> dict:
        """
        List notifications for a user.

        Args:
            user_id: User UUID
            unread_only: Only return unread notifications
            limit: Maximum number of notifications to return

        Returns:
            dict with success status and list of notifications
        """
        try:
            async with get_db_connection() as db:
                query = """
                    SELECT id, user_id, title, body, type, priority, action_url, created_at, read_at, dismissed_at
                    FROM agent_notifications
                    WHERE user_id = $1
                """
                params = [user_id]

                if unread_only:
                    query += " AND read_at IS NULL"

                query += " ORDER BY created_at DESC LIMIT $2"
                params.append(limit)

                rows = await db.fetch(query, *params)

                notifications = [
                    {
                        "id": str(row["id"]),
                        "user_id": str(row["user_id"]),
                        "title": row["title"],
                        "body": row["body"],
                        "type": row["type"],
                        "priority": row["priority"],
                        "action_url": row["action_url"],
                        "created_at": row["created_at"].isoformat(),
                        "read_at": row["read_at"].isoformat() if row["read_at"] else None,
                        "dismissed_at": row["dismissed_at"].isoformat() if row["dismissed_at"] else None,
                    }
                    for row in rows
                ]

                return {
                    "success": True,
                    "data": notifications,
                    "count": len(notifications),
                }

        except Exception as exc:
            logger.error("list_notifications_failed", error=str(exc))
            return {
                "success": False,
                "error": {"code": "LIST_FAILED", "message": str(exc)},
            }

    async def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Mark a notification as read."""
        try:
            async with get_db_connection() as db:
                updated = await db.fetchrow(
                    """
                    UPDATE agent_notifications
                    SET read_at = $1
                    WHERE id = $2 AND user_id = $3
                    RETURNING id, read_at
                    """,
                    datetime.now(timezone.utc),
                    notification_id,
                    user_id,
                )

                if not updated:
                    return {
                        "success": False,
                        "error": {"code": "NOT_FOUND", "message": "Notification not found"},
                    }

                return {
                    "success": True,
                    "data": {
                        "id": str(updated["id"]),
                        "read_at": updated["read_at"].isoformat(),
                    },
                }

        except Exception as exc:
            logger.error("mark_notification_read_failed", error=str(exc))
            return {
                "success": False,
                "error": {"code": "UPDATE_FAILED", "message": str(exc)},
            }

    async def mark_as_dismissed(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Mark a notification as dismissed."""
        try:
            async with get_db_connection() as db:
                updated = await db.fetchrow(
                    """
                    UPDATE agent_notifications
                    SET dismissed_at = $1
                    WHERE id = $2 AND user_id = $3
                    RETURNING id, dismissed_at
                    """,
                    datetime.now(timezone.utc),
                    notification_id,
                    user_id,
                )

                if not updated:
                    return {
                        "success": False,
                        "error": {"code": "NOT_FOUND", "message": "Notification not found"},
                    }

                return {
                    "success": True,
                    "data": {
                        "id": str(updated["id"]),
                        "dismissed_at": updated["dismissed_at"].isoformat(),
                    },
                }

        except Exception as exc:
            logger.error("mark_notification_dismissed_failed", error=str(exc))
            return {
                "success": False,
                "error": {"code": "UPDATE_FAILED", "message": str(exc)},
            }

    async def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Delete a notification permanently."""
        try:
            async with get_db_connection() as db:
                deleted = await db.fetchval(
                    """
                    DELETE FROM agent_notifications
                    WHERE id = $1 AND user_id = $2
                    RETURNING id
                    """,
                    notification_id,
                    user_id,
                )

                if not deleted:
                    return {
                        "success": False,
                        "error": {"code": "NOT_FOUND", "message": "Notification not found"},
                    }

                return {
                    "success": True,
                    "data": {"id": str(deleted)},
                }

        except Exception as exc:
            logger.error("delete_notification_failed", error=str(exc))
            return {
                "success": False,
                "error": {"code": "DELETE_FAILED", "message": str(exc)},
            }
