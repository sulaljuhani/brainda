"""API Router for LLM model management."""

from uuid import UUID
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import asyncpg
import logging
import asyncio

from api.dependencies import get_db, get_current_user
from api.services.llm_models_service import LLMModelsService
from api.adapters.llm_adapter import build_adapter_from_config, LLMAdapterError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm-models", tags=["llm-models"])


class LLMModelResponse(BaseModel):
    """LLM model response model."""
    id: UUID
    user_id: UUID
    name: str
    provider: str
    model_name: str
    config: Dict[str, Any]  # Masked in list views
    temperature: float
    max_tokens: Optional[int]
    is_default: bool
    is_active: bool


class CreateLLMModelRequest(BaseModel):
    """Create LLM model request."""
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., pattern="^(openai|anthropic|ollama|custom)$")
    model_name: str = Field(..., min_length=1, max_length=255)
    config: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    is_default: bool = False


class UpdateLLMModelRequest(BaseModel):
    """Update LLM model request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[str] = Field(None, pattern="^(openai|anthropic|ollama|custom)$")
    model_name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


def mask_sensitive_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in config for API responses."""
    masked = config.copy()
    sensitive_fields = ["api_key", "authorization", "bearer_token"]

    for field in sensitive_fields:
        if field in masked and masked[field]:
            masked[field] = "***MASKED***"

    return masked


@router.get("", response_model=List[LLMModelResponse])
async def list_llm_models(
    include_inactive: bool = False,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """List all LLM models for the current user.

    Sensitive config fields (API keys) are masked in the response.
    """
    try:
        service = LLMModelsService(db)
        models = await service.list_models(user_id, include_inactive)

        # Mask sensitive fields in config
        for model in models:
            if model.get("config"):
                model["config"] = mask_sensitive_config(model["config"])

        return models

    except Exception as e:
        logger.error(f"Error listing LLM models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list LLM models")


@router.get("/default", response_model=Optional[LLMModelResponse])
async def get_default_llm_model(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get the default LLM model for the current user."""
    try:
        service = LLMModelsService(db)
        model = await service.get_default_model(user_id)

        if model and model.get("config"):
            model["config"] = mask_sensitive_config(model["config"])

        return model

    except Exception as e:
        logger.error(f"Error getting default LLM model: {e}")
        raise HTTPException(status_code=500, detail="Failed to get default LLM model")


@router.get("/{model_id}", response_model=LLMModelResponse)
async def get_llm_model(
    model_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get a specific LLM model by ID."""
    try:
        service = LLMModelsService(db)
        model = await service.get_model(user_id, model_id, decrypt=False)

        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")

        # Mask sensitive fields
        if model.get("config"):
            model["config"] = mask_sensitive_config(model["config"])

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM model: {e}")
        raise HTTPException(status_code=500, detail="Failed to get LLM model")


@router.post("", response_model=LLMModelResponse, status_code=201)
async def create_llm_model(
    request: CreateLLMModelRequest,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Create a new LLM model configuration."""
    try:
        service = LLMModelsService(db)
        model = await service.create_model(
            user_id=user_id,
            name=request.name,
            provider=request.provider,
            model_name=request.model_name,
            config=request.config,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            is_default=request.is_default,
        )

        # Mask sensitive fields
        if model.get("config"):
            model["config"] = mask_sensitive_config(model["config"])

        return model

    except Exception as e:
        logger.error(f"Error creating LLM model: {e}")
        if "llm_models_user_name_unique" in str(e):
            raise HTTPException(status_code=400, detail="A model with this name already exists")
        raise HTTPException(status_code=500, detail="Failed to create LLM model")


@router.patch("/{model_id}", response_model=LLMModelResponse)
async def update_llm_model(
    model_id: UUID,
    request: UpdateLLMModelRequest,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Update an LLM model configuration."""
    try:
        service = LLMModelsService(db)
        model = await service.update_model(
            user_id=user_id,
            model_id=model_id,
            name=request.name,
            provider=request.provider,
            model_name=request.model_name,
            config=request.config,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            is_default=request.is_default,
            is_active=request.is_active,
        )

        if not model:
            raise HTTPException(status_code=404, detail="LLM model not found")

        # Mask sensitive fields
        if model.get("config"):
            model["config"] = mask_sensitive_config(model["config"])

        return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating LLM model: {e}")
        if "llm_models_user_name_unique" in str(e):
            raise HTTPException(status_code=400, detail="A model with this name already exists")
        raise HTTPException(status_code=500, detail="Failed to update LLM model")


@router.delete("/{model_id}")
async def delete_llm_model(
    model_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Delete an LLM model configuration."""
    try:
        service = LLMModelsService(db)
        success = await service.delete_model(user_id, model_id)

        if not success:
            raise HTTPException(status_code=404, detail="LLM model not found")

        return {"success": True, "message": "LLM model deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting LLM model: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete LLM model")


@router.post("/{model_id}/set-default")
async def set_default_llm_model(
    model_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Set an LLM model as the default."""
    try:
        service = LLMModelsService(db)
        success = await service.set_default_model(user_id, model_id)

        if not success:
            raise HTTPException(status_code=404, detail="LLM model not found")

        return {"success": True, "message": "Default model updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default LLM model: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default model")


# Provider management and model discovery endpoints

class TestProviderRequest(BaseModel):
    """Request to test provider credentials."""
    provider: str = Field(..., pattern="^(openai|anthropic|ollama|custom)$")
    config: Dict[str, Any]


class ProviderModelInfo(BaseModel):
    """Information about an available model from a provider."""
    id: str
    name: str
    description: Optional[str] = None
    context_length: Optional[int] = None


class DiscoverModelsRequest(BaseModel):
    """Request to discover available models from a provider."""
    provider: str = Field(..., pattern="^(openai|anthropic|ollama|custom)$")
    config: Dict[str, Any]


class CreateBulkModelsRequest(BaseModel):
    """Request to create multiple models at once."""
    provider: str = Field(..., pattern="^(openai|anthropic|ollama|custom)$")
    config: Dict[str, Any]
    models: List[str]  # List of model IDs to create
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    set_first_as_default: bool = False


@router.post("/test-provider")
async def test_provider_credentials(
    request: TestProviderRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Test provider credentials by making a simple API call."""
    try:
        # Build a temporary adapter with the provided config
        adapter = build_adapter_from_config(
            provider=request.provider,
            model_name="test-model",  # Placeholder
            config=request.config,
            temperature=0.7,
        )

        # Try a simple completion to test the connection
        try:
            response = await asyncio.wait_for(
                adapter.complete("test", max_tokens=5),
                timeout=10.0
            )
            return {
                "success": True,
                "message": f"Successfully connected to {request.provider}",
                "provider": request.provider,
            }
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail=f"Connection to {request.provider} timed out"
            )
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
                raise HTTPException(
                    status_code=401,
                    detail=f"Authentication failed: {error_msg}"
                )
            raise HTTPException(
                status_code=400,
                detail=f"Connection failed: {error_msg}"
            )

    except LLMAdapterError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to test provider")


@router.post("/discover-models")
async def discover_available_models(
    request: DiscoverModelsRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Discover available models from a provider.

    Returns a list of model IDs/names that can be used with this provider.
    """
    try:
        if request.provider == "openai":
            return await _discover_openai_models(request.config)
        elif request.provider == "anthropic":
            return await _discover_anthropic_models(request.config)
        elif request.provider == "ollama":
            return await _discover_ollama_models(request.config)
        elif request.provider == "custom":
            # Custom providers don't have a standard way to list models
            return {
                "success": True,
                "provider": "custom",
                "models": [],
                "message": "Custom providers require manual model specification"
            }
        else:
            raise HTTPException(status_code=400, detail="Unknown provider")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to discover models: {str(e)}")


@router.post("/bulk-create")
async def bulk_create_models(
    request: CreateBulkModelsRequest,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Create multiple models at once from a provider."""
    try:
        service = LLMModelsService(db)
        created_models = []

        for idx, model_id in enumerate(request.models):
            # Generate a friendly name
            name = f"{request.provider.capitalize()} - {model_id}"

            is_default = request.set_first_as_default and idx == 0

            try:
                model = await service.create_model(
                    user_id=user_id,
                    name=name,
                    provider=request.provider,
                    model_name=model_id,
                    config=request.config,
                    temperature=request.temperature,
                    is_default=is_default,
                )
                created_models.append(model)
            except Exception as e:
                logger.warning(f"Failed to create model {model_id}: {e}")
                # Continue with other models

        return {
            "success": True,
            "created": len(created_models),
            "models": [mask_sensitive_config(m) for m in created_models],
        }

    except Exception as e:
        logger.error(f"Error bulk creating models: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk create models")


# Helper functions for model discovery

async def _discover_openai_models(config: Dict[str, Any]):
    """Discover available OpenAI models."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise HTTPException(status_code=500, detail="OpenAI package not installed")

    api_key = config.get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")

    base_url = config.get("base_url")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=10.0)

    try:
        models_response = await asyncio.wait_for(client.models.list(), timeout=10.0)
        models = [
            {
                "id": model.id,
                "name": model.id,
                "created": model.created,
            }
            for model in models_response.data
            if any(prefix in model.id for prefix in ["gpt-", "o1-", "text-"])
        ]

        return {
            "success": True,
            "provider": "openai",
            "models": models,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch OpenAI models: {str(e)}")


async def _discover_anthropic_models(config: Dict[str, Any]):
    """Discover available Anthropic models."""
    # Anthropic doesn't have a models list API, so we return the known models
    models = [
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet (Oct 2024)",
            "description": "Most intelligent model",
        },
        {
            "id": "claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku (Oct 2024)",
            "description": "Fast and efficient",
        },
        {
            "id": "claude-3-opus-20240229",
            "name": "Claude 3 Opus",
            "description": "Previous generation flagship",
        },
        {
            "id": "claude-3-sonnet-20240229",
            "name": "Claude 3 Sonnet",
            "description": "Balanced performance",
        },
        {
            "id": "claude-3-haiku-20240307",
            "name": "Claude 3 Haiku",
            "description": "Fast and compact",
        },
    ]

    return {
        "success": True,
        "provider": "anthropic",
        "models": models,
        "note": "Anthropic models are curated. Check Anthropic docs for latest models."
    }


async def _discover_ollama_models(config: Dict[str, Any]):
    """Discover available Ollama models."""
    import httpx

    base_url = config.get("base_url", "http://ollama:11434")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = [
                {
                    "id": model["name"],
                    "name": model["name"],
                    "size": model.get("size"),
                    "modified_at": model.get("modified_at"),
                }
                for model in data.get("models", [])
            ]

            return {
                "success": True,
                "provider": "ollama",
                "models": models,
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Ollama models: {str(e)}")
