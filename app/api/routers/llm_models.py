"""API Router for LLM model management."""

from uuid import UUID
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import asyncpg
import logging

from api.dependencies import get_db, get_current_user
from api.services.llm_models_service import LLMModelsService

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
