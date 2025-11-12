"""
Authentication middleware that extracts user_id from token and sets it in request state.
This allows downstream middleware (like IdempotencyMiddleware) to access user_id without
requiring database queries in every middleware.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import structlog
import os
from common.db import connect_with_json_codec
from api.dependencies import get_user_id_from_token

logger = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL")


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extracts user_id from Authorization header and sets it in request.state.
    """

    # Endpoints that don't require authentication
    PUBLIC_ENDPOINTS = {
        "/api/v1/health",
        "/api/v1/version",
        "/api/v1/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if request.url.path in self.PUBLIC_ENDPOINTS:
            return await call_next(request)

        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            # No auth header - let the endpoint handler deal with it
            return await call_next(request)

        token = authorization.split(" ", 1)[1]

        # Get user_id from database/session
        conn = None
        try:
            conn = await connect_with_json_codec(DATABASE_URL)
            user_id = await get_user_id_from_token(token, conn)
            request.state.user_id = user_id
            logger.debug("auth_middleware_user_found", user_id=str(user_id))

        except Exception as e:
            logger.error("auth_middleware_error", error=str(e))
            # Continue without setting user_id
        finally:
            if conn:
                await conn.close()

        return await call_next(request)
