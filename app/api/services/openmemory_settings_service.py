from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

import asyncpg
import structlog
from cryptography.fernet import Fernet, InvalidToken


logger = structlog.get_logger(__name__)


def _get_fernet() -> Fernet:
    """Get Fernet cipher for encrypting/decrypting OpenMemory API keys."""
    # Try OpenMemory-specific key first, fallback to Google Calendar key for simplicity
    key = os.getenv("OPENMEMORY_ENCRYPTION_KEY") or os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "OPENMEMORY_ENCRYPTION_KEY or GOOGLE_TOKEN_ENCRYPTION_KEY must be set to use OpenMemory settings"
        )
    try:
        return Fernet(key)
    except Exception as exc:
        raise ValueError("Encryption key is invalid") from exc


class OpenMemorySettingsService:
    """Service for managing per-user OpenMemory settings."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    @staticmethod
    def _encrypt_api_key(api_key: str) -> str:
        """Encrypt an API key using Fernet."""
        if not api_key:
            return ""
        fernet = _get_fernet()
        return fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decrypt_api_key(encrypted: str) -> Optional[str]:
        """Decrypt an API key using Fernet. Returns None if decryption fails."""
        if not encrypted:
            return None
        try:
            fernet = _get_fernet()
            return fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as exc:
            logger.warning("api_key_decryption_failed", error=str(exc))
            return None

    async def get_user_settings(self, user_id: UUID) -> dict:
        """
        Get OpenMemory settings for a user.
        Returns user-specific settings if they exist, otherwise returns defaults from environment.
        """
        # Check for user-specific settings
        row = await self.db.fetchrow(
            "SELECT * FROM openmemory_user_settings WHERE user_id = $1",
            user_id,
        )

        if row:
            # User has custom settings
            decrypted_api_key = None
            if row.get("api_key_encrypted"):
                decrypted_api_key = self._decrypt_api_key(row["api_key_encrypted"])

            return {
                "enabled": row.get("enabled", False),
                "server_url": row.get("server_url"),
                "api_key": decrypted_api_key,
                "auto_store_conversations": row.get("auto_store_conversations", True),
                "retention_days": row.get("retention_days", 90),
            }

        # Return global defaults from environment
        global_enabled = os.getenv("OPENMEMORY_ENABLED", "true").lower() == "true"
        global_url = os.getenv("OPENMEMORY_URL")
        global_api_key = os.getenv("OPENMEMORY_API_KEY")

        return {
            "enabled": global_enabled,
            "server_url": global_url,
            "api_key": global_api_key,
            "auto_store_conversations": True,
            "retention_days": 90,
        }

    async def update_user_settings(
        self,
        user_id: UUID,
        enabled: Optional[bool] = None,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        auto_store_conversations: Optional[bool] = None,
        retention_days: Optional[int] = None,
    ) -> dict:
        """
        Update OpenMemory settings for a user.
        Creates new settings row if it doesn't exist.
        Returns updated settings with decrypted API key.
        """
        # Check if user settings exist
        existing = await self.db.fetchrow(
            "SELECT * FROM openmemory_user_settings WHERE user_id = $1",
            user_id,
        )

        # Prepare encrypted API key if provided
        encrypted_api_key = None
        if api_key is not None:
            if api_key:  # Only encrypt if not empty
                encrypted_api_key = self._encrypt_api_key(api_key)
            else:
                encrypted_api_key = ""  # Empty string to clear the key

        if existing:
            # Update existing settings
            updates = []
            params = []
            idx = 1

            if enabled is not None:
                updates.append(f"enabled = ${idx}")
                params.append(enabled)
                idx += 1

            if server_url is not None:
                updates.append(f"server_url = ${idx}")
                params.append(server_url if server_url else None)
                idx += 1

            if encrypted_api_key is not None:
                updates.append(f"api_key_encrypted = ${idx}")
                params.append(encrypted_api_key if encrypted_api_key else None)
                idx += 1

            if auto_store_conversations is not None:
                updates.append(f"auto_store_conversations = ${idx}")
                params.append(auto_store_conversations)
                idx += 1

            if retention_days is not None:
                updates.append(f"retention_days = ${idx}")
                params.append(retention_days)
                idx += 1

            if updates:
                query = f"""
                    UPDATE openmemory_user_settings
                    SET {', '.join(updates)}
                    WHERE user_id = ${idx}
                    RETURNING *
                """
                params.append(user_id)
                row = await self.db.fetchrow(query, *params)
            else:
                row = existing
        else:
            # Insert new settings
            row = await self.db.fetchrow(
                """
                INSERT INTO openmemory_user_settings (
                    user_id, enabled, server_url, api_key_encrypted,
                    auto_store_conversations, retention_days
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                user_id,
                enabled if enabled is not None else False,
                server_url if server_url else None,
                encrypted_api_key if encrypted_api_key else None,
                auto_store_conversations if auto_store_conversations is not None else True,
                retention_days if retention_days is not None else 90,
            )

        # Return decrypted settings
        decrypted_api_key = None
        if row.get("api_key_encrypted"):
            decrypted_api_key = self._decrypt_api_key(row["api_key_encrypted"])

        return {
            "enabled": row.get("enabled", False),
            "server_url": row.get("server_url"),
            "api_key": decrypted_api_key,
            "auto_store_conversations": row.get("auto_store_conversations", True),
            "retention_days": row.get("retention_days", 90),
        }
