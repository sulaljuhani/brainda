from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID
import structlog
from asyncpg.exceptions import UniqueViolationError
from api.models.reminder import ReminderCreate, ReminderUpdate
from api.metrics import reminders_created_total, reminders_deduped_total

logger = structlog.get_logger()

class ReminderService:
    def __init__(self, db):
        self.db = db
    
    async def create_reminder(
        self, 
        user_id: UUID, 
        data: ReminderCreate
    ) -> dict:
        """
        Create reminder with 5-minute deduplication window.
        Returns standardized response format.
        """
        # Check for duplicate in last 5 minutes
        existing = await self.db.fetchrow("""
            SELECT * FROM reminders 
            WHERE user_id = $1 
            AND title = $2 
            AND ABS(EXTRACT(EPOCH FROM (due_at_utc - $3::timestamptz))) < 1
            AND created_at > NOW() - INTERVAL '5 minutes'
            AND status = 'active'
        """, user_id, data.title, data.due_at_utc)
        
        if existing:
            logger.info(
                "duplicate_reminder_skipped",
                user_id=str(user_id),
                reminder_id=str(existing['id']),
                title=data.title,
                due_at_utc=data.due_at_utc.isoformat()
            )
            reminders_deduped_total.labels(user_id=str(user_id)).inc()
            return {
                "success": True,
                "deduplicated": True,
                "data": {
                    **dict(existing),
                    "message": f"Reminder already exists (created {self._time_ago(existing['created_at'])})"
                }
            }
        
        # Create new reminder
        try:
            reminder = await self.db.fetchrow("""
                INSERT INTO reminders (
                    user_id, title, body, due_at_utc, due_at_local, 
                    timezone, repeat_rrule, note_id, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
                RETURNING *
            """, 
                user_id, data.title, data.body, data.due_at_utc, 
                data.due_at_local, data.timezone, data.repeat_rrule, 
                data.note_id
            )
            
            logger.info(
                "reminder_created",
                user_id=str(user_id),
                reminder_id=str(reminder['id']),
                due_at_utc=data.due_at_utc.isoformat(),
                timezone=data.timezone,
                repeat=bool(data.repeat_rrule)
            )
            
            from worker.scheduler import schedule_reminder
            schedule_reminder(str(reminder['id']), data.due_at_utc)
            reminders_created_total.labels(user_id=str(user_id)).inc()
            
            return {"success": True, "data": dict(reminder)}
            
        except UniqueViolationError as e:
            # Race condition caught by DB constraint
            logger.warning(
                "duplicate_reminder_prevented_by_constraint",
                user_id=str(user_id),
                title=data.title,
                error=str(e)
            )
            # Fetch existing
            existing = await self.db.fetchrow("""
                SELECT * FROM reminders 
                WHERE user_id = $1 AND title = $2 
                AND ABS(EXTRACT(EPOCH FROM (due_at_utc - $3::timestamptz))) < 1
                ORDER BY created_at DESC LIMIT 1
            """, user_id, data.title, data.due_at_utc)
            
            reminders_deduped_total.labels(user_id=str(user_id)).inc()
            return {
                "success": True,
                "deduplicated": True,
                "data": dict(existing)
            }
    
    def _time_ago(self, dt: datetime) -> str:
        """Human readable time difference"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds} seconds ago"
        elif seconds < 3600:
            return f"{seconds // 60} minutes ago"
        else:
            return f"{seconds // 3600} hours ago"
    
    async def list_reminders(
        self, 
        user_id: UUID, 
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """List user's reminders"""
        query = """
            SELECT * FROM reminders 
            WHERE user_id = $1
        """
        params = [user_id]
        
        if status:
            query += " AND status = $2"
            params.append(status)
        
        query += " ORDER BY due_at_utc ASC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        reminders = await self.db.fetch(query, *params)
        return [dict(r) for r in reminders]
    
    async def update_reminder(
        self, 
        reminder_id: UUID, 
        user_id: UUID, 
        data: ReminderUpdate
    ) -> dict:
        """Update reminder (ownership check)"""
        # Verify ownership
        existing = await self.db.fetchrow(
            "SELECT * FROM reminders WHERE id = $1 AND user_id = $2",
            reminder_id, user_id
        )
        if not existing:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Reminder not found"
                }
            }
        
        # Build update query dynamically
        updates = []
        params = []
        param_idx = 1
        
        for field, value in data.dict(exclude_unset=True).items():
            if field != "schema_version" and value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return {"success": True, "data": dict(existing)}
        
        params.extend([reminder_id, user_id])
        query = f"""
            UPDATE reminders 
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING *
        """
        
        reminder = await self.db.fetchrow(query, *params)
        
        logger.info(
            "reminder_updated",
            user_id=str(user_id),
            reminder_id=str(reminder_id),
            fields_updated=list(data.dict(exclude_unset=True).keys())
        )
        
        return {"success": True, "data": dict(reminder)}
    
    async def snooze_reminder(
        self, 
        reminder_id: UUID, 
        user_id: UUID, 
        duration_minutes: int
    ) -> dict:
        """Snooze reminder by adding time to due_at"""
        from datetime import timedelta
        
        existing = await self.db.fetchrow(
            "SELECT * FROM reminders WHERE id = $1 AND user_id = $2",
            reminder_id, user_id
        )
        if not existing:
            return {
                "success": False,
                "error": {"code": "NOT_FOUND", "message": "Reminder not found"}
            }
        
        new_due_utc = existing['due_at_utc'] + timedelta(minutes=duration_minutes)
        
        reminder = await self.db.fetchrow("""
            UPDATE reminders 
            SET due_at_utc = $1, status = 'active', updated_at = NOW()
            WHERE id = $2 AND user_id = $3
            RETURNING *
        """, new_due_utc, reminder_id, user_id)
        
        logger.info(
            "reminder_snoozed",
            user_id=str(user_id),
            reminder_id=str(reminder_id),
            duration_minutes=duration_minutes,
            new_due_at=new_due_utc.isoformat()
        )
        
        return {"success": True, "data": dict(reminder)}
