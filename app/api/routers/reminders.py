from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from uuid import UUID

from api.models.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
    ReminderSnoozeRequest,
)
from api.services.reminder_service import ReminderService
from api.dependencies import get_db, get_current_user


router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])

@router.post("", response_model=dict)
async def create_reminder(
    data: ReminderCreate,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create a new reminder"""
    service = ReminderService(db)
    result = await service.create_reminder(user_id, data)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("", response_model=List[ReminderResponse])
async def list_reminders(
    status: Optional[str] = None,
    limit: int = 50,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """List user's reminders"""
    service = ReminderService(db)
    reminders = await service.list_reminders(user_id, status, limit)
    return reminders

@router.patch("/{reminder_id}", response_model=dict)
async def update_reminder(
    reminder_id: UUID,
    data: ReminderUpdate,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update a reminder"""
    service = ReminderService(db)
    result = await service.update_reminder(reminder_id, user_id, data)
    
    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result

@router.post("/{reminder_id}/snooze", response_model=dict)
async def snooze_reminder(
    reminder_id: UUID,
    payload: ReminderSnoozeRequest,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Snooze a reminder"""
    service = ReminderService(db)
    result = await service.snooze_reminder(reminder_id, user_id, payload.duration_minutes)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

@router.delete("/{reminder_id}")
async def cancel_reminder(
    reminder_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Cancel a reminder (soft delete)"""
    service = ReminderService(db)
    result = await service.update_reminder(
        reminder_id, 
        user_id, 
        ReminderUpdate(status="cancelled")
    )
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {"success": True, "message": "Reminder cancelled"}
