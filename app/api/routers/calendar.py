from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_current_user, get_db
from api.models.calendar import CalendarEventCreate, CalendarEventUpdate
from api.services.calendar_service import CalendarService

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.get("/events", response_model=dict)
async def list_calendar_events(
    start: datetime = Query(..., description="Start of the window (UTC)"),
    end: datetime = Query(..., description="End of the window (UTC)"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.list_events(user_id, start, end, status)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/events", response_model=dict)
async def create_calendar_event(
    payload: CalendarEventCreate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.create_event(user_id, payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/events/{event_id}", response_model=dict)
async def update_calendar_event(
    event_id: UUID,
    payload: CalendarEventUpdate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.update_event(event_id, user_id, payload)
    if not result.get("success"):
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.delete("/events/{event_id}", response_model=dict)
async def delete_calendar_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.cancel_event(event_id, user_id)
    if not result.get("success"):
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.post("/events/{event_id}/reminders/{reminder_id}", response_model=dict)
async def link_reminder(
    event_id: UUID,
    reminder_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.link_reminder_to_event(user_id, event_id, reminder_id)
    if not result.get("success"):
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.delete("/events/{event_id}/reminders/{reminder_id}", response_model=dict)
async def unlink_reminder(
    event_id: UUID,
    reminder_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.unlink_reminder_from_event(user_id, event_id, reminder_id)
    if not result.get("success"):
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result
