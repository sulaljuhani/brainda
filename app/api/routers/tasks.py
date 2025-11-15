from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from uuid import UUID

from api.models.task import TaskCreate, TaskUpdate, TaskResponse
from api.services.task_service import TaskService
from api.dependencies import get_db, get_current_user


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=dict)
async def create_task(
    data: TaskCreate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Create a new task"""
    service = TaskService(db)
    result = await service.create_task(user_id, data)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status (active, completed, cancelled)"),
    include_subtasks: bool = Query(True, description="Include subtasks in hierarchy"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    limit: int = Query(500, ge=1, le=1000),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """List user's tasks"""
    service = TaskService(db)
    tasks = await service.list_tasks(
        user_id,
        status=status,
        include_subtasks=include_subtasks,
        category_id=category_id,
        limit=limit,
    )
    return tasks


@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Get a specific task with its subtasks"""
    service = TaskService(db)
    task = await service.get_task(task_id, user_id)

    if not task:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Task not found"})

    return {"success": True, "data": task}


@router.patch("/{task_id}", response_model=dict)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Update a task"""
    service = TaskService(db)
    result = await service.update_task(task_id, user_id, data)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.post("/{task_id}/complete", response_model=dict)
async def complete_task(
    task_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mark a task as completed"""
    service = TaskService(db)
    result = await service.complete_task(task_id, user_id)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Delete a task (soft delete - sets status to cancelled)"""
    service = TaskService(db)
    result = await service.delete_task(task_id, user_id)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result


@router.get("/{task_id}/subtasks", response_model=List[dict])
async def get_subtasks(
    task_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Get all subtasks of a parent task"""
    service = TaskService(db)
    subtasks = await service.get_subtasks(task_id, user_id)
    return subtasks


@router.post("/{task_id}/move", response_model=dict)
async def move_task(
    task_id: UUID,
    parent_task_id: Optional[UUID] = Query(None, description="New parent task ID (null for top-level)"),
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    """Move a task to a new parent (for drag-and-drop hierarchy changes)"""
    service = TaskService(db)
    result = await service.move_task_to_parent(task_id, parent_task_id, user_id)

    if not result["success"]:
        status_code = 404 if result["error"]["code"] == "NOT_FOUND" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
