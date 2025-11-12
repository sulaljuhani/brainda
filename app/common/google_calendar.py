from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import asyncpg
import structlog
from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials

logger = structlog.get_logger()

STATE_TOKEN_TTL_SECONDS = int(os.getenv("GOOGLE_OAUTH_STATE_TTL", "600"))


class GoogleConfigurationError(RuntimeError):
    """Raised when required Google Calendar configuration is missing."""


def _get_state_secret() -> bytes:
    secret = os.getenv("GOOGLE_OAUTH_STATE_SECRET")
    if not secret:
        raise GoogleConfigurationError("GOOGLE_OAUTH_STATE_SECRET is not set")
    return secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def generate_state_token(user_id: UUID, expires_in: Optional[int] = None) -> str:
    """Generate a short-lived, signed OAuth2 state token."""

    issued_at = int(time.time())
    ttl = expires_in or STATE_TOKEN_TTL_SECONDS
    payload = {
        "uid": str(user_id),
        "iat": issued_at,
        "exp": issued_at + ttl,
        "nonce": secrets.token_urlsafe(16),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(_get_state_secret(), payload_bytes, hashlib.sha256).digest()
    return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def verify_state_token(token: str) -> Optional[UUID]:
    """Validate a previously issued OAuth2 state token."""

    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    try:
        payload_bytes = _b64decode(payload_b64)
        provided_signature = _b64decode(signature_b64)
    except (ValueError, binascii.Error):
        return None

    expected_signature = hmac.new(_get_state_secret(), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None

    try:
        return UUID(payload["uid"])
    except (KeyError, ValueError):
        return None


def _get_fernet() -> Fernet:
    key = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY")
    if not key:
        raise GoogleConfigurationError("GOOGLE_TOKEN_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise GoogleConfigurationError("GOOGLE_TOKEN_ENCRYPTION_KEY is invalid") from exc


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return value


def encrypt_credentials(data: dict[str, Any]) -> str:
    payload = json.dumps(data, default=_serialize).encode("utf-8")
    return _get_fernet().encrypt(payload).decode("utf-8")


def decrypt_credentials(value: str) -> dict[str, Any]:
    plaintext = _get_fernet().decrypt(value.encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))


def credentials_to_dict(credentials: Credentials) -> dict[str, Any]:
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }


def credentials_from_dict(data: dict[str, Any]) -> Credentials:
    expiry_value = data.get("expiry")
    expiry: Optional[datetime] = None
    if isinstance(expiry_value, str):
        try:
            expiry = datetime.fromisoformat(expiry_value)
        except ValueError:
            expiry = None
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
        expiry=expiry,
    )


class GoogleCalendarRepository:
    """Low-level data access helpers for Google Calendar synchronisation."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def ensure_sync_state(self, user_id: UUID) -> None:
        await self.conn.execute(
            """
            INSERT INTO calendar_sync_state (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )

    async def update_sync_state(self, user_id: UUID, **fields: Any) -> None:
        if not fields:
            return
        await self.ensure_sync_state(user_id)
        assignments = []
        values: list[Any] = [user_id]
        idx = 2
        for key, value in fields.items():
            assignments.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        assignments.append("updated_at = NOW()")
        query = f"""
            UPDATE calendar_sync_state
            SET {', '.join(assignments)}
            WHERE user_id = $1
        """
        await self.conn.execute(query, *values)

    async def get_sync_state(self, user_id: UUID) -> Optional[dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT * FROM calendar_sync_state WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None

    async def list_users_with_sync(self) -> list[dict[str, Any]]:
        rows = await self.conn.fetch(
            """
            SELECT user_id, sync_direction, last_sync_at
            FROM calendar_sync_state
            WHERE sync_enabled = TRUE
        """
        )
        return [dict(row) for row in rows]

    async def save_credentials(self, user_id: UUID, data: dict[str, Any]) -> None:
        encrypted = encrypt_credentials(data)
        await self.conn.execute(
            """
            INSERT INTO google_credentials (user_id, encrypted_credentials, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET encrypted_credentials = EXCLUDED.encrypted_credentials,
                updated_at = NOW()
            """,
            user_id,
            encrypted,
        )

    async def get_credentials(self, user_id: UUID) -> Optional[dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT encrypted_credentials FROM google_credentials WHERE user_id = $1",
            user_id,
        )
        if not row:
            return None
        try:
            return decrypt_credentials(row["encrypted_credentials"])
        except InvalidToken:
            logger.error("google_credentials_decryption_failed", user_id=str(user_id))
            return None

    async def delete_credentials(self, user_id: UUID) -> None:
        await self.conn.execute(
            "DELETE FROM google_credentials WHERE user_id = $1",
            user_id,
        )

    async def list_events_for_sync(self, user_id: UUID, source: str) -> list[dict[str, Any]]:
        rows = await self.conn.fetch(
            """
            SELECT *
            FROM calendar_events
            WHERE user_id = $1
              AND source = $2
        """,
            user_id,
            source,
        )
        return [dict(row) for row in rows]

    async def update_event_fields(self, event_id: UUID, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not fields:
            return None
        assignments = []
        values: list[Any] = []
        idx = 1
        for key, value in fields.items():
            assignments.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        assignments.append("updated_at = NOW()")
        values.append(event_id)
        query = f"""
            UPDATE calendar_events
            SET {', '.join(assignments)}
            WHERE id = ${idx}
            RETURNING *
        """
        row = await self.conn.fetchrow(query, *values)
        return dict(row) if row else None

    async def get_event_by_google_id(self, google_event_id: str) -> Optional[dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT * FROM calendar_events WHERE google_event_id = $1",
            google_event_id,
        )
        return dict(row) if row else None

    async def create_google_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = await self.conn.fetchrow(
            """
            INSERT INTO calendar_events (
                user_id,
                title,
                description,
                starts_at,
                ends_at,
                timezone,
                location_text,
                rrule,
                source,
                google_event_id,
                google_calendar_id,
                status
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
            )
            RETURNING *
            """,
            payload["user_id"],
            payload["title"],
            payload.get("description"),
            payload["starts_at"],
            payload.get("ends_at"),
            payload["timezone"],
            payload.get("location_text"),
            payload.get("rrule"),
            payload.get("source", "google"),
            payload.get("google_event_id"),
            payload.get("google_calendar_id"),
            payload.get("status", "confirmed"),
        )
        return dict(row)

    async def get_event(self, event_id: UUID) -> Optional[dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT * FROM calendar_events WHERE id = $1",
            event_id,
        )
        return dict(row) if row else None

    async def delete_credentials_and_state(self, user_id: UUID) -> None:
        await self.delete_credentials(user_id)
        await self.update_sync_state(
            user_id,
            sync_enabled=False,
            sync_token=None,
            google_calendar_id=None,
        )


