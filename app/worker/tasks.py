from celery import Celery
from celery.schedules import crontab
import os
import time
import hashlib
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from dateutil import tz
from dateutil.parser import isoparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import structlog
import yaml
from common.db import connect_with_json_codec
from common.embeddings import VECTOR_DIMENSIONS, MODEL_NAME
from common.google_calendar import (
    GoogleCalendarRepository,
    credentials_from_dict,
    credentials_to_dict,
)
from api.metrics import (
    celery_queue_depth,
    document_ingestion_duration_seconds,
    documents_failed_total,
    documents_ingested_total,
    embedding_duration_seconds,
    retention_cleanup_total,
    retention_cleanup_duration_seconds,
)
from api.services.embedding_service import EmbeddingService
from api.services.parsing_service import ParsingService
from api.services.vector_service import VectorService

# --- Setup ---
celery_app = Celery(
    'vib-worker',
    broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://redis:6379/0')
)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)
celery_app.conf.worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", 3))
celery_app.conf.beat_schedule = {
    "cleanup-old-data": {
        "task": "worker.tasks.cleanup_old_data",
        "schedule": crontab(hour=3, minute=0),
    },
    "cleanup-idempotency-keys": {
        "task": "worker.tasks.cleanup_expired_idempotency_keys",
        "schedule": crontab(minute=0),  # Every hour
    },
    "google-calendar-sync": {
        "task": "worker.tasks.schedule_google_calendar_syncs",
        "schedule": crontab(minute="*/15"),
    },
}

logger = structlog.get_logger()
DATABASE_URL = os.getenv("DATABASE_URL")
QDRANT_URL = os.getenv("QDRANT_URL")
embedding_service = EmbeddingService()
_vector_service = None


def get_vector_service() -> VectorService:
    """Lazily instantiate a shared VectorService so the embedding model loads once."""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService(embedding_service)
    return _vector_service

RETENTION_MESSAGES = int(os.getenv("RETENTION_MESSAGES", "90"))
RETENTION_JOBS = int(os.getenv("RETENTION_JOBS", "30"))
RETENTION_NOTIFICATIONS = int(os.getenv("RETENTION_NOTIFICATIONS", "60"))
RETENTION_AUDIT_LOG = int(os.getenv("RETENTION_AUDIT_LOG", "365"))

GOOGLE_SYNC_DEBOUNCE_SECONDS = int(os.getenv("GOOGLE_SYNC_DEBOUNCE_SECONDS", "300"))


async def _connect_db():
    return await connect_with_json_codec(DATABASE_URL)


def _rows_from_command(command_tag: str) -> int:
    try:
        return int(str(command_tag).split()[-1])
    except (ValueError, AttributeError, IndexError):
        return 0


async def _vacuum_tables(tables: list[str]):
    """Run vacuum analyze on tables to reclaim space after cleanup."""
    if not tables:
        return
    # Whitelist of allowed tables to prevent SQL injection
    ALLOWED_TABLES = {
        "messages", "jobs", "notification_delivery", "audit_log",
        "notes", "documents", "chunks", "reminders", "users", "idempotency_keys"
    }
    conn = await _connect_db()
    try:
        await conn.set_autocommit(True)
        for table in tables:
            # Validate table name against whitelist
            if table not in ALLOWED_TABLES:
                logger.warning("vacuum_table_rejected", table=table, reason="not_in_whitelist")
                continue
            try:
                # Use parameterized identifier (safe after whitelist validation)
                await conn.execute(f"VACUUM (ANALYZE) {table};")
                logger.info("vacuum_table_completed", table=table)
            except Exception as exc:
                logger.warning("vacuum_table_failed", table=table, error=str(exc))
    finally:
        await conn.close()

# --- Helper Functions ---
def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def extract_note_id_from_frontmatter(content: str) -> uuid.UUID | None:
    try:
        front_matter = content.split("---")[1]
        data = yaml.safe_load(front_matter)
        if 'id' in data:
            return uuid.UUID(data['id'])
    except (IndexError, yaml.YAMLError, ValueError):
        return None
    return None

def ensure_qdrant_collection(client: QdrantClient):
    """Ensure the Qdrant collection exists with proper error handling."""
    try:
        # Get existing collections
        collections_response = client.get_collections()
        existing_collections = [c.name for c in collections_response.collections]

        logger.info("worker_checking_qdrant_collections", existing=existing_collections)

        # Create collection if it doesn't exist
        if "knowledge_base" not in existing_collections:
            logger.info("worker_creating_qdrant_collection", collection_name="knowledge_base")
            client.create_collection(
                collection_name="knowledge_base",
                vectors_config=VectorParams(
                    size=VECTOR_DIMENSIONS,
                    distance=Distance.COSINE
                )
            )
            logger.info("worker_created_qdrant_collection", collection_name="knowledge_base")
        else:
            logger.info("worker_qdrant_collection_exists", collection_name="knowledge_base")

        # Verify collection exists
        collections_response = client.get_collections()
        existing_collections = [c.name for c in collections_response.collections]
        if "knowledge_base" not in existing_collections:
            logger.error("worker_qdrant_collection_verification_failed", collection_name="knowledge_base")
            raise RuntimeError("Failed to create or verify Qdrant collection")

    except Exception as e:
        logger.error("worker_qdrant_collection_error", error=str(e))
        raise

async def embed_and_upsert_note_async(note_id: uuid.UUID, title: str, body: str, tags: list, md_path: str, user_id: uuid.UUID):
    """Embed note and store in Qdrant"""
    text = f"{title}\n\n{body}"
    logger.info("embedding_note_start", note_id=str(note_id), md_path=md_path)
    with embedding_duration_seconds.labels(source_type="note").time():
        embedding = await embedding_service.embed(text)
    
    client = QdrantClient(url=QDRANT_URL)
    ensure_qdrant_collection(client)
    client.upsert(
        collection_name="knowledge_base",
        points=[{
            "id": str(note_id),
            "vector": embedding,
            "payload": {
                "embedding_model": embedding_service.model_name,
                "content_type": "note",
                "source_id": str(note_id),
                "title": title,
                "tags": tags,
                "md_path": md_path,
                "created_at": datetime.now(timezone.utc).isoformat() + "Z",
                "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
                "embedded_at": datetime.now(timezone.utc).isoformat() + "Z",
                "user_id": str(user_id)
            }
        }]
    )
    logger.info("embedding_note_qdrant_upserted", note_id=str(note_id))

    # Update database in a transaction to ensure atomicity
    conn = await _connect_db()
    try:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO file_sync_state (user_id, file_path, content_hash, last_modified_at, last_embedded_at, embedding_model, vector_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, file_path) DO UPDATE
                SET content_hash = $3, last_embedded_at = $5, vector_id = $7, updated_at = NOW()
            """, user_id, md_path, hash_content(text), datetime.now(timezone.utc), datetime.now(timezone.utc), embedding_service.model_name, str(note_id))
        logger.info("embedding_note_db_upserted", note_id=str(note_id))
    finally:
        await conn.close()

# --- Celery Tasks ---
@celery_app.task(name='worker.tasks.health_check')
def health_check():
    """Simple health check task"""
    return {"status": "ok", "worker": "running"}

@celery_app.task(name='worker.tasks.schedule_embedding_check')
def schedule_embedding_check(filepath):
    """Check if file needs re-embedding after debounce period"""
    async def _async_check():
        relative_path = filepath.replace('/vault/', '')
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            logger.warning("file_watcher_missing_file", path=filepath)
            return
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        conn = await _connect_db()
        try:
            existing = await conn.fetchrow("""
                SELECT content_hash, last_embedded_at 
                FROM file_sync_state 
                WHERE file_path = $1
            """, relative_path)
            
            if not existing or existing['content_hash'] != content_hash:
                logger.info("file_changed_externally", path=relative_path)
                
                note_id = extract_note_id_from_frontmatter(content)
                
                if note_id:
                    embed_note_task.delay(str(note_id))
                else:
                    logger.warning("no_note_id_in_frontmatter", path=relative_path)
        finally:
            await conn.close()
    asyncio.run(_async_check())

@celery_app.task(name='worker.tasks.embed_note_task')
def embed_note_task(note_id_str: str):
    """Background task to embed a note"""
    async def _async_embed():
        note_id = uuid.UUID(note_id_str)
        conn = await _connect_db()
        try:
            note = await conn.fetchrow("SELECT * FROM notes WHERE id = $1", note_id)
            if not note:
                logger.warning("embed_note_task_missing_note", note_id=note_id_str)
                return
            logger.info("embed_note_task_start", note_id=note_id_str, md_path=note['md_path'])
            try:
                await embed_and_upsert_note_async(
                    note['id'], note['title'], note['body'], note['tags'],
                    note['md_path'], note['user_id']
                )
                # Update note timestamp in a transaction
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE notes
                        SET updated_at = NOW()
                        WHERE id = $1
                    """, note_id)
                logger.info("embed_note_task_success", note_id=note_id_str, md_path=note['md_path'])
            except Exception as exc:
                logger.error("embed_note_task_failure", note_id=note_id_str, error=str(exc))
                raise
        finally:
            await conn.close()
    asyncio.run(_async_embed())


@celery_app.task(name='worker.tasks.process_document_ingestion', bind=True, max_retries=3)
def process_document_ingestion(self, job_id: str):
    """Ingest uploaded documents asynchronously."""
    start = time.monotonic()
    document_meta = None
    try:
        result, document_meta = asyncio.run(_process_document(job_id))
        if document_meta:
            duration = time.monotonic() - start
            document_ingestion_duration_seconds.observe(duration)
            documents_ingested_total.labels(
                user_id=str(document_meta["user_id"]),
                mime_type=document_meta.get("mime_type") or "unknown",
            ).inc()
        logger.info("document_ingestion_completed", job_id=job_id)
        return result
    except Exception as exc:
        if document_meta:
            documents_failed_total.labels(
                user_id=str(document_meta["user_id"]),
                mime_type=document_meta.get("mime_type") or "unknown",
                error_type=type(exc).__name__,
            ).inc()
        asyncio.run(_mark_job_failed(job_id, str(exc)))
        logger.error(
            "document_ingestion_failed",
            job_id=job_id,
            error=str(exc),
            retries=self.request.retries,
        )
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        celery_queue_depth.labels(queue_name="document_ingest").dec()


async def _process_document(job_id: str):
    conn = await _connect_db()
    parsing_service = ParsingService()
    vector_service = None
    document_meta = None
    try:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", uuid.UUID(job_id))
        if not job:
            raise ValueError(f"Job {job_id} not found")

        await conn.execute(
            """
            UPDATE jobs
            SET status = 'running', started_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            uuid.UUID(job_id),
        )

        payload = job["payload"] or {}
        document_id = uuid.UUID(payload["document_id"])
        document = await conn.fetchrow(
            "SELECT * FROM documents WHERE id = $1", document_id
        )
        if not document:
            raise ValueError(f"Document {document_id} not found")

        document_meta = dict(document)
        await conn.execute(
            """
            UPDATE documents
            SET status = 'processing', error_message = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            document_id,
        )

        file_path = Path("/app") / document_meta["storage_path"]
        chunks, doc_metadata = await parsing_service.parse_document(
            file_path, document_meta.get("mime_type") or "application/octet-stream"
        )

        chunk_ids = []
        for idx, chunk in enumerate(chunks):
            chunk_id = await conn.fetchval(
                """
                INSERT INTO chunks (document_id, ordinal, text, tokens, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                document_id,
                idx,
                chunk["text"],
                chunk.get("tokens"),
                chunk.get("metadata"),
            )
            chunk_ids.append(chunk_id)

        vector_service = get_vector_service()
        await vector_service.upsert_document_chunks(
            document_id=document_id,
            user_id=document_meta["user_id"],
            chunks=chunks,
            document_title=document_meta["filename"],
        )

        result_payload = {
            "document_id": str(document_id),
            "chunk_count": len(chunk_ids),
            "metadata": doc_metadata,
        }

        # Update document and job status in a transaction to ensure atomicity
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE documents
                SET status = 'indexed', error_message = NULL, updated_at = NOW()
                WHERE id = $1
                """,
                document_id,
            )

            await conn.execute(
                """
                UPDATE jobs
                SET status = 'completed', result = $1, completed_at = NOW(), updated_at = NOW()
                WHERE id = $2
                """,
                result_payload,
                uuid.UUID(job_id),
            )

        return result_payload, document_meta
    finally:
        await conn.close()


async def _mark_job_failed(job_id: str, error_message: str):
    conn = await _connect_db()
    try:
        # Update job and document status in a transaction to ensure atomicity
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error_message = $1,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2
                """,
                error_message,
                uuid.UUID(job_id),
            )

            job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", uuid.UUID(job_id))
            if job and job["payload"]:
                document_id = uuid.UUID(job["payload"]["document_id"])
                await conn.execute(
                    """
                    UPDATE documents
                    SET status = 'failed', error_message = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    error_message,
                    document_id,
                )
    finally:
        await conn.close()


@celery_app.task(name="worker.tasks.cleanup_old_data")
def cleanup_old_data():
    """Celery task scheduled nightly to enforce retention policies."""
    return asyncio.run(_cleanup_old_data_async())


async def _cleanup_old_data_async():
    start = time.monotonic()
    conn = await _connect_db()
    results: dict[str, int] = {}
    # Whitelist of allowed tables for cleanup to prevent SQL injection
    ALLOWED_CLEANUP_TABLES = {
        "messages", "jobs", "notification_delivery", "audit_log"
    }
    try:
        policies = [
            ("messages", RETENTION_MESSAGES),
            ("jobs", RETENTION_JOBS),
            ("notification_delivery", RETENTION_NOTIFICATIONS),
            ("audit_log", RETENTION_AUDIT_LOG),
        ]
        for table, retention_days in policies:
            # Validate table name against whitelist
            if table not in ALLOWED_CLEANUP_TABLES:
                logger.warning("cleanup_table_rejected", table=table, reason="not_in_whitelist")
                continue
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            command = await conn.execute(
                f"DELETE FROM {table} WHERE created_at < $1",
                cutoff,
            )
            deleted = _rows_from_command(command)
            results[table] = deleted
            retention_cleanup_total.labels(table=table).inc(deleted)
            logger.info(
                "retention_cleanup_table",
                table=table,
                deleted=deleted,
                cutoff=cutoff.isoformat(),
            )
    finally:
        await conn.close()

    duration = time.monotonic() - start
    retention_cleanup_duration_seconds.observe(duration)
    logger.info(
        "retention_cleanup_complete",
        duration_seconds=duration,
        results=results,
    )
    tables_to_vacuum = [table for table, count in results.items() if count > 0]
    await _vacuum_tables(tables_to_vacuum)
    return results


# --- File Watcher ---
class VaultWatcher(FileSystemEventHandler):
    def __init__(self, debounce_seconds=5):
        self.debounce_seconds = debounce_seconds
        self.pending_changes = {}
    
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return
        
        filepath = event.src_path
        self.pending_changes[filepath] = time.time()
        
        schedule_embedding_check.apply_async(
            args=[filepath],
            countdown=self.debounce_seconds
        )

def start_file_watcher():
    path = "/vault"
    event_handler = VaultWatcher()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info("file_watcher_started", path=path)
    # The observer runs in a background thread, so we don't need to block here.
    # The main Celery process will keep the script alive.

@celery_app.task(name="worker.tasks.cleanup_expired_idempotency_keys")
def cleanup_expired_idempotency_keys():
    """
    Delete idempotency keys older than 24 hours.
    Runs every hour via Celery Beat.
    """
    return asyncio.run(_cleanup_expired_idempotency_keys_async())


async def _cleanup_expired_idempotency_keys_async():
    """Clean up expired idempotency keys from the database."""
    start = time.monotonic()
    conn = await _connect_db()
    try:
        command = await conn.execute("""
            DELETE FROM idempotency_keys
            WHERE expires_at < NOW()
        """)
        deleted = _rows_from_command(command)

        duration = time.monotonic() - start
        logger.info(
            "idempotency_cleanup_completed",
            deleted_count=deleted,
            duration_seconds=duration
        )

        # Vacuum table if significant deletions
        if deleted > 100:
            await _vacuum_tables(["idempotency_keys"])

        return {"deleted": deleted, "duration_seconds": duration}
    except Exception as exc:
        logger.error("idempotency_cleanup_failed", error=str(exc))
        raise
    finally:
        await conn.close()


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure periodic tasks - called when Celery app is configured"""
    logger.info("periodic_tasks_configured")

# Use worker_ready signal for more reliable file watcher startup
from celery.signals import worker_ready

@worker_ready.connect
def start_file_watcher_on_worker_ready(sender, **kwargs):
    """Start file watcher when Celery worker is fully ready"""
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    logger.info("file_watcher_thread_started_from_worker_ready")


async def _load_google_credentials(
    repo: GoogleCalendarRepository,
    user_id: uuid.UUID,
) -> Optional[Credentials]:
    creds_data = await repo.get_credentials(user_id)
    if not creds_data:
        return None

    credentials = credentials_from_dict(creds_data)
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            await repo.save_credentials(user_id, credentials_to_dict(credentials))
        except Exception as exc:  # pragma: no cover - network dependency
            logger.error(
                "google_credentials_refresh_failed",
                user_id=str(user_id),
                error=str(exc),
            )
            return None
    return credentials


async def _ensure_vib_calendar(service, repo: GoogleCalendarRepository, user_id: uuid.UUID) -> Optional[str]:
    sync_state = await repo.get_sync_state(user_id)
    if sync_state and sync_state.get("google_calendar_id"):
        return sync_state["google_calendar_id"]

    calendars = service.calendarList().list().execute()
    for calendar in calendars.get("items", []):
        if calendar.get("summary") == "VIB":
            calendar_id = calendar.get("id")
            await repo.update_sync_state(user_id, google_calendar_id=calendar_id)
            return calendar_id

    calendar_body = {
        "summary": "VIB",
        "description": "Events synced from VIB",
        "timeZone": "UTC",
    }
    created = service.calendars().insert(body=calendar_body).execute()
    calendar_id = created.get("id")
    await repo.update_sync_state(user_id, google_calendar_id=calendar_id)
    logger.info("google_calendar_created", user_id=str(user_id), calendar_id=calendar_id)
    return calendar_id


def _to_google_event_format(event: dict) -> dict[str, Any]:
    timezone_name = event.get("timezone") or "UTC"
    starts_at = event.get("starts_at")
    ends_at = event.get("ends_at") or (
        (starts_at + timedelta(hours=1)) if starts_at else None
    )
    body: dict[str, Any] = {
        "summary": event.get("title") or "Untitled event",
        "description": event.get("description") or "",
        "start": {
            "dateTime": starts_at.isoformat() if starts_at else None,
            "timeZone": timezone_name,
        },
        "end": {
            "dateTime": ends_at.isoformat() if ends_at else None,
            "timeZone": timezone_name,
        },
        "status": event.get("status", "confirmed"),
    }
    if event.get("location_text"):
        body["location"] = event["location_text"]
    if event.get("rrule"):
        body["recurrence"] = [f"RRULE:{event['rrule']}"]
    return body


def _parse_google_datetime(value: Optional[str], timezone_hint: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    dt = isoparse(value)
    if dt.tzinfo is None:
        tzinfo = tz.gettz(timezone_hint or "UTC")
        dt = dt.replace(tzinfo=tzinfo)
    return dt


def _parse_google_recurrence(recurrence: Optional[list[str]]) -> Optional[str]:
    if not recurrence:
        return None
    for rule in recurrence:
        if rule.startswith("RRULE:"):
            return rule[6:]
    return None


def _from_google_event_format(
    google_event: dict,
    user_id: uuid.UUID,
    calendar_id: str,
) -> dict[str, Any]:
    start_info = google_event.get("start", {})
    end_info = google_event.get("end", {})
    start_value = start_info.get("dateTime") or start_info.get("date")
    end_value = end_info.get("dateTime") or end_info.get("date")
    timezone_hint = start_info.get("timeZone") or end_info.get("timeZone") or "UTC"

    starts_at = _parse_google_datetime(start_value, timezone_hint)
    ends_at = _parse_google_datetime(end_value, timezone_hint)

    return {
        "user_id": user_id,
        "title": google_event.get("summary") or "Untitled event",
        "description": google_event.get("description"),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "timezone": timezone_hint,
        "location_text": google_event.get("location"),
        "rrule": _parse_google_recurrence(google_event.get("recurrence")),
        "source": "google",
        "google_event_id": google_event.get("id"),
        "google_calendar_id": calendar_id,
        "status": google_event.get("status", "confirmed"),
    }


async def _process_google_event(
    repo: GoogleCalendarRepository,
    user_id: uuid.UUID,
    google_event: dict,
    calendar_id: str,
):
    google_event_id = google_event.get("id")
    status = google_event.get("status", "confirmed")
    existing = await repo.get_event_by_google_id(google_event_id)

    if status == "cancelled":
        if existing:
            await repo.update_event_fields(existing["id"], {"status": "cancelled"})
            logger.info("google_event_cancelled_locally", event_id=str(existing["id"]))
        return

    payload = _from_google_event_format(google_event, user_id, calendar_id)

    if not existing:
        created = await repo.create_google_event(payload)
        logger.info("google_event_imported", event_id=str(created["id"]))
        return

    updates = payload.copy()
    updates.pop("user_id", None)
    if existing.get("source") != "google":
        updates.pop("source", None)
        updated_value = google_event.get("updated")
        if updated_value:
            google_updated = _parse_google_datetime(updated_value, payload.get("timezone"))
            local_updated = existing.get("updated_at")
            if google_updated and local_updated and google_updated <= local_updated:
                logger.info(
                    "google_event_conflict_skipped",
                    event_id=str(existing["id"]),
                )
                return

    await repo.update_event_fields(existing["id"], updates)
    logger.info("google_event_updated_locally", event_id=str(existing["id"]))


@celery_app.task(name="worker.tasks.schedule_google_calendar_syncs")
def schedule_google_calendar_syncs():
    async def _schedule():
        conn = await _connect_db()
        try:
            repo = GoogleCalendarRepository(conn)
            rows = await repo.list_users_with_sync()
            now = datetime.now(timezone.utc)
            for row in rows:
                user_id = row.get("user_id")
                if not user_id:
                    continue
                last_sync_at = row.get("last_sync_at")
                if last_sync_at and (now - last_sync_at).total_seconds() < GOOGLE_SYNC_DEBOUNCE_SECONDS:
                    continue
                sync_google_calendar_push.delay(str(user_id))
                if row.get("sync_direction") == "two_way":
                    sync_google_calendar_pull.delay(str(user_id))
        finally:
            await conn.close()

    asyncio.run(_schedule())


@celery_app.task(name="worker.tasks.sync_google_calendar_push")
def sync_google_calendar_push(user_id_str: str):
    async def _run():
        user_id = uuid.UUID(user_id_str)
        conn = await _connect_db()
        try:
            repo = GoogleCalendarRepository(conn)
            credentials = await _load_google_credentials(repo, user_id)
            if not credentials:
                logger.warning("google_sync_missing_credentials", user_id=user_id_str)
                return

            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
            calendar_id = await _ensure_vib_calendar(service, repo, user_id)
            if not calendar_id:
                logger.warning("google_sync_no_calendar", user_id=user_id_str)
                return

            events = await repo.list_events_for_sync(user_id, "internal")
            synced = 0
            errors = 0
            for event in events:
                try:
                    if event.get("status") == "cancelled" and event.get("google_event_id"):
                        try:
                            service.events().delete(
                                calendarId=calendar_id,
                                eventId=event["google_event_id"],
                            ).execute()
                        except HttpError as exc:
                            if exc.resp.status != 404:
                                raise
                        await repo.update_event_fields(event["id"], {
                            "google_event_id": None,
                            "google_calendar_id": calendar_id,
                        })
                        synced += 1
                        continue

                    if event.get("status") == "cancelled":
                        continue

                    google_body = _to_google_event_format(event)
                    if not event.get("google_event_id"):
                        created = service.events().insert(
                            calendarId=calendar_id,
                            body=google_body,
                        ).execute()
                        await repo.update_event_fields(event["id"], {
                            "google_event_id": created.get("id"),
                            "google_calendar_id": calendar_id,
                        })
                        synced += 1
                    else:
                        service.events().update(
                            calendarId=calendar_id,
                            eventId=event["google_event_id"],
                            body=google_body,
                        ).execute()
                        await repo.update_event_fields(event["id"], {
                            "google_calendar_id": calendar_id,
                        })
                        synced += 1
                except HttpError as exc:
                    errors += 1
                    logger.error(
                        "google_sync_push_http_error",
                        user_id=user_id_str,
                        event_id=str(event["id"]),
                        error=str(exc),
                    )
                except Exception as exc:
                    errors += 1
                    logger.error(
                        "google_sync_push_error",
                        user_id=user_id_str,
                        event_id=str(event["id"]),
                        error=str(exc),
                    )

            await repo.update_sync_state(user_id, last_sync_at=datetime.now(timezone.utc))
            await repo.save_credentials(user_id, credentials_to_dict(credentials))
            logger.info(
                "google_sync_push_completed",
                user_id=user_id_str,
                synced=synced,
                errors=errors,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@celery_app.task(name="worker.tasks.sync_google_calendar_pull")
def sync_google_calendar_pull(user_id_str: str):
    async def _run():
        user_id = uuid.UUID(user_id_str)
        conn = await _connect_db()
        try:
            repo = GoogleCalendarRepository(conn)
            sync_state = await repo.get_sync_state(user_id)
            if not sync_state or sync_state.get("sync_direction") != "two_way":
                return

            credentials = await _load_google_credentials(repo, user_id)
            if not credentials:
                logger.warning("google_sync_missing_credentials", user_id=user_id_str)
                return

            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
            calendar_id = await _ensure_vib_calendar(service, repo, user_id)
            if not calendar_id:
                logger.warning("google_sync_no_calendar", user_id=user_id_str)
                return

            sync_token = sync_state.get("sync_token")
            events_processed = 0
            page_token = None

            while True:
                list_kwargs = {
                    "calendarId": calendar_id,
                    "showDeleted": True,
                }
                if sync_token:
                    list_kwargs["syncToken"] = sync_token
                else:
                    list_kwargs["maxResults"] = 250
                if page_token:
                    list_kwargs["pageToken"] = page_token

                response = service.events().list(**list_kwargs).execute()
                events = response.get("items", [])
                for google_event in events:
                    await _process_google_event(repo, user_id, google_event, calendar_id)
                events_processed += len(events)

                page_token = response.get("nextPageToken")
                if page_token:
                    continue
                sync_token = response.get("nextSyncToken", sync_token)
                break

            await repo.update_sync_state(
                user_id,
                sync_token=sync_token,
                last_sync_at=datetime.now(timezone.utc),
            )
            await repo.save_credentials(user_id, credentials_to_dict(credentials))
            logger.info(
                "google_sync_pull_completed",
                user_id=user_id_str,
                events_processed=events_processed,
            )
        except HttpError as exc:
            if exc.resp.status == 410:  # Sync token expired
                await repo.update_sync_state(user_id, sync_token=None)
                logger.warning("google_sync_pull_token_expired", user_id=user_id_str)
            else:
                logger.error(
                    "google_sync_pull_http_error",
                    user_id=user_id_str,
                    error=str(exc),
                )
        except Exception as exc:
            logger.error(
                "google_sync_pull_error",
                user_id=user_id_str,
                error=str(exc),
            )
        finally:
            await conn.close()

    asyncio.run(_run())
