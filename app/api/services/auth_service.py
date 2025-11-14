from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional
from uuid import UUID

import hashlib
import hmac
import os

import asyncpg
import bcrypt
import structlog


logger = structlog.get_logger(__name__)

_SESSION_TOKEN_SECRET = os.getenv("SESSION_TOKEN_SECRET")
if not _SESSION_TOKEN_SECRET:
    fallback_secret = os.getenv("API_TOKEN") or "default-session-secret-change-me"
    logger.warning(
        "session_token_secret_missing",
        message="Falling back to less secure default for session hashing",
    )
    _SESSION_TOKEN_SECRET = fallback_secret
_SESSION_TOKEN_SECRET_BYTES = _SESSION_TOKEN_SECRET.encode("utf-8")


def _hash_session_token(token: str) -> str:
    return hmac.new(_SESSION_TOKEN_SECRET_BYTES, token.encode("utf-8"), hashlib.sha256).hexdigest()


class AuthService:
    """Data access helpers for authentication and account management."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    # --- User helpers -----------------------------------------------------

    async def get_user_by_email(self, email: str) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow("SELECT * FROM users WHERE email = $1", email)

    async def get_user_by_username(self, username: str) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow("SELECT * FROM users WHERE username = $1", username)

    async def get_user_by_id(self, user_id: UUID) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def create_organization(self, name: str) -> asyncpg.Record:
        return await self.db.fetchrow(
            """
            INSERT INTO organizations (name)
            VALUES ($1)
            RETURNING *
            """,
            name,
        )

    async def create_user_for_passkey(
        self,
        email: str,
        display_name: Optional[str] = None,
    ) -> asyncpg.Record:
        """Legacy passkey user creation - generates username from email."""
        normalized_email = email.strip().lower()
        username = normalized_email.split("@")[0]  # Use email prefix as username
        org_name = display_name or normalized_email
        async with self.db.transaction():
            organization = await self.create_organization(org_name)
            user = await self.db.fetchrow(
                """
                INSERT INTO users (username, email, display_name, organization_id, role, is_active)
                VALUES ($1, $2, $3, $4, 'owner', FALSE)
                RETURNING *
                """,
                username,
                normalized_email,
                display_name,
                organization["id"],
            )
        return user

    async def ensure_user_profile(
        self,
        user: asyncpg.Record,
        display_name: Optional[str] = None,
    ) -> asyncpg.Record:
        updates: Dict[str, Any] = {}
        user_data = dict(user)
        if display_name and user_data.get("display_name") != display_name:
            updates["display_name"] = display_name

        if user_data.get("organization_id") is None:
            org_name = display_name or user_data.get("display_name") or user_data.get("email")
            organization = await self.create_organization(org_name)
            updates["organization_id"] = organization["id"]
            updates["role"] = user_data.get("role") or "owner"

        if not user_data.get("is_active"):
            updates["is_active"] = True

        if updates:
            user = await self.update_user(user["id"], updates)
        return user

    async def update_user(self, user_id: UUID, updates: Dict[str, Any]) -> asyncpg.Record:
        if not updates:
            existing = await self.get_user_by_id(user_id)
            if existing is None:
                raise ValueError("User not found")
            return existing

        assignments = []
        values: list[Any] = []
        idx = 1
        for column, value in updates.items():
            assignments.append(f"{column} = ${idx}")
            values.append(value)
            idx += 1
        assignments.append("updated_at = NOW()")
        query = (
            "UPDATE users SET "
            + ", ".join(assignments)
            + f" WHERE id = ${idx} RETURNING *"
        )
        values.append(user_id)
        updated = await self.db.fetchrow(query, *values)
        if updated is None:
            raise ValueError("User not found")
        return updated

    # --- Passkey helpers --------------------------------------------------

    async def create_passkey_credential(
        self,
        user_id: UUID,
        credential_id: str,
        public_key: str,
        sign_count: int,
        transports: Optional[Iterable[str]] = None,
        device_name: Optional[str] = None,
    ) -> asyncpg.Record:
        transports_array = list(transports) if transports else None
        return await self.db.fetchrow(
            """
            INSERT INTO passkey_credentials (
                user_id, credential_id, public_key, counter, transports, device_name, last_used_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING *
            """,
            user_id,
            credential_id,
            public_key,
            sign_count,
            transports_array,
            device_name,
        )

    async def get_passkey_credential_by_id(
        self, credential_id: str
    ) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow(
            "SELECT * FROM passkey_credentials WHERE credential_id = $1",
            credential_id,
        )

    async def update_passkey_credential(
        self,
        credential_id: UUID,
        updates: Dict[str, Any],
    ) -> asyncpg.Record:
        if not updates:
            existing = await self.db.fetchrow(
                "SELECT * FROM passkey_credentials WHERE id = $1",
                credential_id,
            )
            if existing is None:
                raise ValueError("Credential not found")
            return existing

        assignments = []
        values: list[Any] = []
        idx = 1
        for column, value in updates.items():
            assignments.append(f"{column} = ${idx}")
            values.append(value)
            idx += 1
        query = (
            "UPDATE passkey_credentials SET "
            + ", ".join(assignments)
            + f" WHERE id = ${idx} RETURNING *"
        )
        values.append(credential_id)
        updated = await self.db.fetchrow(query, *values)
        if updated is None:
            raise ValueError("Credential not found")
        return updated

    # --- Sessions ---------------------------------------------------------

    async def create_session(
        self,
        user_id: UUID,
        token: str,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> asyncpg.Record:
        expiry = expires_at or datetime.now(timezone.utc) + timedelta(days=30)
        hashed_token = _hash_session_token(token)
        return await self.db.fetchrow(
            """
            INSERT INTO sessions (
                user_id, token, device_name, device_type, ip_address, user_agent, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            user_id,
            hashed_token,
            device_name,
            device_type,
            ip_address,
            user_agent,
            expiry,
        )

    async def get_session_by_token(self, token: str) -> Optional[asyncpg.Record]:
        hashed_token = _hash_session_token(token)
        session = await self.db.fetchrow(
            "SELECT * FROM sessions WHERE token = $1",
            hashed_token,
        )
        if session:
            return session

        # Legacy plaintext sessions fallback with automatic migration
        legacy_session = await self.db.fetchrow(
            "SELECT * FROM sessions WHERE token = $1",
            token,
        )
        if not legacy_session:
            return None

        try:
            await self.db.execute(
                "UPDATE sessions SET token = $1 WHERE id = $2",
                hashed_token,
                legacy_session["id"],
            )
            refreshed = await self.db.fetchrow(
                "SELECT * FROM sessions WHERE id = $1",
                legacy_session["id"],
            )
            logger.info(
                "session_token_migrated",
                session_id=str(legacy_session["id"]),
            )
            return refreshed
        except Exception as exc:
            logger.warning(
                "session_token_migration_failed",
                session_id=str(legacy_session["id"]),
                error=str(exc),
            )
            return legacy_session

    async def touch_session(self, session_id: UUID) -> None:
        await self.db.execute(
            "UPDATE sessions SET last_active_at = NOW() WHERE id = $1",
            session_id,
        )

    async def delete_session(self, token: str) -> None:
        hashed_token = _hash_session_token(token)
        deleted = await self.db.execute("DELETE FROM sessions WHERE token = $1", hashed_token)
        if deleted == "DELETE 0":
            await self.db.execute("DELETE FROM sessions WHERE token = $1", token)

    # --- Audit log --------------------------------------------------------

    async def log_auth_event(
        self,
        event_type: str,
        *,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await self.db.execute(
                """
                INSERT INTO auth_audit_log (user_id, event_type, ip_address, user_agent, metadata)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                event_type,
                ip_address,
                user_agent,
                metadata,
            )
        except Exception as exc:
            logger.warning("auth_event_log_failed", error=str(exc), event_type=event_type)

    # --- TOTP -------------------------------------------------------------

    @staticmethod
    def hash_backup_codes(codes: Iterable[str]) -> list[str]:
        return [bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for code in codes]

    async def create_totp_secret(
        self,
        user_id: UUID,
        secret: str,
        backup_codes: Iterable[str],
        enabled: bool = False,
    ) -> asyncpg.Record:
        hashed_codes = self.hash_backup_codes(backup_codes)
        return await self.db.fetchrow(
            """
            INSERT INTO totp_secrets (user_id, secret, enabled, backup_codes)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET secret = EXCLUDED.secret,
                enabled = EXCLUDED.enabled,
                backup_codes = EXCLUDED.backup_codes,
                verified_at = NULL
            RETURNING *
            """,
            user_id,
            secret,
            enabled,
            hashed_codes,
        )

    async def get_totp_secret(self, user_id: UUID) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow(
            "SELECT * FROM totp_secrets WHERE user_id = $1",
            user_id,
        )

    async def update_totp_secret(
        self,
        totp_id: UUID,
        updates: Dict[str, Any],
    ) -> asyncpg.Record:
        if not updates:
            existing = await self.db.fetchrow(
                "SELECT * FROM totp_secrets WHERE id = $1",
                totp_id,
            )
            if existing is None:
                raise ValueError("TOTP secret not found")
            return existing

        assignments = []
        values: list[Any] = []
        idx = 1
        for column, value in updates.items():
            assignments.append(f"{column} = ${idx}")
            values.append(value)
            idx += 1
        query = (
            "UPDATE totp_secrets SET "
            + ", ".join(assignments)
            + f" WHERE id = ${idx} RETURNING *"
        )
        values.append(totp_id)
        updated = await self.db.fetchrow(query, *values)
        if updated is None:
            raise ValueError("TOTP secret not found")
        return updated

    async def replace_backup_codes(
        self,
        totp_id: UUID,
        backup_codes: Iterable[str],
    ) -> asyncpg.Record:
        hashed_codes = self.hash_backup_codes(backup_codes)
        return await self.update_totp_secret(
            totp_id,
            {"backup_codes": hashed_codes},
        )

    # --- Password helpers -------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against a bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    async def create_user_with_password(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> asyncpg.Record:
        """Create a new user with username and password."""
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower() if email else None
        password_hash = self.hash_password(password)
        org_name = display_name or normalized_username
        async with self.db.transaction():
            organization = await self.create_organization(org_name)
            user = await self.db.fetchrow(
                """
                INSERT INTO users (username, email, password_hash, display_name, organization_id, role, is_active)
                VALUES ($1, $2, $3, $4, $5, 'owner', TRUE)
                RETURNING *
                """,
                normalized_username,
                normalized_email,
                password_hash,
                display_name,
                organization["id"],
            )
        return user

    async def authenticate_with_password(
        self,
        username: str,
        password: str,
    ) -> Optional[asyncpg.Record]:
        """Authenticate user with username and password. Returns user if successful, None otherwise."""
        user = await self.get_user_by_username(username.strip().lower())
        if not user:
            return None

        if not user.get("password_hash"):
            return None

        if not self.verify_password(password, user["password_hash"]):
            return None

        if not user.get("is_active"):
            return None

        return user
