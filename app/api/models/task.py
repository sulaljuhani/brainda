from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID


class TaskCreate(BaseModel):
    """Schema for creating tasks"""
    schema_version: Literal["1.0"] = "1.0"
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category_id: Optional[UUID] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    all_day: bool = False
    timezone: str = "UTC"
    rrule: Optional[str] = None
    parent_task_id: Optional[UUID] = None

    @validator('timezone')
    def validate_timezone(cls, v):
        import pytz
        try:
            pytz.timezone(v)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @validator('rrule')
    def validate_rrule(cls, v):
        if v is None:
            return v
        from dateutil.rrule import rrulestr
        try:
            rrulestr(v)
        except:
            raise ValueError(f"Invalid RRULE: {v}")
        return v

    @validator('ends_at')
    def validate_end_after_start(cls, v, values):
        if v and 'starts_at' in values and values['starts_at']:
            if v < values['starts_at']:
                raise ValueError("ends_at must be after starts_at")
        return v


class TaskUpdate(BaseModel):
    """Schema for updating tasks"""
    schema_version: Literal["1.0"] = "1.0"
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    rrule: Optional[str] = None
    status: Optional[str] = None
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[UUID] = None

    @validator('status')
    def validate_status(cls, v):
        if v and v not in ['active', 'completed', 'cancelled']:
            raise ValueError("status must be one of: active, completed, cancelled")
        return v


class TaskResponse(BaseModel):
    """Schema for task responses"""
    id: UUID
    user_id: UUID
    parent_task_id: Optional[UUID]
    title: str
    description: Optional[str]
    category_id: Optional[UUID]
    category_name: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    all_day: bool
    timezone: str
    rrule: Optional[str]
    status: str
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    subtasks: List['TaskResponse'] = []

    class Config:
        orm_mode = True


# Enable forward references for recursive subtasks
TaskResponse.update_forward_refs()
