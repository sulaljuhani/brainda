from datetime import datetime, timezone
from typing import List, Literal
from uuid import UUID
import structlog
from asyncpg.exceptions import UniqueViolationError

from api.models.category import CategoryCreate, CategoryUpdate, CategoryResponse

logger = structlog.get_logger()

# Map category type to table name
CATEGORY_TABLES = {
    "tasks": "task_categories",
    "events": "event_categories",
    "reminders": "reminder_categories",
}


class CategoryService:
    def __init__(self, db):
        self.db = db

    def _get_table_name(self, category_type: str) -> str:
        """Get the table name for a category type."""
        table = CATEGORY_TABLES.get(category_type)
        if not table:
            raise ValueError(f"Invalid category type: {category_type}")
        return table

    async def create_category(
        self,
        user_id: UUID,
        category_type: Literal["tasks", "events", "reminders"],
        data: CategoryCreate,
    ) -> dict:
        """
        Create a new category of the specified type.
        Returns standardized response format.
        """
        try:
            table = self._get_table_name(category_type)

            async with self.db.transaction():
                category = await self.db.fetchrow(
                    f"""
                    INSERT INTO {table} (user_id, name, color)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    user_id,
                    data.name,
                    data.color,
                )

            logger.info(
                "category_created",
                user_id=str(user_id),
                category_id=str(category["id"]),
                category_type=category_type,
                name=data.name,
            )

            return {
                "success": True,
                "data": dict(category),
            }

        except UniqueViolationError:
            logger.warning(
                "duplicate_category_name",
                user_id=str(user_id),
                category_type=category_type,
                name=data.name,
            )
            return {
                "success": False,
                "error": {
                    "code": "DUPLICATE_NAME",
                    "message": f"Category '{data.name}' already exists",
                },
            }
        except Exception as exc:
            logger.error(
                "category_creation_failed",
                error=str(exc),
                user_id=str(user_id),
                category_type=category_type,
            )
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    async def list_categories(
        self,
        user_id: UUID,
        category_type: Literal["tasks", "events", "reminders"],
    ) -> List[dict]:
        """List all categories of the specified type for a user."""
        table = self._get_table_name(category_type)

        rows = await self.db.fetch(
            f"""
            SELECT * FROM {table}
            WHERE user_id = $1
            ORDER BY name ASC
            """,
            user_id,
        )

        return [dict(row) for row in rows]

    async def update_category(
        self,
        category_id: UUID,
        user_id: UUID,
        category_type: Literal["tasks", "events", "reminders"],
        data: CategoryUpdate,
    ) -> dict:
        """Update a category."""
        try:
            table = self._get_table_name(category_type)

            # Check category exists and belongs to user
            existing = await self.db.fetchrow(
                f"SELECT * FROM {table} WHERE id = $1 AND user_id = $2",
                category_id,
                user_id,
            )
            if not existing:
                return {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Category not found",
                    },
                }

            # Build update query dynamically
            update_fields = []
            params = []
            param_count = 0

            for field, value in data.dict(exclude_unset=True).items():
                param_count += 1
                update_fields.append(f"{field} = ${param_count}")
                params.append(value)

            if not update_fields:
                return {
                    "success": True,
                    "data": dict(existing),
                }

            # Add WHERE clause parameters
            param_count += 1
            params.append(category_id)
            param_count += 1
            params.append(user_id)

            query = f"""
                UPDATE {table}
                SET {', '.join(update_fields)}
                WHERE id = ${param_count - 1} AND user_id = ${param_count}
                RETURNING *
            """

            async with self.db.transaction():
                updated = await self.db.fetchrow(query, *params)

            logger.info(
                "category_updated",
                category_id=str(category_id),
                user_id=str(user_id),
                category_type=category_type,
            )

            return {
                "success": True,
                "data": dict(updated),
            }

        except UniqueViolationError:
            return {
                "success": False,
                "error": {
                    "code": "DUPLICATE_NAME",
                    "message": f"Category name already exists",
                },
            }
        except Exception as exc:
            logger.error(
                "category_update_failed",
                error=str(exc),
                category_id=str(category_id),
                category_type=category_type,
            )
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }

    async def delete_category(
        self,
        category_id: UUID,
        user_id: UUID,
        category_type: Literal["tasks", "events", "reminders"],
    ) -> dict:
        """
        Delete a category.
        Note: Due to ON DELETE SET NULL, existing items will have their category_id set to NULL.
        """
        try:
            table = self._get_table_name(category_type)

            async with self.db.transaction():
                deleted = await self.db.fetchrow(
                    f"""
                    DELETE FROM {table}
                    WHERE id = $1 AND user_id = $2
                    RETURNING *
                    """,
                    category_id,
                    user_id,
                )

            if not deleted:
                return {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Category not found",
                    },
                }

            logger.info(
                "category_deleted",
                category_id=str(category_id),
                user_id=str(user_id),
                category_type=category_type,
            )

            return {
                "success": True,
                "message": "Category deleted successfully",
            }

        except Exception as exc:
            logger.error(
                "category_deletion_failed",
                error=str(exc),
                category_id=str(category_id),
                category_type=category_type,
            )
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                },
            }
