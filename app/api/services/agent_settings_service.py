"""Agent settings service - Manage per-user agent configurations."""
from __future__ import annotations

from datetime import time, datetime, timezone
from typing import Optional
from uuid import UUID

import structlog

from api.tools.db_helper import get_db_connection

logger = structlog.get_logger()


class AgentSettingsService:
    """Service for managing user agent settings."""

    async def get_settings(self, user_id: UUID) -> dict:
        """
        Get agent settings for a user.
        Creates default settings if they don't exist.

        Returns:
            dict with agent settings
        """
        try:
            async with get_db_connection() as db:
                settings = await db.fetchrow(
                    """
                    SELECT
                        id, user_id,
                        morning_briefing_enabled, evening_review_enabled,
                        weekly_summary_enabled, smart_suggestions_enabled,
                        morning_briefing_time, evening_review_time,
                        weekly_summary_day_of_week, weekly_summary_time,
                        timezone, created_at, updated_at
                    FROM agent_settings
                    WHERE user_id = $1
                    """,
                    user_id,
                )

                if not settings:
                    # Create default settings
                    settings = await db.fetchrow(
                        """
                        INSERT INTO agent_settings (user_id)
                        VALUES ($1)
                        RETURNING
                            id, user_id,
                            morning_briefing_enabled, evening_review_enabled,
                            weekly_summary_enabled, smart_suggestions_enabled,
                            morning_briefing_time, evening_review_time,
                            weekly_summary_day_of_week, weekly_summary_time,
                            timezone, created_at, updated_at
                        """,
                        user_id,
                    )

                return {
                    "success": True,
                    "data": {
                        "id": str(settings["id"]),
                        "user_id": str(settings["user_id"]),
                        "morning_briefing": {
                            "enabled": settings["morning_briefing_enabled"],
                            "time": settings["morning_briefing_time"].isoformat() if settings["morning_briefing_time"] else "07:00:00",
                        },
                        "evening_review": {
                            "enabled": settings["evening_review_enabled"],
                            "time": settings["evening_review_time"].isoformat() if settings["evening_review_time"] else "20:00:00",
                        },
                        "weekly_summary": {
                            "enabled": settings["weekly_summary_enabled"],
                            "day_of_week": settings["weekly_summary_day_of_week"],
                            "time": settings["weekly_summary_time"].isoformat() if settings["weekly_summary_time"] else "18:00:00",
                        },
                        "smart_suggestions": {
                            "enabled": settings["smart_suggestions_enabled"],
                        },
                        "timezone": settings["timezone"],
                        "created_at": settings["created_at"].isoformat(),
                        "updated_at": settings["updated_at"].isoformat(),
                    },
                }

        except Exception as exc:
            logger.error("get_agent_settings_failed", error=str(exc), user_id=str(user_id))
            return {
                "success": False,
                "error": {"code": "GET_SETTINGS_FAILED", "message": str(exc)},
            }

    async def update_settings(self, user_id: UUID, updates: dict) -> dict:
        """
        Update agent settings for a user.

        Args:
            user_id: User UUID
            updates: Dictionary with settings to update

        Returns:
            dict with success status and updated settings
        """
        try:
            async with get_db_connection() as db:
                # Ensure settings exist
                await self.get_settings(user_id)

                # Build update query dynamically
                update_fields = []
                params = []
                param_count = 0

                # Handle nested updates
                if "morning_briefing" in updates:
                    mb = updates["morning_briefing"]
                    if "enabled" in mb:
                        param_count += 1
                        update_fields.append(f"morning_briefing_enabled = ${param_count}")
                        params.append(mb["enabled"])
                    if "time" in mb:
                        param_count += 1
                        update_fields.append(f"morning_briefing_time = ${param_count}")
                        # Parse time string (HH:MM:SS or HH:MM)
                        params.append(self._parse_time(mb["time"]))

                if "evening_review" in updates:
                    er = updates["evening_review"]
                    if "enabled" in er:
                        param_count += 1
                        update_fields.append(f"evening_review_enabled = ${param_count}")
                        params.append(er["enabled"])
                    if "time" in er:
                        param_count += 1
                        update_fields.append(f"evening_review_time = ${param_count}")
                        params.append(self._parse_time(er["time"]))

                if "weekly_summary" in updates:
                    ws = updates["weekly_summary"]
                    if "enabled" in ws:
                        param_count += 1
                        update_fields.append(f"weekly_summary_enabled = ${param_count}")
                        params.append(ws["enabled"])
                    if "day_of_week" in ws:
                        param_count += 1
                        update_fields.append(f"weekly_summary_day_of_week = ${param_count}")
                        params.append(ws["day_of_week"])
                    if "time" in ws:
                        param_count += 1
                        update_fields.append(f"weekly_summary_time = ${param_count}")
                        params.append(self._parse_time(ws["time"]))

                if "smart_suggestions" in updates:
                    ss = updates["smart_suggestions"]
                    if "enabled" in ss:
                        param_count += 1
                        update_fields.append(f"smart_suggestions_enabled = ${param_count}")
                        params.append(ss["enabled"])

                if "timezone" in updates:
                    param_count += 1
                    update_fields.append(f"timezone = ${param_count}")
                    params.append(updates["timezone"])

                if not update_fields:
                    return await self.get_settings(user_id)

                # Add user_id parameter
                param_count += 1
                params.append(user_id)

                query = f"""
                    UPDATE agent_settings
                    SET {', '.join(update_fields)}
                    WHERE user_id = ${param_count}
                    RETURNING id
                """

                await db.fetchrow(query, *params)

                logger.info("agent_settings_updated", user_id=str(user_id))

                # Return updated settings
                return await self.get_settings(user_id)

        except Exception as exc:
            logger.error("update_agent_settings_failed", error=str(exc), user_id=str(user_id))
            return {
                "success": False,
                "error": {"code": "UPDATE_SETTINGS_FAILED", "message": str(exc)},
            }

    async def get_enabled_agents_for_user(self, user_id: UUID) -> dict:
        """
        Get list of enabled agents for a user with their schedules.

        Returns:
            dict with enabled agents and their configurations
        """
        result = await self.get_settings(user_id)
        if not result.get("success"):
            return result

        settings = result["data"]
        enabled_agents = []

        if settings["morning_briefing"]["enabled"]:
            enabled_agents.append({
                "name": "morning_briefing",
                "schedule": settings["morning_briefing"]["time"],
                "timezone": settings["timezone"],
            })

        if settings["evening_review"]["enabled"]:
            enabled_agents.append({
                "name": "evening_review",
                "schedule": settings["evening_review"]["time"],
                "timezone": settings["timezone"],
            })

        if settings["weekly_summary"]["enabled"]:
            enabled_agents.append({
                "name": "weekly_summary",
                "schedule": {
                    "day_of_week": settings["weekly_summary"]["day_of_week"],
                    "time": settings["weekly_summary"]["time"],
                },
                "timezone": settings["timezone"],
            })

        if settings["smart_suggestions"]["enabled"]:
            enabled_agents.append({
                "name": "smart_suggestions",
                "schedule": "on_demand",
                "timezone": settings["timezone"],
            })

        return {
            "success": True,
            "data": {
                "enabled_agents": enabled_agents,
                "timezone": settings["timezone"],
            },
        }

    async def get_all_users_with_enabled_agents(self) -> list[dict]:
        """
        Get all users who have at least one agent enabled.

        Returns:
            List of user settings with enabled agents
        """
        try:
            async with get_db_connection() as db:
                rows = await db.fetch(
                    """
                    SELECT
                        user_id,
                        morning_briefing_enabled, morning_briefing_time,
                        evening_review_enabled, evening_review_time,
                        weekly_summary_enabled, weekly_summary_day_of_week, weekly_summary_time,
                        smart_suggestions_enabled,
                        timezone
                    FROM agent_settings
                    WHERE morning_briefing_enabled = true
                       OR evening_review_enabled = true
                       OR weekly_summary_enabled = true
                       OR smart_suggestions_enabled = true
                    """
                )

                users = []
                for row in rows:
                    user_data = {
                        "user_id": str(row["user_id"]),
                        "timezone": row["timezone"],
                        "enabled_agents": [],
                    }

                    if row["morning_briefing_enabled"]:
                        user_data["enabled_agents"].append({
                            "name": "morning_briefing",
                            "time": row["morning_briefing_time"],
                        })

                    if row["evening_review_enabled"]:
                        user_data["enabled_agents"].append({
                            "name": "evening_review",
                            "time": row["evening_review_time"],
                        })

                    if row["weekly_summary_enabled"]:
                        user_data["enabled_agents"].append({
                            "name": "weekly_summary",
                            "day_of_week": row["weekly_summary_day_of_week"],
                            "time": row["weekly_summary_time"],
                        })

                    users.append(user_data)

                return users

        except Exception as exc:
            logger.error("get_users_with_enabled_agents_failed", error=str(exc))
            return []

    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        if isinstance(time_str, time):
            return time_str

        # Handle HH:MM:SS or HH:MM format
        parts = time_str.split(":")
        if len(parts) == 2:
            return time(int(parts[0]), int(parts[1]), 0)
        elif len(parts) == 3:
            return time(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            raise ValueError(f"Invalid time format: {time_str}")
