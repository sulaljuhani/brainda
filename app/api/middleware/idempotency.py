"""
Idempotency middleware for ensuring exactly-once semantics.

This middleware ensures that state-changing operations (POST, PATCH, PUT, DELETE)
can be safely retried without creating duplicate data. It works by:

1. Client sends Idempotency-Key header (UUID v4)
2. Middleware checks if key exists in cache
3. If exists: return cached response (idempotent replay)
4. If new: execute request, cache response for 24h
5. Auto-cleanup expired keys via scheduled job
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import hashlib
import json
import structlog
import os
from common.db import connect_with_json_codec

logger = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Ensures exactly-once semantics for state-changing operations.
    """

    IDEMPOTENT_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
    IDEMPOTENT_ENDPOINTS = {
        "/api/v1/notes",
        "/api/v1/reminders",
        "/api/v1/calendar/events",
        "/api/v1/ingest",
        "/api/v1/documents",
    }

    async def dispatch(self, request: Request, call_next):
        # Only apply to state-changing operations
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        # Only apply to specific endpoints
        if not any(request.url.path.startswith(ep) for ep in self.IDEMPOTENT_ENDPOINTS):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # No key provided: proceed normally (backward compatible)
            return await call_next(request)

        # Get user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # No user_id available - skip idempotency check
            # This happens for unauthenticated endpoints
            return await call_next(request)

        endpoint = request.url.path

        # Check cache
        cached = await self.get_cached_response(user_id, idempotency_key, endpoint)
        if cached:
            logger.info(
                "idempotency_cache_hit",
                extra={
                    "user_id": str(user_id),
                    "idempotency_key": idempotency_key,
                    "endpoint": endpoint,
                },
            )
            return Response(
                content=cached["response_body"],
                status_code=cached["response_status"],
                headers={"X-Idempotency-Replay": "true", "Content-Type": "application/json"},
                media_type="application/json",
            )

        # Read request body for caching
        body = await request.body()

        # Execute request
        # We need to make the body available again for the next handler
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive

        response = await call_next(request)

        # Cache response (only for successful state changes)
        if 200 <= response.status_code < 300:
            await self.cache_response(
                user_id, idempotency_key, endpoint, body, response
            )

        return response

    async def get_cached_response(
        self, user_id, key: str, endpoint: str
    ) -> Optional[dict]:
        """Fetch cached response from database"""
        conn = None
        try:
            conn = await connect_with_json_codec(DATABASE_URL)
            query = """
                SELECT response_status, response_body
                FROM idempotency_keys
                WHERE user_id = $1 AND idempotency_key = $2 AND endpoint = $3
                AND expires_at > NOW()
            """
            row = await conn.fetchrow(query, user_id, key, endpoint)
            if row:
                return {
                    "response_status": row["response_status"],
                    "response_body": json.dumps(row["response_body"]),
                }
            return None
        except Exception as e:
            logger.error("idempotency_cache_lookup_failed", error=str(e))
            return None
        finally:
            if conn:
                await conn.close()

    async def cache_response(
        self, user_id, key: str, endpoint: str, request_body: bytes, response: Response
    ):
        """Store response in cache for 24 hours"""
        conn = None
        try:
            request_hash = hashlib.sha256(request_body).hexdigest()

            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Parse response body as JSON
            try:
                response_json = json.loads(response_body.decode())
            except json.JSONDecodeError:
                logger.warning(
                    "idempotency_cache_json_decode_failed",
                    response_body=response_body.decode()[:200],
                )
                return

            conn = await connect_with_json_codec(DATABASE_URL)
            query = """
                INSERT INTO idempotency_keys
                (idempotency_key, user_id, endpoint, request_hash, response_status, response_body, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '24 hours')
                ON CONFLICT (user_id, idempotency_key, endpoint) DO NOTHING
            """
            await conn.execute(
                query,
                key,
                user_id,
                endpoint,
                request_hash,
                response.status_code,
                response_json,
            )

            logger.info(
                "idempotency_response_cached",
                user_id=str(user_id),
                idempotency_key=key,
                endpoint=endpoint,
            )

        except Exception as e:
            logger.error("idempotency_cache_store_failed", error=str(e))
        finally:
            if conn:
                await conn.close()
