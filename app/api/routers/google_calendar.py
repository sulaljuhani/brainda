from __future__ import annotations

import os
from typing import Any, Literal, Optional
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from api.dependencies import get_current_user, get_db
from api.task_queue import get_celery_client
from common.google_calendar import (
    GoogleCalendarRepository,
    GoogleConfigurationError,
    credentials_to_dict,
    generate_state_token,
    verify_state_token,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/calendar/google", tags=["google-calendar"])


def _get_redirect_uri() -> str:
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        raise GoogleConfigurationError("GOOGLE_REDIRECT_URI is not configured")
    return redirect_uri


def _get_scopes() -> list[str]:
    scopes_env = os.getenv("GOOGLE_CALENDAR_SCOPES")
    if scopes_env:
        scopes = [scope.strip() for scope in scopes_env.split(",") if scope.strip()]
        if scopes:
            return scopes
    return ["https://www.googleapis.com/auth/calendar"]


def _build_client_config() -> dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = _get_redirect_uri()
    if not client_id or not client_secret:
        raise GoogleConfigurationError("Google OAuth client credentials are missing")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def _success_redirect() -> str:
    return os.getenv("GOOGLE_OAUTH_SUCCESS_REDIRECT", "http://localhost:3000/settings?success=google_connected")


def _failure_redirect() -> str:
    return os.getenv("GOOGLE_OAUTH_FAILURE_REDIRECT", "http://localhost:3000/settings?error=google_auth_failed")


@router.get("/connect")
async def connect_google_calendar(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Initiate the Google OAuth2 flow and return the consent URL."""

    try:
        state = generate_state_token(user_id)
        client_config = _build_client_config()
        scopes = _get_scopes()
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=_get_redirect_uri(),
        )
    except GoogleConfigurationError as exc:  # pragma: no cover - configuration errors
        logger.error("google_oauth_config_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )

    logger.info("google_oauth_start", user_id=str(user_id))
    return {"authorization_url": authorization_url, "state": state}


@router.get("/callback")
async def google_calendar_callback(
    code: str = Query(..., description="Authorization code supplied by Google"),
    state: str = Query(..., description="Opaque state token for CSRF protection"),
    db: asyncpg.Connection = Depends(get_db),
):
    """Exchange the authorization code for tokens and persist them."""

    try:
        user_id = verify_state_token(state)
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid state token")

        client_config = _build_client_config()
        scopes = _get_scopes()
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=_get_redirect_uri(),
        )
        flow.fetch_token(code=code)

        credentials = flow.credentials
        if not credentials.refresh_token:
            logger.warning("google_oauth_missing_refresh_token", user_id=str(user_id))
            raise HTTPException(
                status_code=400,
                detail="Google did not return a refresh token. Ensure 'prompt=consent' is enabled and the app is not already authorised.",
            )

        repo = GoogleCalendarRepository(db)
        await repo.save_credentials(user_id, credentials_to_dict(credentials))
        await repo.update_sync_state(
            user_id,
            sync_enabled=True,
            sync_direction="one_way",
            sync_token=None,
            google_calendar_id=None,
            last_sync_at=None,
        )
    except HTTPException:
        raise
    except GoogleConfigurationError as exc:  # pragma: no cover - configuration errors
        logger.error("google_oauth_config_error", error=str(exc))
        return RedirectResponse(url=_failure_redirect(), status_code=303)
    except Exception as exc:  # pragma: no cover - network/external errors
        logger.exception("google_oauth_callback_failed", error=str(exc))
        return RedirectResponse(url=_failure_redirect(), status_code=303)

    logger.info("google_calendar_connected", user_id=str(user_id))
    return RedirectResponse(url=_success_redirect(), status_code=303)


@router.post("/disconnect")
async def disconnect_google_calendar(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Disable Google Calendar synchronisation and remove stored credentials."""

    repo = GoogleCalendarRepository(db)
    await repo.delete_credentials_and_state(user_id)
    logger.info("google_calendar_disconnected", user_id=str(user_id))
    return {"success": True, "message": "Google Calendar disconnected"}


@router.get("/status")
async def get_sync_status(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Return the current Google Calendar synchronisation status."""

    repo = GoogleCalendarRepository(db)
    sync_state = await repo.get_sync_state(user_id)
    credentials = await repo.get_credentials(user_id)

    return {
        "connected": bool(sync_state and sync_state.get("sync_enabled") and credentials),
        "sync_direction": sync_state.get("sync_direction") if sync_state else None,
        "last_sync": sync_state.get("last_sync_at") if sync_state else None,
        "google_calendar_id": sync_state.get("google_calendar_id") if sync_state else None,
    }


@router.post("/sync")
async def trigger_manual_sync(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Queue background jobs to synchronise with Google Calendar immediately."""

    repo = GoogleCalendarRepository(db)
    sync_state = await repo.get_sync_state(user_id)
    if not sync_state or not sync_state.get("sync_enabled"):
        raise HTTPException(status_code=400, detail="Google Calendar is not connected")

    celery_client = get_celery_client()
    celery_client.send_task("worker.tasks.sync_google_calendar_push", args=[str(user_id)])
    if sync_state.get("sync_direction") == "two_way":
        celery_client.send_task("worker.tasks.sync_google_calendar_pull", args=[str(user_id)])

    logger.info("google_manual_sync_enqueued", user_id=str(user_id))
    return {"success": True}


class SyncSettingsUpdate(BaseModel):
    sync_direction: Optional[Literal["one_way", "two_way"]] = None
    sync_enabled: Optional[bool] = None


@router.patch("/settings")
async def update_sync_settings(
    payload: SyncSettingsUpdate,
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Update Google Calendar synchronisation preferences."""

    repo = GoogleCalendarRepository(db)
    existing_state = await repo.get_sync_state(user_id)
    credentials = await repo.get_credentials(user_id)

    if payload.sync_enabled is not None and payload.sync_enabled and not credentials:
        raise HTTPException(status_code=400, detail="Connect Google Calendar before enabling sync")

    updates: dict[str, Any] = {}
    if payload.sync_enabled is not None:
        updates["sync_enabled"] = payload.sync_enabled
    if payload.sync_direction is not None:
        updates["sync_direction"] = payload.sync_direction

    if not updates:
        return {
            "success": True,
            "state": existing_state,
        }

    await repo.update_sync_state(user_id, **updates)
    new_state = await repo.get_sync_state(user_id)
    logger.info(
        "google_sync_settings_updated",
        user_id=str(user_id),
        updates=updates,
    )
    return {"success": True, "state": new_state}
