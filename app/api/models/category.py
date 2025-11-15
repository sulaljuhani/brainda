from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
import re


class CategoryCreate(BaseModel):
    """Schema for creating categories"""
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = None

    @validator('color')
    def validate_color(cls, v):
        if v is None:
            return v
        # Validate hex color format (#RRGGBB)
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError("color must be in hex format (#RRGGBB)")
        return v


class CategoryUpdate(BaseModel):
    """Schema for updating categories"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = None

    @validator('color')
    def validate_color(cls, v):
        if v is None:
            return v
        # Validate hex color format (#RRGGBB)
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError("color must be in hex format (#RRGGBB)")
        return v


class CategoryResponse(BaseModel):
    """Schema for category responses"""
    id: UUID
    user_id: UUID
    name: str
    color: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
