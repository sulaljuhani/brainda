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

logger = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL")
API_TOKEN = os.getenv("API_TOKEN", "default-token-change-me")


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

        # Validate token
        if token != API_TOKEN:
            # Invalid token - let the endpoint handler deal with it
            return await call_next(request)

        # Get user_id from database
        conn = None
        try:
            conn = await connect_with_json_codec(DATABASE_URL)
            user = await conn.fetchrow(
                "SELECT id FROM users WHERE api_token = $1", token
            )

            if user:
                # Set user_id in request state for downstream middleware
                request.state.user_id = user["id"]
                logger.debug(
                    "auth_middleware_user_found", user_id=str(user["id"])
                )
            else:
                # Create user if doesn't exist
                placeholder_email = f"default+{token[:8]}@vib.local"
                new_user = await conn.fetchrow(
                    """
                    INSERT INTO users (email, api_token)
                    VALUES ($1, $2)
                    ON CONFLICT (api_token) DO UPDATE
                    SET email = EXCLUDED.email
                    RETURNING id
                    """,
                    placeholder_email,
                    token,
                )
                request.state.user_id = new_user["id"]
                logger.info(
                    "auth_middleware_user_created", user_id=str(new_user["id"])
                )

        except Exception as e:
            logger.error("auth_middleware_error", error=str(e))
            # Continue without setting user_id
        finally:
            if conn:
                await conn.close()

        return await call_next(request)
