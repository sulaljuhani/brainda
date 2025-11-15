from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List, Literal
from uuid import UUID

from api.models.category import CategoryCreate, CategoryUpdate, CategoryResponse
from api.services.category_service import CategoryService
from api.dependencies import get_db, get_current_user


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@router.post("/{category_type}", response_model=dict)
async def create_category(
    category_type: Literal["tasks", "events", "reminders"] = Path(..., description="Type of category"),
    data: CategoryCreate = ...,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Create a new category for tasks, events, or reminders"""
    service = CategoryService(db)
    result = await service.create_category(user_id, category_type, data)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/{category_type}", response_model=List[CategoryResponse])
async def list_categories(
    category_type: Literal["tasks", "events", "reminders"] = Path(..., description="Type of category"),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """List all categories of a specific type for the current user"""
    service = CategoryService(db)
    categories = await service.list_categories(user_id, category_type)
    return categories


@router.patch("/{category_type}/{category_id}", response_model=dict)
async def update_category(
    category_type: Literal["tasks", "events", "reminders"] = Path(..., description="Type of category"),
    category_id: UUID = Path(..., description="Category ID"),
    data: CategoryUpdate = ...,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Update a category"""
    service = CategoryService(db)
    result = await service.update_category(category_id, user_id, category_type, data)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.delete("/{category_type}/{category_id}", response_model=dict)
async def delete_category(
    category_type: Literal["tasks", "events", "reminders"] = Path(..., description="Type of category"),
    category_id: UUID = Path(..., description="Category ID"),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Delete a category.
    Note: Existing items with this category will have their category_id set to NULL.
    """
    service = CategoryService(db)
    result = await service.delete_category(category_id, user_id, category_type)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
