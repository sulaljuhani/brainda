from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from api.metrics import tool_calls_total
from api.models.task import TaskCreate, TaskUpdate
from api.services.task_service import TaskService

logger = structlog.get_logger()

TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a task with optional recurrence and hierarchy support.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "category_id": {"type": "string", "description": "Category UUID"},
                    "starts_at": {"type": "string", "description": "ISO8601 timestamp when task starts"},
                    "ends_at": {"type": "string", "description": "ISO8601 timestamp when task ends"},
                    "all_day": {"type": "boolean", "description": "Whether task is all-day"},
                    "timezone": {"type": "string", "description": "IANA timezone (default: UTC)"},
                    "rrule": {"type": "string", "description": "RFC 5545 recurrence rule"},
                    "parent_task_id": {"type": "string", "description": "Parent task UUID for subtasks"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "category_id": {"type": "string"},
                    "starts_at": {"type": "string"},
                    "ends_at": {"type": "string"},
                    "all_day": {"type": "boolean"},
                    "timezone": {"type": "string"},
                    "rrule": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "completed", "cancelled"]},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks with optional filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["active", "completed", "cancelled"], "description": "Filter by status"},
                    "category_id": {"type": "string", "description": "Filter by category UUID"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_subtask",
            "description": "Create a subtask under an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_task_id": {"type": "string", "description": "Parent task UUID"},
                    "title": {"type": "string", "description": "Subtask title"},
                    "description": {"type": "string", "description": "Subtask description"},
                    "starts_at": {"type": "string"},
                    "ends_at": {"type": "string"},
                },
                "required": ["parent_task_id", "title"],
            },
        },
    },
]


async def execute_task_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    db,
) -> dict[str, Any]:
    """Execute task-related tools."""
    tool_calls_total.labels(tool_name=tool_name).inc()

    task_service = TaskService(db)

    try:
        if tool_name == "create_task":
            task_data = TaskCreate(**arguments)
            task = await task_service.create_task(user_id, task_data)
            return {
                "success": True,
                "data": {
                    "task_id": str(task["id"]),
                    "title": task["title"],
                    "status": task["status"],
                },
            }

        elif tool_name == "update_task":
            task_id = UUID(arguments.pop("task_id"))
            task_data = TaskUpdate(**arguments)
            task = await task_service.update_task(user_id, task_id, task_data)
            return {
                "success": True,
                "data": {
                    "task_id": str(task["id"]),
                    "title": task["title"],
                    "status": task["status"],
                },
            }

        elif tool_name == "complete_task":
            task_id = UUID(arguments["task_id"])
            task = await task_service.complete_task(user_id, task_id)
            return {
                "success": True,
                "data": {
                    "task_id": str(task["id"]),
                    "title": task["title"],
                    "completed_at": task["completed_at"].isoformat() if task.get("completed_at") else None,
                },
            }

        elif tool_name == "delete_task":
            task_id = UUID(arguments["task_id"])
            await task_service.delete_task(user_id, task_id)
            return {
                "success": True,
                "data": {"task_id": str(task_id)},
            }

        elif tool_name == "list_tasks":
            status = arguments.get("status")
            category_id = arguments.get("category_id")
            tasks = await task_service.list_tasks(
                user_id,
                status=status,
                category_id=UUID(category_id) if category_id else None,
            )
            return {
                "success": True,
                "data": {
                    "tasks": [
                        {
                            "id": str(task["id"]),
                            "title": task["title"],
                            "status": task["status"],
                            "starts_at": task.get("starts_at"),
                            "category_name": task.get("category_name"),
                        }
                        for task in tasks
                    ],
                    "count": len(tasks),
                },
            }

        elif tool_name == "create_subtask":
            parent_task_id = UUID(arguments.pop("parent_task_id"))
            arguments["parent_task_id"] = str(parent_task_id)
            task_data = TaskCreate(**arguments)
            task = await task_service.create_task(user_id, task_data)
            return {
                "success": True,
                "data": {
                    "task_id": str(task["id"]),
                    "title": task["title"],
                    "parent_task_id": str(parent_task_id),
                },
            }

        else:
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Unknown task tool: {tool_name}",
                },
            }

    except ValueError as e:
        logger.error("task_tool_validation_error", tool=tool_name, error=str(e))
        return {
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": str(e)},
        }
    except Exception as e:
        logger.error("task_tool_execution_error", tool=tool_name, error=str(e))
        return {
            "success": False,
            "error": {"code": "EXECUTION_ERROR", "message": str(e)},
        }
