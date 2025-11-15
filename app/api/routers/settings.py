"""User Settings API Router

Provides endpoints for managing user preferences and settings.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from api.dependencies import get_db, get_current_user
from common.db import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["settings"])


class UserSettingsResponse(BaseModel):
    """User settings response model"""
    notifications_enabled: bool = True
    email_notifications: bool = True
    reminder_notifications: bool = True
    calendar_notifications: bool = True
    theme: Literal['light', 'dark', 'auto'] = 'dark'
    font_size: Literal['small', 'medium', 'large'] = 'medium'
    timezone: Optional[str] = 'UTC'


class UpdateUserSettingsRequest(BaseModel):
    """Update user settings request model"""
    notifications_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    reminder_notifications: Optional[bool] = None
    calendar_notifications: Optional[bool] = None
    theme: Optional[Literal['light', 'dark', 'auto']] = None
    font_size: Optional[Literal['small', 'medium', 'large']] = None
    timezone: Optional[str] = None


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    user_id: UUID = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Get user settings

    Returns the current user's settings. If no settings exist, default values are returned.
    """
    try:
        # Try to get existing settings
        row = await db.fetchrow(
            """
            SELECT
                notifications_enabled,
                email_notifications,
                reminder_notifications,
                calendar_notifications,
                theme,
                font_size,
                timezone
            FROM user_settings
            WHERE user_id = $1
            """,
            user_id,
        )

        if row:
            return UserSettingsResponse(**dict(row))

        # If no settings exist, create default settings
        await db.execute(
            """
            INSERT INTO user_settings (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )

        # Return defaults
        return UserSettingsResponse()

    except Exception as e:
        logger.error(f"Error fetching user settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    updates: UpdateUserSettingsRequest,
    user_id: UUID = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Update user settings

    Updates the current user's settings. Only provided fields will be updated.
    """
    try:
        # Build update query dynamically based on provided fields
        update_fields = []
        params = [user_id]
        param_count = 2

        update_data = updates.dict(exclude_unset=True)

        for field, value in update_data.items():
            update_fields.append(f"{field} = ${param_count}")
            params.append(value)
            param_count += 1

        if not update_fields:
            # No fields to update, just return current settings
            return await get_user_settings(user_id, db)

        # Upsert settings
        query = f"""
            INSERT INTO user_settings (user_id, {', '.join(update_data.keys())})
            VALUES ($1, {', '.join(f'${i+2}' for i in range(len(update_data)))})
            ON CONFLICT (user_id) DO UPDATE SET
                {', '.join(update_fields)},
                updated_at = NOW()
            RETURNING
                notifications_enabled,
                email_notifications,
                reminder_notifications,
                calendar_notifications,
                theme,
                font_size,
                timezone
        """

        row = await db.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=500, detail="Failed to update settings")

        return UserSettingsResponse(**dict(row))

    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")
