from celery import Celery
from celery.schedules import crontab
import os
import time
import hashlib
import uuid
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import structlog
import yaml
from common.db import connect_with_json_codec
from common.embeddings import VECTOR_DIMENSIONS, MODEL_NAME
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
    }
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
    conn = await _connect_db()
    try:
        await conn.set_autocommit(True)
        for table in tables:
            try:
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
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "embedded_at": datetime.utcnow().isoformat() + "Z",
                "user_id": str(user_id)
            }
        }]
    )
    logger.info("embedding_note_qdrant_upserted", note_id=str(note_id))
    
    conn = await _connect_db()
    try:
        await conn.execute("""
            INSERT INTO file_sync_state (user_id, file_path, content_hash, last_modified_at, last_embedded_at, embedding_model, vector_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id, file_path) DO UPDATE
            SET content_hash = $3, last_embedded_at = $5, vector_id = $7, updated_at = NOW()
        """, user_id, md_path, hash_content(text), datetime.utcnow(), datetime.utcnow(), embedding_service.model_name, str(note_id))
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
    try:
        policies = [
            ("messages", RETENTION_MESSAGES),
            ("jobs", RETENTION_JOBS),
            ("notification_delivery", RETENTION_NOTIFICATIONS),
            ("audit_log", RETENTION_AUDIT_LOG),
        ]
        for table, retention_days in policies:
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
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
    def __init__(self, debounce_seconds=30):
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

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Start the file watcher in a background thread
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
