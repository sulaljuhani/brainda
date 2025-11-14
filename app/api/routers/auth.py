from __future__ import annotations

import secrets
from typing import Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from asyncpg.exceptions import UniqueViolationError
from pydantic import BaseModel

from api.dependencies import get_db, verify_token, get_current_user
from api.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    display_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register_user(
    payload: UserRegisterRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
):
    """Register a new user with username and password."""
    auth_service = AuthService(db)

    # Validate username
    if len(payload.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

    if not payload.username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, hyphens, and underscores")

    # Check if username already exists
    existing_user = await auth_service.get_user_by_username(payload.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # If email provided, ensure it's not already in use
    if payload.email:
        existing_email_user = await auth_service.get_user_by_email(payload.email.strip().lower())
        if existing_email_user:
            raise HTTPException(status_code=400, detail='Email already registered')

    # Validate password length
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        # Create user
        user = await auth_service.create_user_with_password(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
        )

        # Create session
        session_token = secrets.token_urlsafe(48)
        session = await auth_service.create_session(
            user_id=user["id"],
            token=session_token,
            device_type="web",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Log registration event
        await auth_service.log_auth_event(
            "user_registered",
            user_id=user["id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"username": payload.username},
        )

        return {
            "success": True,
            "session_token": session_token,
            "expires_at": session["expires_at"].isoformat(),
            "user": {
                "id": str(user["id"]),
                "username": user["username"],
                "email": user.get("email"),
                "display_name": user.get("display_name"),
            },
        }
        except UniqueViolationError as exc:
        # Map unique constraint violations to user-friendly messages
        detail = str(exc)
        if 'users_email_key' in detail or '(email)' in detail:
            raise HTTPException(status_code=400, detail='Email already registered') from exc
        if 'idx_users_username_unique' in detail or '(username)' in detail:
            raise HTTPException(status_code=400, detail='Username already taken') from exc

        await auth_service.log_auth_event(
            'registration_failed',
            metadata={'username': payload.username, 'error': str(exc)},
        )
        raise HTTPException(status_code=500, detail='Registration failed') from exc
    except Exception as exc:
        await auth_service.log_auth_event(
            'registration_failed',
            metadata={'username': payload.username, 'error': str(exc)},
        )
        raise HTTPException(status_code=500, detail='Registration failed') from exc


@router.post("/login")
async def login_user(
    payload: UserLoginRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
):
    """Login with username and password."""
    auth_service = AuthService(db)

    # Authenticate user
    user = await auth_service.authenticate_with_password(
        payload.username,
        payload.password,
    )

    if not user:
        await auth_service.log_auth_event(
            "login_failed",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"username": payload.username, "reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create session
    session_token = secrets.token_urlsafe(48)
    session = await auth_service.create_session(
        user_id=user["id"],
        token=session_token,
        device_type="web",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Log login event
    await auth_service.log_auth_event(
        "login_success",
        user_id=user["id"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"username": payload.username},
    )

    return {
        "success": True,
        "session_token": session_token,
        "expires_at": session["expires_at"].isoformat(),
        "user": {
            "id": str(user["id"]),
            "username": user["username"],
            "email": user.get("email"),
            "display_name": user.get("display_name"),
        },
    }


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(verify_token),
    db: asyncpg.Connection = Depends(get_db),
):
    """Logout the current user."""
    auth_service = AuthService(db)

    session = await auth_service.get_session_by_token(token)
    if session:
        await auth_service.delete_session(token)
        await auth_service.log_auth_event(
            "logout",
            user_id=session["user_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {"success": True, "message": "Logged out"}

    # Legacy API token logout is a no-op
    return {"success": True, "message": "Token invalidated"}


@router.get("/users/me")
async def get_current_user_profile(
    user_id: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get current authenticated user profile."""
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return user profile with safe fields
    return {
        "id": str(user["id"]),
        "username": user["username"],  # username is required (NOT NULL)
        "email": user.get("email"),  # email is optional
        "display_name": user.get("display_name"),  # display_name is optional
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
    }

