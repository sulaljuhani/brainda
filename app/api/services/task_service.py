from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
import structlog

from api.models.task import TaskCreate, TaskUpdate, TaskResponse

logger = structlog.get_logger()


class TaskService:
    def __init__(self, db):
        self.db = db

    async def create_task(
        self,
        user_id: UUID,
        data: TaskCreate,
    ) -> dict:
        """
        Create a new task.
        Returns standardized response format.
        """
        try:
            # Validate parent task if provided
            if data.parent_task_id:
                parent = await self.db.fetchrow(
                    "SELECT id, user_id, status FROM tasks WHERE id = $1",
                    data.parent_task_id,
                )
                if not parent or parent["user_id"] != user_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "INVALID_PARENT",
                            "message": "Parent task not found for this user",
                        },
                    }
                if parent["status"] == "cancelled":
                    return {
                        "success": False,
                        "error": {
                            "code": "INVALID_PARENT",
                            "message": "Cannot create subtask under cancelled task",
                        },
                    }

            # Validate category if provided
            if data.category_id:
                category = await self.db.fetchrow(
                    "SELECT id, user_id FROM task_categories WHERE id = $1",
                    data.category_id,
                )
                if not category or category["user_id"] != user_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "INVALID_CATEGORY",
                            "message": "Category not found for this user",
                        },
                    }

            async with self.db.transaction():
                task = await self.db.fetchrow(
                    """
                    INSERT INTO tasks (
                        user_id, parent_task_id, title, description, category_id,
                        starts_at, ends_at, all_day, timezone, rrule, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active')
                    RETURNING *
                    """,
                    user_id,
                    data.parent_task_id,
                    data.title,
                    data.description,
                    data.category_id,
                    data.starts_at,
                    data.ends_at,
                    data.all_day,
                    data.timezone,
                    data.rrule,
                )

            logger.info(
                "task_created",
                user_id=str(user_id),
                task_id=str(task["id"]),
                title=data.title,
                has_parent=bool(data.parent_task_id),
            )

            # Fetch with category name
            task_with_category = await self._fetch_task_with_category(task["id"])

            return {
                "success": True,
                "data": task_with_category,
            }

        except Exception as exc:
            logger.error("task_creation_failed", error=str(exc), user_id=str(user_id))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    async def list_tasks(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        include_subtasks: bool = True,
        category_id: Optional[UUID] = None,
        limit: int = 500,
    ) -> List[dict]:
        """
        List tasks for a user with optional filtering.
        Returns only top-level tasks if include_subtasks=False.
        """
        query = """
            SELECT t.*, tc.name as category_name
            FROM tasks t
            LEFT JOIN task_categories tc ON t.category_id = tc.id
            WHERE t.user_id = $1
        """
        params = [user_id]
        param_count = 1

        if status:
            param_count += 1
            query += f" AND t.status = ${param_count}"
            params.append(status)

        if category_id:
            param_count += 1
            query += f" AND t.category_id = ${param_count}"
            params.append(category_id)

        if not include_subtasks:
            query += " AND t.parent_task_id IS NULL"

        query += f" ORDER BY t.created_at DESC LIMIT ${param_count + 1}"
        params.append(limit)

        rows = await self.db.fetch(query, *params)

        tasks = [dict(row) for row in rows]

        # If include_subtasks, organize into hierarchy
        if include_subtasks:
            tasks = await self._organize_task_hierarchy(tasks)

        return tasks

    async def get_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get a single task with its subtasks."""
        task = await self._fetch_task_with_category(task_id, user_id)

        if not task:
            return None

        # Fetch subtasks
        subtasks = await self.db.fetch(
            """
            SELECT t.*, tc.name as category_name
            FROM tasks t
            LEFT JOIN task_categories tc ON t.category_id = tc.id
            WHERE t.parent_task_id = $1 AND t.user_id = $2
            ORDER BY t.created_at ASC
            """,
            task_id,
            user_id,
        )

        task["subtasks"] = [dict(s) for s in subtasks]
        return task

    async def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        data: TaskUpdate,
    ) -> dict:
        """Update a task."""
        try:
            # Check task exists and belongs to user
            existing = await self.db.fetchrow(
                "SELECT * FROM tasks WHERE id = $1 AND user_id = $2",
                task_id,
                user_id,
            )
            if not existing:
                return {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Task not found",
                    },
                }

            # Validate category if being updated
            if data.category_id:
                category = await self.db.fetchrow(
                    "SELECT id, user_id FROM task_categories WHERE id = $1",
                    data.category_id,
                )
                if not category or category["user_id"] != user_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "INVALID_CATEGORY",
                            "message": "Category not found for this user",
                        },
                    }

            # Build update query dynamically
            update_fields = []
            params = []
            param_count = 0

            for field, value in data.dict(exclude_unset=True, exclude={"schema_version"}).items():
                param_count += 1
                update_fields.append(f"{field} = ${param_count}")
                params.append(value)

            if not update_fields:
                return {
                    "success": True,
                    "data": dict(existing),
                }

            # Add updated_at
            param_count += 1
            update_fields.append(f"updated_at = ${param_count}")
            params.append(datetime.now(timezone.utc))

            # Add WHERE clause parameters
            param_count += 1
            params.append(task_id)
            param_count += 1
            params.append(user_id)

            query = f"""
                UPDATE tasks
                SET {', '.join(update_fields)}
                WHERE id = ${param_count - 1} AND user_id = ${param_count}
                RETURNING *
            """

            async with self.db.transaction():
                updated = await self.db.fetchrow(query, *params)

            logger.info("task_updated", task_id=str(task_id), user_id=str(user_id))

            # Fetch with category name
            task_with_category = await self._fetch_task_with_category(task_id)

            return {
                "success": True,
                "data": task_with_category,
            }

        except Exception as exc:
            logger.error("task_update_failed", error=str(exc), task_id=str(task_id))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    async def complete_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Mark a task as completed."""
        return await self.update_task(
            task_id,
            user_id,
            TaskUpdate(
                status="completed",
                completed_at=datetime.now(timezone.utc),
            ),
        )

    async def delete_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Delete a task (soft delete by setting status to cancelled)."""
        return await self.update_task(
            task_id,
            user_id,
            TaskUpdate(status="cancelled"),
        )

    async def get_subtasks(
        self,
        parent_task_id: UUID,
        user_id: UUID,
    ) -> List[dict]:
        """Get all subtasks of a parent task."""
        subtasks = await self.db.fetch(
            """
            SELECT t.*, tc.name as category_name
            FROM tasks t
            LEFT JOIN task_categories tc ON t.category_id = tc.id
            WHERE t.parent_task_id = $1 AND t.user_id = $2
            ORDER BY t.created_at ASC
            """,
            parent_task_id,
            user_id,
        )
        return [dict(s) for s in subtasks]

    async def move_task_to_parent(
        self,
        task_id: UUID,
        parent_task_id: Optional[UUID],
        user_id: UUID,
    ) -> dict:
        """
        Move a task to a new parent (or to top-level if parent_task_id is None).
        Used for drag-and-drop hierarchy changes.
        """
        try:
            # Check task exists
            task = await self.db.fetchrow(
                "SELECT * FROM tasks WHERE id = $1 AND user_id = $2",
                task_id,
                user_id,
            )
            if not task:
                return {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Task not found",
                    },
                }

            # Validate new parent if provided
            if parent_task_id:
                # Prevent circular reference
                if parent_task_id == task_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "CIRCULAR_REFERENCE",
                            "message": "Task cannot be its own parent",
                        },
                    }

                parent = await self.db.fetchrow(
                    "SELECT id, user_id, parent_task_id FROM tasks WHERE id = $1",
                    parent_task_id,
                )
                if not parent or parent["user_id"] != user_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "INVALID_PARENT",
                            "message": "Parent task not found",
                        },
                    }

                # Prevent moving parent under its own child
                if parent["parent_task_id"] == task_id:
                    return {
                        "success": False,
                        "error": {
                            "code": "CIRCULAR_REFERENCE",
                            "message": "Cannot move parent under its own child",
                        },
                    }

            async with self.db.transaction():
                updated = await self.db.fetchrow(
                    """
                    UPDATE tasks
                    SET parent_task_id = $1, updated_at = $2
                    WHERE id = $3 AND user_id = $4
                    RETURNING *
                    """,
                    parent_task_id,
                    datetime.now(timezone.utc),
                    task_id,
                    user_id,
                )

            logger.info(
                "task_moved",
                task_id=str(task_id),
                new_parent=str(parent_task_id) if parent_task_id else "top_level",
            )

            return {
                "success": True,
                "data": dict(updated),
            }

        except Exception as exc:
            logger.error("task_move_failed", error=str(exc), task_id=str(task_id))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    # Helper methods

    async def _fetch_task_with_category(
        self,
        task_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[dict]:
        """Fetch a task with its category name joined."""
        query = """
            SELECT t.*, tc.name as category_name
            FROM tasks t
            LEFT JOIN task_categories tc ON t.category_id = tc.id
            WHERE t.id = $1
        """
        params = [task_id]

        if user_id:
            query += " AND t.user_id = $2"
            params.append(user_id)

        row = await self.db.fetchrow(query, *params)
        return dict(row) if row else None

    async def _organize_task_hierarchy(self, tasks: List[dict]) -> List[dict]:
        """
        Organize flat list of tasks into hierarchy.
        Returns only top-level tasks with subtasks nested.
        """
        task_map = {task["id"]: {**task, "subtasks": []} for task in tasks}
        top_level = []

        for task in tasks:
            if task["parent_task_id"]:
                parent = task_map.get(task["parent_task_id"])
                if parent:
                    parent["subtasks"].append(task_map[task["id"]])
            else:
                top_level.append(task_map[task["id"]])

        return top_level
