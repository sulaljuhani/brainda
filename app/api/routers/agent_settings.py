"""Agent settings API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from api.dependencies import get_current_user_id
from api.services.agent_settings_service import AgentSettingsService

router = APIRouter(prefix="/api/v1/agent-settings", tags=["agent-settings"])


class MorningBriefingSettings(BaseModel):
    """Morning briefing settings"""
    enabled: Optional[bool] = None
    time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$", description="Time in HH:MM or HH:MM:SS format")


class EveningReviewSettings(BaseModel):
    """Evening review settings"""
    enabled: Optional[bool] = None
    time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$", description="Time in HH:MM or HH:MM:SS format")


class WeeklySummarySettings(BaseModel):
    """Weekly summary settings"""
    enabled: Optional[bool] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, 6=Sunday")
    time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$", description="Time in HH:MM or HH:MM:SS format")


class SmartSuggestionsSettings(BaseModel):
    """Smart suggestions settings"""
    enabled: Optional[bool] = None


class AgentSettingsUpdate(BaseModel):
    """Agent settings update request"""
    morning_briefing: Optional[MorningBriefingSettings] = None
    evening_review: Optional[EveningReviewSettings] = None
    weekly_summary: Optional[WeeklySummarySettings] = None
    smart_suggestions: Optional[SmartSuggestionsSettings] = None
    timezone: Optional[str] = Field(None, description="IANA timezone (e.g., America/New_York)")

    class Config:
        schema_extra = {
            "example": {
                "morning_briefing": {
                    "enabled": True,
                    "time": "07:00"
                },
                "evening_review": {
                    "enabled": True,
                    "time": "20:00"
                },
                "weekly_summary": {
                    "enabled": True,
                    "day_of_week": 6,
                    "time": "18:00"
                },
                "smart_suggestions": {
                    "enabled": False
                },
                "timezone": "America/New_York"
            }
        }


@router.get("")
async def get_agent_settings(
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Get agent settings for the current user.
    Creates default settings if they don't exist.
    """
    service = AgentSettingsService()
    result = await service.get_settings(user_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", {}).get("message", "Failed to get agent settings"),
        )

    return result.get("data")


@router.patch("")
async def update_agent_settings(
    settings: AgentSettingsUpdate,
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Update agent settings for the current user.

    You can update any subset of settings. For example:
    - Enable/disable individual agents
    - Change agent firing times
    - Update timezone

    After updating settings, agent schedules will be reconfigured automatically.
    """
    service = AgentSettingsService()

    # Convert Pydantic models to dict
    updates = {}
    if settings.morning_briefing is not None:
        updates["morning_briefing"] = settings.morning_briefing.dict(exclude_none=True)
    if settings.evening_review is not None:
        updates["evening_review"] = settings.evening_review.dict(exclude_none=True)
    if settings.weekly_summary is not None:
        updates["weekly_summary"] = settings.weekly_summary.dict(exclude_none=True)
    if settings.smart_suggestions is not None:
        updates["smart_suggestions"] = settings.smart_suggestions.dict(exclude_none=True)
    if settings.timezone is not None:
        updates["timezone"] = settings.timezone

    # Validate timezone if provided
    if "timezone" in updates:
        import pytz
        try:
            pytz.timezone(updates["timezone"])
        except pytz.exceptions.UnknownTimeZoneError:
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {updates['timezone']}")

    result = await service.update_settings(user_id, updates)

    if not result.get("success"):
        error = result.get("error", {})
        raise HTTPException(
            status_code=400,
            detail=error.get("message", "Failed to update agent settings"),
        )

    # Trigger agent schedule reconfiguration
    from worker.scheduler import reconfigure_agent_schedules
    try:
        await reconfigure_agent_schedules(user_id)
    except Exception as exc:
        # Log error but don't fail the request
        import structlog
        logger = structlog.get_logger()
        logger.warning("failed_to_reconfigure_agent_schedules", error=str(exc), user_id=str(user_id))

    return result.get("data")


@router.get("/enabled-agents")
async def get_enabled_agents(
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Get list of enabled agents for the current user.

    Returns a simplified view showing which agents are active
    and their schedules.
    """
    service = AgentSettingsService()
    result = await service.get_enabled_agents_for_user(user_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", {}).get("message", "Failed to get enabled agents"),
        )

    return result.get("data")


@router.post("/test-agent/{agent_name}")
async def test_agent(
    agent_name: str,
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Trigger a test run of an agent immediately (for testing purposes).

    Available agents:
    - morning_briefing
    - evening_review
    - weekly_summary
    - smart_suggestions
    """
    from worker.agents import (
        morning_briefing_agent,
        evening_review_agent,
        weekly_summary_agent,
        smart_suggestions_agent,
    )

    agent_map = {
        "morning_briefing": morning_briefing_agent,
        "evening_review": evening_review_agent,
        "weekly_summary": weekly_summary_agent,
        "smart_suggestions": smart_suggestions_agent,
    }

    if agent_name not in agent_map:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Available: {', '.join(agent_map.keys())}",
        )

    # Queue the agent for immediate execution
    agent_task = agent_map[agent_name]
    try:
        agent_task.delay(str(user_id))
        return {
            "success": True,
            "message": f"Agent '{agent_name}' queued for execution",
            "agent": agent_name,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue agent: {str(exc)}",
        )
