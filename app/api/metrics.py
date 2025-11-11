"""
Central Prometheus metrics registry for VIB.

Metrics cover:
- Business SLOs (reminder firing accuracy, push delivery)
- Business activity (notes, reminders, chat/tool usage)
- Document ingestion / RAG pipeline
- System health gauges (queues, DB connections, cache, vector store)
- Retention/background maintenance tasks
"""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    CONTENT_TYPE_LATEST,
    generate_latest,
)

registry = CollectorRegistry(auto_describe=True)

# ===========================================
# BUSINESS SLO METRICS
# ===========================================

reminder_fire_lag_seconds = Histogram(
    "reminder_fire_lag_seconds",
    "Time between scheduled fire time and actual fire time",
    buckets=[1, 5, 10, 30, 60, 300],
    registry=registry,
)

push_delivery_success_total = Counter(
    "push_delivery_success_total",
    "Successful push notification deliveries",
    ["platform"],
    registry=registry,
)

push_delivery_failure_total = Counter(
    "push_delivery_failure_total",
    "Failed push notification deliveries",
    ["platform", "error_type"],
    registry=registry,
)

# ===========================================
# BUSINESS ACTIVITY METRICS
# ===========================================

chat_turns_total = Counter(
    "chat_turns_total",
    "Total chat messages from users",
    ["user_id"],
    registry=registry,
)

tool_calls_total = Counter(
    "tool_calls_total",
    "LLM tool calls executed, labeled by status",
    ["tool_name", "status"],
    registry=registry,
)

notes_created_total = Counter(
    "notes_created_total",
    "Notes created successfully",
    ["user_id"],
    registry=registry,
)

notes_deduped_total = Counter(
    "notes_deduped_total",
    "Notes prevented by deduplication",
    ["user_id"],
    registry=registry,
)

reminders_created_total = Counter(
    "reminders_created_total",
    "Reminders created successfully",
    ["user_id"],
    registry=registry,
)

reminders_deduped_total = Counter(
    "reminders_deduped_total",
    "Reminders prevented by deduplication",
    ["user_id"],
    registry=registry,
)

reminders_fired_total = Counter(
    "reminders_fired_total",
    "Reminders that fired",
    ["user_id"],
    registry=registry,
)

# ===========================================
# DOCUMENT INGESTION / RAG METRICS
# ===========================================

document_ingestion_duration_seconds = Histogram(
    "document_ingestion_duration_seconds",
    "Time to ingest and index a document",
    buckets=[10, 30, 60, 120, 300, 600],
    registry=registry,
)

document_parsing_duration_seconds = Histogram(
    "document_parsing_duration_seconds",
    "Time spent parsing documents",
    buckets=[1, 5, 10, 30, 60, 120],
    registry=registry,
)

embedding_duration_seconds = Histogram(
    "embedding_duration_seconds",
    "Time to generate embeddings",
    ["source_type"],
    buckets=[1, 5, 10, 30, 60],
    registry=registry,
)

vector_search_duration_seconds = Histogram(
    "vector_search_duration_seconds",
    "Time to perform vector search queries",
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
    registry=registry,
)

documents_ingested_total = Counter(
    "documents_ingested_total",
    "Documents successfully ingested",
    ["user_id", "mime_type"],
    registry=registry,
)

documents_failed_total = Counter(
    "documents_failed_total",
    "Documents that failed ingestion",
    ["user_id", "mime_type", "error_type"],
    registry=registry,
)

chunks_created_total = Counter(
    "chunks_created_total",
    "Chunks created for embeddings",
    ["source_type"],
    registry=registry,
)

rag_queries_total = Counter(
    "rag_queries_total",
    "RAG queries executed by users",
    ["user_id"],
    registry=registry,
)

# ===========================================
# SYSTEM HEALTH METRICS
# ===========================================

celery_queue_depth = Gauge(
    "celery_queue_depth",
    "Number of queued jobs in Celery",
    ["queue_name"],
    registry=registry,
)

postgres_connections = Gauge(
    "postgres_connections",
    "Active Postgres connections",
    registry=registry,
)

redis_memory_bytes = Gauge(
    "redis_memory_bytes",
    "Redis memory usage in bytes",
    registry=registry,
)

qdrant_points_count = Gauge(
    "qdrant_points_count",
    "Vectors stored per Qdrant collection",
    ["collection_name"],
    registry=registry,
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration histogram",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=registry,
)

# ===========================================
# RETENTION / MAINTENANCE
# ===========================================

retention_cleanup_total = Counter(
    "retention_cleanup_total",
    "Rows deleted by retention policy",
    ["table"],
    registry=registry,
)

retention_cleanup_duration_seconds = Histogram(
    "retention_cleanup_duration_seconds",
    "Duration of each retention cleanup run",
    buckets=[1, 5, 15, 30, 60, 120],
    registry=registry,
)


def get_metrics() -> bytes:
    """Return Prometheus exposition format for all metrics."""
    return generate_latest(registry)


def get_content_type() -> str:
    """Return correct content type for Prometheus responses."""
    return CONTENT_TYPE_LATEST
