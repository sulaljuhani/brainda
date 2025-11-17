"""Service layer for managing LLM model configurations."""

from typing import List, Optional, Dict, Any
from uuid import UUID
import asyncpg
import structlog
from cryptography.fernet import Fernet
import os
import json

logger = structlog.get_logger()

# Encryption key for sensitive config data (API keys, etc.)
ENCRYPTION_KEY = os.getenv("LLM_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt sensitive fields in config (api_key, custom headers, etc.)."""
    encrypted = config.copy()

    # Fields to encrypt
    sensitive_fields = ["api_key", "authorization", "bearer_token"]

    for field in sensitive_fields:
        if field in encrypted and encrypted[field]:
            encrypted[field] = fernet.encrypt(encrypted[field].encode()).decode()

    return encrypted


def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt sensitive fields in config."""
    decrypted = config.copy()

    sensitive_fields = ["api_key", "authorization", "bearer_token"]

    for field in sensitive_fields:
        if field in decrypted and decrypted[field]:
            try:
                decrypted[field] = fernet.decrypt(decrypted[field].encode()).decode()
            except Exception as e:
                logger.warning(f"Failed to decrypt {field}", error=str(e))

    return decrypted


class LLMModelsService:
    """Service for managing user LLM model configurations."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def list_models(self, user_id: UUID, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all LLM models for a user."""
        query = """
            SELECT id, user_id, name, provider, model_name, config,
                   temperature, max_tokens, is_default, is_active,
                   created_at, updated_at
            FROM llm_models
            WHERE user_id = $1
        """

        if not include_inactive:
            query += " AND is_active = TRUE"

        query += " ORDER BY is_default DESC, created_at DESC"

        rows = await self.db.fetch(query, user_id)

        models = []
        for row in rows:
            model = dict(row)
            # Don't decrypt config in list view for security
            # Config will be decrypted only when needed for adapter creation
            models.append(model)

        return models

    async def get_model(self, user_id: UUID, model_id: UUID, decrypt: bool = False) -> Optional[Dict[str, Any]]:
        """Get a specific LLM model by ID."""
        row = await self.db.fetchrow(
            """
            SELECT id, user_id, name, provider, model_name, config,
                   temperature, max_tokens, is_default, is_active,
                   created_at, updated_at
            FROM llm_models
            WHERE id = $1 AND user_id = $2
            """,
            model_id,
            user_id,
        )

        if not row:
            return None

        model = dict(row)

        if decrypt and model.get("config"):
            model["config"] = decrypt_config(model["config"])

        return model

    async def get_default_model(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the default LLM model for a user."""
        row = await self.db.fetchrow(
            """
            SELECT id, user_id, name, provider, model_name, config,
                   temperature, max_tokens, is_default, is_active,
                   created_at, updated_at
            FROM llm_models
            WHERE user_id = $1 AND is_default = TRUE AND is_active = TRUE
            LIMIT 1
            """,
            user_id,
        )

        if not row:
            return None

        model = dict(row)
        model["config"] = decrypt_config(model["config"])

        return model

    async def create_model(
        self,
        user_id: UUID,
        name: str,
        provider: str,
        model_name: str,
        config: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """Create a new LLM model configuration."""

        # Encrypt sensitive config fields
        encrypted_config = encrypt_config(config)

        async with self.db.transaction():
            # If setting as default, unset other defaults
            if is_default:
                await self.db.execute(
                    "UPDATE llm_models SET is_default = FALSE WHERE user_id = $1",
                    user_id,
                )

            row = await self.db.fetchrow(
                """
                INSERT INTO llm_models (
                    user_id, name, provider, model_name, config,
                    temperature, max_tokens, is_default
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, user_id, name, provider, model_name, config,
                          temperature, max_tokens, is_default, is_active,
                          created_at, updated_at
                """,
                user_id,
                name,
                provider,
                model_name,
                json.dumps(encrypted_config),
                temperature,
                max_tokens,
                is_default,
            )

        return dict(row)

    async def update_model(
        self,
        user_id: UUID,
        model_id: UUID,
        name: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        is_default: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an LLM model configuration."""

        # Check if model exists and belongs to user
        existing = await self.get_model(user_id, model_id)
        if not existing:
            return None

        updates = []
        values = []
        param_count = 1

        if name is not None:
            updates.append(f"name = ${param_count}")
            values.append(name)
            param_count += 1

        if provider is not None:
            updates.append(f"provider = ${param_count}")
            values.append(provider)
            param_count += 1

        if model_name is not None:
            updates.append(f"model_name = ${param_count}")
            values.append(model_name)
            param_count += 1

        if config is not None:
            encrypted_config = encrypt_config(config)
            updates.append(f"config = ${param_count}")
            values.append(json.dumps(encrypted_config))
            param_count += 1

        if temperature is not None:
            updates.append(f"temperature = ${param_count}")
            values.append(temperature)
            param_count += 1

        if max_tokens is not None:
            updates.append(f"max_tokens = ${param_count}")
            values.append(max_tokens)
            param_count += 1

        if is_default is not None:
            updates.append(f"is_default = ${param_count}")
            values.append(is_default)
            param_count += 1

        if is_active is not None:
            updates.append(f"is_active = ${param_count}")
            values.append(is_active)
            param_count += 1

        if not updates:
            return existing

        updates.append("updated_at = NOW()")
        values.extend([model_id, user_id])

        query = f"""
            UPDATE llm_models
            SET {', '.join(updates)}
            WHERE id = ${param_count} AND user_id = ${param_count + 1}
            RETURNING id, user_id, name, provider, model_name, config,
                      temperature, max_tokens, is_default, is_active,
                      created_at, updated_at
        """

        async with self.db.transaction():
            # If setting as default, unset other defaults
            if is_default:
                await self.db.execute(
                    "UPDATE llm_models SET is_default = FALSE WHERE user_id = $1 AND id != $2",
                    user_id,
                    model_id,
                )

            row = await self.db.fetchrow(query, *values)

        return dict(row) if row else None

    async def delete_model(self, user_id: UUID, model_id: UUID) -> bool:
        """Delete an LLM model configuration."""
        result = await self.db.execute(
            "DELETE FROM llm_models WHERE id = $1 AND user_id = $2",
            model_id,
            user_id,
        )

        return result == "DELETE 1"

    async def set_default_model(self, user_id: UUID, model_id: UUID) -> bool:
        """Set a model as the default for a user."""
        async with self.db.transaction():
            # Verify model exists and belongs to user
            existing = await self.get_model(user_id, model_id)
            if not existing:
                return False

            # Unset all defaults
            await self.db.execute(
                "UPDATE llm_models SET is_default = FALSE WHERE user_id = $1",
                user_id,
            )

            # Set new default
            await self.db.execute(
                "UPDATE llm_models SET is_default = TRUE WHERE id = $1 AND user_id = $2",
                model_id,
                user_id,
            )

        return True
