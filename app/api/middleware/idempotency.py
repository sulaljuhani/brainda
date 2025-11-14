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
import asyncio
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

        # Read request body for caching and compute request hash
        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()

        # Attempt to claim this idempotency key to prevent concurrent duplicates
        # The first requester inserts a placeholder row; others will wait for the
        # response to be populated and then return the cached response.
        claimed = await self.claim_idempotency_key(
            user_id, idempotency_key, endpoint, request_hash
        )
        if not claimed:
            # Another request is in-flight; wait briefly for it to complete
            cached = await self.wait_for_cached_response(
                user_id, idempotency_key, endpoint, timeout_seconds=5.0, poll_interval=0.1
            )
            if cached:
                return Response(
                    content=cached["response_body"],
                    status_code=cached["response_status"],
                    headers={"X-Idempotency-Replay": "true", "Content-Type": "application/json"},
                    media_type="application/json",
                )
            # If not cached after waiting, proceed to handle request (best effort)

        # Execute request
        # We need to make the body available again for the next handler
        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive

        response = await call_next(request)

        # Cache response (only for successful state changes)
        if 200 <= response.status_code < 300:
            response_body = await self.cache_response(
                user_id, idempotency_key, endpoint, body, response
            )
            # Reconstruct response with the cached body
            if response_body is not None:
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type or "application/json",
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
        """Store response in cache for 24 hours and return the response body"""
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
                return response_body

            conn = await connect_with_json_codec(DATABASE_URL)
            query = """
                INSERT INTO idempotency_keys
                (idempotency_key, user_id, endpoint, request_hash, response_status, response_body, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '24 hours')
                ON CONFLICT (user_id, idempotency_key, endpoint)
                DO UPDATE SET
                    request_hash = EXCLUDED.request_hash,
                    response_status = EXCLUDED.response_status,
                    response_body = EXCLUDED.response_body,
                    expires_at = EXCLUDED.expires_at
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

            return response_body

        except Exception as e:
            logger.error("idempotency_cache_store_failed", error=str(e))
            return None
        finally:
            if conn:
                await conn.close()

    async def claim_idempotency_key(self, user_id, key: str, endpoint: str, request_hash: str) -> bool:
        """Attempt to create a placeholder record for this idempotency key.

        Returns True if we successfully claimed (i.e., first in-flight request), False
        if another request already claimed it.
        """
        conn = None
        try:
            conn = await connect_with_json_codec(DATABASE_URL)
            query = """
                INSERT INTO idempotency_keys
                (idempotency_key, user_id, endpoint, request_hash, response_status, response_body, expires_at)
                VALUES ($1, $2, $3, $4, 102, '{}'::jsonb, NOW() + INTERVAL '24 hours')
                ON CONFLICT (user_id, idempotency_key, endpoint) DO NOTHING
                RETURNING id
            """
            row = await conn.fetchrow(query, key, user_id, endpoint, request_hash)
            return bool(row)
        except Exception as e:
            logger.error("idempotency_claim_failed", error=str(e))
            return False
        finally:
            if conn:
                await conn.close()

    async def wait_for_cached_response(
        self,
        user_id,
        key: str,
        endpoint: str,
        timeout_seconds: float = 5.0,
        poll_interval: float = 0.1,
    ) -> Optional[dict]:
        """Poll for a cached response for a short time.

        This allows concurrent requests with the same idempotency key to wait for
        the first request to complete and populate the cache.
        """
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            cached = await self.get_cached_response(user_id, key, endpoint)
            if cached and 200 <= cached.get("response_status", 0) < 300:
                return cached
            await asyncio.sleep(poll_interval)
        return None
