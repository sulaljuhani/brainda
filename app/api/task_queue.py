from __future__ import annotations

import os
from functools import lru_cache
from celery import Celery


@lru_cache(maxsize=1)
def get_celery_client() -> Celery:
    """Return a configured Celery client instance.

    Celery initialization is moderately expensive and we need a shared client
    across routers and services. Using an LRU cache avoids circular imports
    from FastAPI's startup sequence while still giving every caller the same
    configured handle.
    """
    broker_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    celery_app = Celery("brainda-worker", broker=broker_url, backend=broker_url)
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=900,
        task_soft_time_limit=840,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
    )
    concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", "3"))
    celery_app.conf.worker_concurrency = concurrency
    return celery_app


__all__ = ["get_celery_client"]
