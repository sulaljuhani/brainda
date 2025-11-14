import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import structlog
import os
import time
import uuid
import re
import asyncpg
from asyncpg.exceptions import UniqueViolationError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from starlette.middleware.base import BaseHTTPMiddleware
from common.embeddings import generate_embedding, VECTOR_DIMENSIONS, MODEL_NAME
from common.db import connect_with_json_codec

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(message)s",
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

from contextlib import asynccontextmanager
from worker.scheduler import start_scheduler, sync_scheduled_reminders
from common.migrations import run_migrations
from api.task_queue import get_celery_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # CRITICAL: Run migrations first, before any code that depends on DB schema
    logger.info("running_database_migrations")
    await run_migrations(DATABASE_URL)

    # Now it's safe to start services that depend on the full schema
    start_scheduler()
    await sync_scheduled_reminders()
    await ensure_qdrant_collection()
    yield
    # Shutdown (if needed)

app = FastAPI(title="VIB API", version="1.0.0", lifespan=lifespan)

# --- Database and Model Setup ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Celery client ---
celery_client = get_celery_client()

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        status_code = "500"
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception:
            raise
        finally:
            duration = time.perf_counter() - start
            route = request.scope.get("route")
            endpoint = getattr(route, "path", request.url.path)
            api_request_duration_seconds.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
            ).observe(duration)

from api.adapters.llm_adapter import get_llm_adapter
from api.dependencies import get_db, get_current_user
from api.metrics import (
    api_request_duration_seconds,
    celery_queue_depth,
    chat_turns_total,
    get_content_type,
    get_metrics,
    retention_cleanup_total,
    notes_created_total,
    notes_deduped_total,
    postgres_connections,
    qdrant_points_count,
    redis_memory_bytes,
    tool_calls_total,
)
from api.models.reminder import ReminderCreate
from api.services.rag_service import RAGService
from api.services.reminder_service import ReminderService
from api.services.vector_service import VectorService
from api.tools.calendar import CALENDAR_TOOLS, execute_calendar_tool
from api.tools.reminder_tools import REMINDER_TOOLS, execute_reminder_tool


class SlidingWindowRateLimiter:
    """Simple in-memory sliding window limiter for lightweight protection."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> tuple[bool, Optional[int]]:
        now = time.monotonic()
        async with self._lock:
            window = self._events[key]
            while window and now - window[0] > self.window_seconds:
                window.popleft()
            if len(window) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - window[0])))
                return False, retry_after
            window.append(now)
            return True, None


CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "30"))
CHAT_RATE_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))
DEFAULT_CHAT_TIMEZONE = os.getenv("CHAT_DEFAULT_TIMEZONE", "UTC")

chat_rate_limiter = SlidingWindowRateLimiter(
    CHAT_RATE_LIMIT,
    CHAT_RATE_WINDOW_SECONDS,
)

def generate_markdown_filename(title: str, vault_path: str) -> str:
    """Generate unique filename from title"""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    
    filepath = os.path.join(vault_path, "notes", f"{slug}.md")
    if os.path.exists(filepath):
        short_uuid = str(uuid.uuid4())[:8]
        slug = f"{slug}-{short_uuid}"
    
    return f"notes/{slug}.md"

def create_markdown_file(note_id: uuid.UUID, title: str, body: str, tags: list, md_path: str):
    """Creates a markdown file with YAML front-matter."""
    vault_path = "/vault"
    full_path = os.path.join(vault_path, md_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    tags_yaml = f"[{', '.join(tags)}]" if tags else "[]"

    content = f"""---
id: {note_id}
title: {title}
tags: {tags_yaml}
created: {datetime.now(timezone.utc).isoformat()}Z
updated: {datetime.now(timezone.utc).isoformat()}Z
---

# {title}

{body}
"""
    with open(full_path, "w") as f:
        f.write(content)

def update_markdown_file(note: dict):
    """Updates an existing markdown file."""
    vault_path = "/vault"
    full_path = os.path.join(vault_path, note['md_path'])
    
    tags_yaml = f"[{', '.join(note['tags'])}]" if note['tags'] else "[]"
    
    content = f"""---
id: {note['id']}
title: {note['title']}
tags: {tags_yaml}
created: {note['created_at'].isoformat()}Z
updated: {datetime.now(timezone.utc).isoformat()}Z
---

# {note['title']}

{note['body']}
"""
    with open(full_path, "w") as f:
        f.write(content)


async def create_note_record(
    user_id: uuid.UUID,
    note: "NoteCreateRequest",
    db: asyncpg.Connection,
) -> dict:
    """Core note creation logic shared between HTTP endpoints and chat actions.
    Idempotency is handled by middleware."""
    try:
        md_path = generate_markdown_filename(note.title, "/vault")
        try:
            inserted_note = await db.fetchrow(
                """
                INSERT INTO notes (user_id, title, body, tags, md_path)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, title, md_path, created_at
                """,
                user_id,
                note.title,
                note.body,
                note.tags,
                md_path,
            )

            # Increment metric immediately after successful DB insert
            # This ensures the metric reflects notes created in the database,
            # even if subsequent operations (markdown file, embedding) fail
            notes_created_total.labels(user_id=str(user_id)).inc()

            create_markdown_file(
                inserted_note["id"],
                note.title,
                note.body,
                note.tags,
                md_path,
            )
            await queue_embedding_task(inserted_note["id"])

            logger.info(
                "create_note_endpoint_success",
                note_id=str(inserted_note["id"]),
            )
            return {
                "success": True,
                "data": {
                    "id": str(inserted_note["id"]),
                    "title": inserted_note["title"],
                    "md_path": inserted_note["md_path"],
                    "created_at": inserted_note["created_at"].isoformat() + "Z",
                },
            }
        except UniqueViolationError:
            # DB constraint caught a duplicate - this is a safety net
            # Primary duplicate prevention is handled by idempotency middleware
            logger.warning(
                "duplicate_note_prevented_by_constraint",
                title=note.title,
            )
            existing = await db.fetchrow(
                """
                SELECT id, title, md_path, created_at
                FROM notes
                WHERE user_id = $1 AND lower(title) = lower($2)
                ORDER BY created_at DESC LIMIT 1
                """,
                user_id,
                note.title,
            )
            # Count deduplicated creations toward created metric to reflect
            # user-visible successful note creation semantics in metrics.
            # This avoids flakiness when tests or clients attempt to create a
            # note with a title that already exists for the user.
            notes_deduped_total.labels(user_id=str(user_id)).inc()
            notes_created_total.labels(user_id=str(user_id)).inc()
            return {
                "success": True,
                "deduplicated": True,
                "message": f"Note with title '{note.title}' already exists",
                "data": {
                    "id": str(existing["id"]),
                    "title": existing["title"],
                    "md_path": existing["md_path"],
                    "created_at": existing["created_at"].isoformat() + "Z",
                },
            }
    except Exception as exc:
        logger.error("create_note_record_failed", error=str(exc))
        raise

async def queue_embedding_task(note_id: uuid.UUID):
    """Dispatches a task to the Celery worker to embed the note."""
    logger.info("queuing_embedding_task", note_id=str(note_id))
    celery_client.send_task('worker.tasks.embed_note_task', args=[str(note_id)])

async def ensure_qdrant_collection():
    """Ensure the Qdrant collection exists with retry logic."""
    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            client = QdrantClient(url=os.getenv("QDRANT_URL"))

            # Get existing collections
            collections_response = client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]

            logger.info(
                "checking_qdrant_collections",
                existing=existing_collections,
                attempt=attempt + 1
            )

            # Create collection if it doesn't exist
            if "knowledge_base" not in existing_collections:
                logger.info("creating_qdrant_collection", collection_name="knowledge_base")
                client.create_collection(
                    collection_name="knowledge_base",
                    vectors_config=VectorParams(
                        size=VECTOR_DIMENSIONS,
                        distance=Distance.COSINE
                    )
                )
                logger.info("created_qdrant_collection", collection_name="knowledge_base")
            else:
                logger.info("qdrant_collection_exists", collection_name="knowledge_base")

            # Verify collection was created
            collections_response = client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]
            if "knowledge_base" in existing_collections:
                logger.info("qdrant_collection_verified", collection_name="knowledge_base")
                return
            else:
                logger.warning(
                    "qdrant_collection_not_verified",
                    collection_name="knowledge_base",
                    attempt=attempt + 1
                )

        except Exception as e:
            logger.error(
                "qdrant_collection_creation_failed",
                error=str(e),
                attempt=attempt + 1,
                max_retries=max_retries
            )
            if attempt < max_retries - 1:
                logger.info("retrying_qdrant_collection", delay=retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("qdrant_collection_creation_exhausted", max_retries=max_retries)
                raise

# Metrics middleware (must run before other middleware to capture timings)
app.add_middleware(MetricsMiddleware)

# Idempotency middleware (ensures exactly-once semantics for state-changing operations)
# NOTE: Must be added AFTER auth middleware so that user_id is available
from api.middleware import AuthMiddleware, IdempotencyMiddleware
app.add_middleware(IdempotencyMiddleware)

# Auth middleware (extracts user_id from token and sets in request.state)
# NOTE: Must be added LAST (runs first) so user_id is set before other middleware
app.add_middleware(AuthMiddleware)

# CORS - Secure configuration using environment variables
# CRITICAL: Never use allow_origins=["*"] with allow_credentials=True
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
# Clean up whitespace from origins
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS]

logger.info("cors_configuration", allowed_origins=CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Specific origins only, configured via environment
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Idempotency-Key"],
    expose_headers=["X-Idempotency-Replay"],
)


# Health check
@app.get("/api/v1/health")
async def health_check():
    """Check health of all services quickly with timeboxed, concurrent checks."""
    import redis
    import httpx

    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "services": {},
    }

    async def check_postgres():
        logger.info("checking_postgres")
        conn = None
        try:
            conn = await connect_with_json_codec(os.getenv("DATABASE_URL"))
            await conn.execute("SELECT 1")
            pg_conns = await conn.fetchval("SELECT COUNT(*) FROM pg_stat_activity")
            postgres_connections.set(int(pg_conns))
            health["services"]["postgres"] = "ok"
            logger.info("postgres_ok")
        except Exception as e:
            health["services"]["postgres"] = "error"
            health["status"] = "unhealthy"
            logger.error("postgres_health_check_failed", error=str(e))
        finally:
            if conn:
                await conn.close()

    async def check_redis():
        logger.info("checking_redis")
        r = None
        try:
            r = redis.from_url(os.getenv("REDIS_URL"))
            r.ping()
            celery_queue_depth.labels(queue_name="celery").set(r.llen("celery"))
            celery_queue_depth.labels(queue_name="document_ingest").set(r.llen("document_ingest"))
            redis_info = r.info("memory")
            redis_memory_bytes.set(int(redis_info.get("used_memory", 0)))
            health["services"]["redis"] = "ok"
            logger.info("redis_ok")
        except Exception as e:
            health["services"]["redis"] = "error"
            health["status"] = "unhealthy"
            logger.error("redis_health_check_failed", error=str(e))
        finally:
            if r:
                try:
                    r.close()
                except Exception:
                    pass

    async def check_qdrant():
        logger.info("checking_qdrant")
        try:
            timeout = httpx.Timeout(2.0, connect=2.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                base = os.getenv("QDRANT_URL")
                resp = await client.get(f"{base}/collections")
                if resp.status_code == 200:
                    health["services"]["qdrant"] = "ok"
                    logger.info("qdrant_ok")
                    collection_name = os.getenv("QDRANT_COLLECTION", "knowledge_base")
                    try:
                        details = await client.get(f"{base}/collections/{collection_name}")
                        if details.status_code == 200:
                            data = details.json()
                            points_count = 0
                            if isinstance(data, dict):
                                result = data.get("result", {})
                                points_count = int(result.get("points_count", 0) or 0)
                            qdrant_points_count.labels(collection_name=collection_name).set(points_count)
                    except Exception as err:
                        logger.warning("qdrant_points_count_update_failed", error=str(err))
                else:
                    health["services"]["qdrant"] = "error"
                    health["status"] = "unhealthy"
                    logger.error("qdrant_health_check_failed", status_code=resp.status_code)
        except Exception as e:
            health["services"]["qdrant"] = "error"
            health["status"] = "unhealthy"
            logger.error("qdrant_health_check_failed", error=str(e))

    async def check_celery():
        logger.info("checking_celery")
        from celery import Celery

        celery_app = None
        try:
            celery_app = Celery(broker=os.getenv("REDIS_URL"))
            # Use a fast ping instead of heavy stats call
            def _ping():
                try:
                    return celery_app.control.ping(timeout=2.0)
                except Exception:
                    return None

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _ping)
            if result:
                health["services"]["celery_worker"] = "ok"
                logger.info("celery_ok")
            else:
                health["services"]["celery_worker"] = "no_workers"
                health["status"] = "degraded"
                logger.warning("celery_no_workers")
        except Exception as e:
            health["services"]["celery_worker"] = "error"
            logger.error("celery_health_check_failed", error=str(e))
        finally:
            if celery_app:
                try:
                    celery_app.close()
                except Exception:
                    pass

    # Run checks concurrently to minimize latency
    await asyncio.gather(
        check_postgres(),
        check_redis(),
        check_qdrant(),
        check_celery(),
        return_exceptions=True,
    )

    status_code = 200 if health["status"] == "healthy" else 503
    return health

# Version endpoint
@app.get("/api/v1/version")
async def version():
    return {
        "version": "1.0.0",
        "stage": "8",
        "description": "Multi-user authentication with passkeys and TOTP"
    }

# Metrics endpoint (Prometheus format)
@app.get("/api/v1/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=get_metrics(), media_type=get_content_type())

# Protected endpoint example
@app.get("/api/v1/protected")
async def protected_endpoint(user_id: uuid.UUID = Depends(get_current_user)):
    logger.info("protected_endpoint_accessed", user_id=str(user_id))
    return {
        "message": "Access granted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user_id),
    }

# --- API Router ---
router = APIRouter(prefix="/api/v1")


class NoteCreateRequest(BaseModel):
    title: str
    body: str
    tags: list[str] = []

class NoteUpdateRequest(BaseModel):
    body: Optional[str] = None
    tags: Optional[list[str]] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    mode: str
    message: str
    conversation_id: Optional[uuid.UUID] = None
    data: Optional[Dict[str, Any]] = None
    citations: Optional[list[Dict[str, Any]]] = None


def _parse_note_command(message: str) -> tuple[str, str]:
    title_match = re.search(
        r"note titled (.+?)(?: with|$)",
        message,
        re.IGNORECASE,
    )
    body_match = re.search(r"with body (.+)", message, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip(' "\'')
    else:
        title = f"Chat Note {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    body = body_match.group(1).strip() if body_match else message.strip()
    return title or "Chat Note", body


def _extract_search_query(message: str) -> str:
    match = re.search(
        r"search(?: my| the)?(?: notes| documents| files)?(?: for)? (.+)",
        message,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip().rstrip(".!?")
    return message.strip()


def _build_reminder_request(message: str) -> ReminderCreate:
    normalized = message.strip()
    lower = normalized.lower()
    now = datetime.now(timezone.utc)
    due_at = now + timedelta(hours=1)

    if "tomorrow" in lower:
        tomorrow = (now + timedelta(days=1)).date()
        due_at = datetime.combine(tomorrow, datetime.min.time()).replace(
            tzinfo=timezone.utc
        ) + timedelta(hours=9)
    else:
        match = re.search(
            r"in (\d+)\s*(minute|minutes|hour|hours)",
            lower,
        )
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            delta = timedelta(minutes=amount) if "minute" in unit else timedelta(
                hours=amount
            )
            due_at = now + delta

    title_match = re.search(r"remind me(?: .*?)? to (.+)", normalized, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip().rstrip(".!?")
    else:
        title = normalized

    due_at = due_at.astimezone(timezone.utc)
    due_local = due_at.time().replace(microsecond=0)

    return ReminderCreate(
        title=title or "Reminder",
        body=normalized,
        due_at_utc=due_at,
        due_at_local=due_local,
        timezone=DEFAULT_CHAT_TIMEZONE,
    )


async def _handle_note_chat(
    message: str,
    user_id: uuid.UUID,
    db: asyncpg.Connection,
) -> Dict[str, Any]:
    title, body = _parse_note_command(message)
    payload = NoteCreateRequest(title=title, body=body, tags=[])
    result = await create_note_record(user_id, payload, db)
    status = "success" if result.get("success") else "error"
    tool_calls_total.labels("note_create", status).inc()
    return {
        "mode": "note",
        "message": f"Note '{payload.title}' created",
        "data": result.get("data"),
    }


async def _handle_search_chat(message: str, user_id: uuid.UUID) -> Dict[str, Any]:
    query = _extract_search_query(message)
    vector_service = VectorService()
    results = await vector_service.search(
        query=query,
        user_id=user_id,
        limit=5,
    )
    tool_calls_total.labels("semantic_search", "success").inc()
    return {
        "mode": "search",
        "message": f"Search results for '{query}'",
        "data": {"query": query, "results": results, "total": len(results)},
    }


async def _handle_reminder_chat(
    message: str,
    user_id: uuid.UUID,
    db: asyncpg.Connection,
) -> Dict[str, Any]:
    reminder_service = ReminderService(db)
    reminder_payload = _build_reminder_request(message)
    result = await reminder_service.create_reminder(user_id, reminder_payload)
    status = "success" if result.get("success") else "error"
    tool_calls_total.labels("reminder_create", status).inc()
    reminder = result.get("data", {})
    due_at = reminder.get("due_at_utc")
    return {
        "mode": "reminder",
        "message": f"Reminder scheduled for {due_at}" if due_at else "Reminder processed",
        "data": reminder,
    }


async def _handle_rag_chat(message: str, user_id: uuid.UUID) -> Dict[str, Any]:
    try:
        vector_service = VectorService()
        rag_service = RAGService(vector_service, get_llm_adapter())
        answer = await rag_service.answer_question(message, user_id)
        tool_calls_total.labels("rag_answer", "success").inc()
        return {
            "mode": "rag",
            "message": answer.get("answer", "No response available."),
            "data": {"sources_used": answer.get("sources_used", 0)},
            "citations": answer.get("citations", []),
        }
    except Exception as exc:
        logger.exception("rag_chat_failed", error=str(exc), user_id=str(user_id))
        tool_calls_total.labels("rag_answer", "error").inc()
        return {
            "mode": "rag",
            "message": f"I encountered an error while processing your request: {str(exc)}",
            "data": {"error": str(exc), "sources_used": 0},
            "citations": [],
        }


async def _dispatch_chat(
    message: str,
    user_id: uuid.UUID,
    db: asyncpg.Connection,
) -> Dict[str, Any]:
    """
    Dispatch chat using LLM tool calling.
    The LLM decides whether to use tools or provide a direct response.
    """
    # Combine all available tools
    all_tools = CALENDAR_TOOLS + REMINDER_TOOLS

    # Get LLM adapter
    llm_adapter = get_llm_adapter()

    # System prompt to guide the LLM
    system_prompt = """You are a helpful assistant with access to calendar and task management tools.

When the user asks to create events, reminders, or tasks, use the appropriate tools.
- For calendar events (meetings, appointments): use create_calendar_event
- For one-time tasks or reminders: use create_reminder
- For recurring tasks: use create_reminder with repeat_rrule parameter

Always infer reasonable defaults for missing information:
- If no time is specified, use a sensible default based on context
- Use the user's timezone (default to UTC if unknown)
- For recurring tasks, construct proper RRULE strings

Be conversational and confirm what you've done."""

    try:
        # Call LLM with tools
        response = await llm_adapter.complete_with_tools(
            prompt=message,
            tools=all_tools,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        # Check if LLM wants to use tools
        if response.get("type") == "tool_calls":
            tool_calls = response.get("tool_calls", [])

            # Execute tools and collect results
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})

                logger.info(
                    "executing_tool",
                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=str(user_id),
                )

                # Execute the appropriate tool
                if tool_name in ["create_calendar_event", "update_calendar_event", "delete_calendar_event", "list_calendar_events", "link_reminder_to_event"]:
                    result = await execute_calendar_tool(tool_name, arguments, user_id, db)
                elif tool_name in ["create_reminder", "list_reminders", "snooze_reminder"]:
                    result = await execute_reminder_tool(tool_name, arguments, user_id, db)
                else:
                    result = {
                        "success": False,
                        "error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"}
                    }

                tool_results.append({
                    "tool_name": tool_name,
                    "result": result,
                })

            # Generate a user-friendly response based on tool results
            if tool_results:
                first_result = tool_results[0]
                tool_name = first_result["tool_name"]
                result = first_result["result"]

                if result.get("success"):
                    data = result.get("data", {})

                    if tool_name == "create_calendar_event":
                        return {
                            "mode": "tool_success",
                            "message": f"Calendar event '{data.get('title', 'Untitled')}' created successfully.",
                            "data": data,
                        }
                    elif tool_name == "create_reminder":
                        return {
                            "mode": "tool_success",
                            "message": f"Task '{data.get('title', 'Untitled')}' created successfully.",
                            "data": data,
                        }
                    elif tool_name == "list_calendar_events":
                        events = data if isinstance(data, list) else result.get("data", [])
                        return {
                            "mode": "tool_success",
                            "message": f"Found {len(events)} calendar event(s).",
                            "data": {"events": events},
                        }
                    elif tool_name == "list_reminders":
                        reminders = result.get("data", [])
                        return {
                            "mode": "tool_success",
                            "message": f"Found {len(reminders)} task(s).",
                            "data": {"reminders": reminders},
                        }
                    else:
                        return {
                            "mode": "tool_success",
                            "message": "Action completed successfully.",
                            "data": data,
                        }
                else:
                    error = result.get("error", {})
                    return {
                        "mode": "tool_error",
                        "message": f"Error: {error.get('message', 'Unknown error')}",
                        "data": {"error": error},
                    }

        # LLM returned text response (no tools needed)
        return {
            "mode": "chat",
            "message": response.get("content", "I'm not sure how to help with that."),
            "data": None,
        }

    except Exception as exc:
        logger.exception("chat_dispatch_failed", error=str(exc), user_id=str(user_id))
        # Fall back to RAG chat on error
        return await _handle_rag_chat(message, user_id)


async def _run_chat_flow(
    message: str,
    conversation_id: Optional[uuid.UUID],
    user_id: uuid.UUID,
    db: asyncpg.Connection,
) -> Dict[str, Any]:
    allowed, retry_after = await chat_rate_limiter.allow(str(user_id))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many chat requests. Try again in a moment.",
                    "retry_after": retry_after,
                }
            },
        )

    chat_turns_total.labels(user_id=str(user_id)).inc()
    response = await _dispatch_chat(message, user_id, db)
    response["conversation_id"] = conversation_id
    return response

@router.post("/notes")
async def create_note_endpoint(
    note: NoteCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """Create a new note"""
    logger.info("create_note_endpoint_start", title=note.title)
    try:
        return await create_note_record(user_id, note, db)
    except Exception as e:
        logger.error("create_note_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/notes")
async def list_notes_endpoint(
    limit: int = 50,
    cursor: str = None,
    user_id: uuid.UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """List notes with pagination"""
    notes = await db.fetch("""
        SELECT id, title, tags, md_path, created_at, updated_at
        FROM notes
        WHERE user_id = $1
        ORDER BY updated_at DESC
        LIMIT $2
    """, user_id, limit)
    
    return {
        "data": [dict(n) for n in notes],
        "pagination": {
            "has_more": len(notes) == limit,
            "next_cursor": str(notes[-1]['id']) if notes else None
        }
    }

@router.patch("/notes/{note_id}")
async def update_note_endpoint(
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """Update a note"""

    note = await db.fetchrow("SELECT * FROM notes WHERE id = $1 AND user_id = $2", note_id, user_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    updated = await db.fetchrow("""
        UPDATE notes
        SET body = COALESCE($1, body),
            tags = COALESCE($2, tags),
            updated_at = NOW()
        WHERE id = $3
        RETURNING *
    """, payload.body, payload.tags, note_id)
    
    update_markdown_file(dict(updated))
    await queue_embedding_task(note_id)
    
    return {"success": True, "data": dict(updated)}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Lightweight, rule-based chat endpoint backed by existing tools."""
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return await _run_chat_flow(message, payload.conversation_id, user_id, db)


@router.get("/chat", response_model=ChatResponse)
async def chat_status(
    message: Optional[str] = None,
    user_id: uuid.UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Support lightweight GET access for health/rate-limit probes."""
    normalized = (message or "status check").strip()

    # Lightweight probe path: check rate limit but skip expensive processing
    if not message or normalized.lower() == "status check":
        allowed, retry_after = await chat_rate_limiter.allow(str(user_id))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many chat requests. Try again in a moment.",
                        "retry_after": retry_after,
                    }
                },
            )
        return ChatResponse(
            mode="status",
            message="Chat endpoint is available",
            conversation_id=None,
            data=None,
            citations=None,
        )

    # Full chat flow for actual messages
    return await _run_chat_flow(normalized, None, user_id, db)


app.include_router(router)

from api.routers import (
    reminders,
    devices,
    documents,
    search,
    calendar,
    google_calendar,
    auth,
    memory,
)
app.include_router(reminders.router)
app.include_router(devices.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(calendar.router)
app.include_router(google_calendar.router)
app.include_router(auth.router)
app.include_router(memory.router)

# Mount static files from web/dist directory (Vite build output)
# This must be done AFTER all API routes are registered
WEB_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
WEB_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "public")

if os.path.exists(WEB_DIST_DIR):
    # Serve static assets (JS, CSS, images) from Vite build
    assets_dir = os.path.join(WEB_DIST_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Serve legacy static files from public directory
if os.path.exists(WEB_PUBLIC_DIR):
    app.mount("/static", StaticFiles(directory=WEB_PUBLIC_DIR), name="static")

# Root route to serve index.html
@app.get("/")
async def read_root():
    """Serve the main UI"""
    # Try Vite build first
    index_path = os.path.join(WEB_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Fallback to public directory
    index_path = os.path.join(WEB_PUBLIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Brainda API is running", "version": "1.0.0", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Internal endpoint to allow worker to reflect retention metrics in API process
@app.post("/api/v1/internal/metrics/retention_bump")
async def retention_bump(payload: dict):
    try:
        table = str(payload.get("table", "unknown"))
        count = int(payload.get("count", 0))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")
    try:
        retention_cleanup_total.labels(table=table).inc(count)
        return {"success": True}
    except Exception:
        raise HTTPException(status_code=500, detail="Metric update failed")

# Catch-all route for SPA (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve React SPA for all non-API routes"""
    # Don't intercept API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # Serve index.html for all other routes (SPA routing)
    index_path = os.path.join(WEB_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    # Fallback to public directory
    index_path = os.path.join(WEB_PUBLIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    # Fallback if build doesn't exist
    return {
        "message": "Brainda API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "Frontend not built. Run 'cd app/web && npm run build'"
    }
