from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from redis.asyncio import Redis
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticatorSelectionCriteria,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from api.dependencies import get_db, get_redis, verify_token, get_current_user
from api.services.auth_service import AuthService


RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "VIB")
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:3000")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class PasskeyRegisterBeginRequest(BaseModel):
    email: EmailStr
    display_name: str


class PasskeyRegisterCompleteRequest(BaseModel):
    user_id: UUID
    credential: dict[str, Any]
    device_name: Optional[str] = None


class PasskeyLoginCompleteRequest(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _ensure_base64url(value: str) -> str:
    if not value:
        return ""
    padded = value + "=" * (-len(value) % 4)
    raw = base64.b64decode(padded)
    return _urlsafe_b64encode(raw)


def _decode_base64(value: Optional[str]) -> bytes:
    if not value:
        return b""
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


@router.post("/register/begin")
async def begin_passkey_registration(
    payload: PasskeyRegisterBeginRequest,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    auth_service = AuthService(db)
    normalized_email = payload.email.strip().lower()
    display_label = payload.display_name.strip() or normalized_email.split("@")[0]

    user = await auth_service.get_user_by_email(normalized_email)
    if user is None:
        user = await auth_service.create_user_for_passkey(
            normalized_email,
            display_label,
        )
    else:
        user = await auth_service.ensure_user_profile(
            user,
            display_label,
        )

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(user["id"]),
        user_name=normalized_email,
        user_display_name=display_label,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    challenge_key = f"webauthn_registration_challenge:{user['id']}"
    await redis.setex(
        challenge_key,
        300,
        _urlsafe_b64encode(options.challenge),
    )

    await auth_service.log_auth_event(
        "passkey_registration_started",
        user_id=user["id"],
        metadata={"email": normalized_email},
    )

    return {
        "user_id": str(user["id"]),
        "options": options.model_dump_json() if hasattr(options, "model_dump_json") else json.dumps(options.model_dump()),
    }


@router.post("/register/complete")
async def complete_passkey_registration(
    payload: PasskeyRegisterCompleteRequest,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    challenge_key = f"webauthn_registration_challenge:{payload.user_id}"
    stored_challenge = await redis.get(challenge_key)
    if not stored_challenge:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid")

    credential_data = payload.credential
    registration_credential = RegistrationCredential(
        id=credential_data["id"],
        raw_id=_ensure_base64url(credential_data.get("rawId", "")),
        response=AuthenticatorAttestationResponse(
            client_data_json=_decode_base64(credential_data["response"].get("clientDataJSON")),
            attestation_object=_decode_base64(credential_data["response"].get("attestationObject")),
        ),
        authenticator_attachment=credential_data.get("authenticatorAttachment"),
        client_extension_results=credential_data.get("clientExtensionResults", {}),
        transports=credential_data.get("transports"),
        type=credential_data.get("type", "public-key"),
    )

    try:
        verification = verify_registration_response(
            credential=registration_credential,
            expected_challenge=_decode_base64(stored_challenge),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            require_user_verification=True,
        )
    except Exception as exc:
        await auth_service.log_auth_event(
            "passkey_registration_failed",
            user_id=payload.user_id,
            metadata={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail="Registration failed") from exc

    await auth_service.create_passkey_credential(
        user_id=payload.user_id,
        credential_id=verification.credential_id,
        public_key=_urlsafe_b64encode(verification.credential_public_key),
        sign_count=verification.sign_count,
        transports=credential_data.get("transports"),
        device_name=payload.device_name or "Unknown Device",
    )

    await auth_service.update_user(
        payload.user_id,
        {"is_active": True},
    )

    await auth_service.log_auth_event(
        "passkey_registered",
        user_id=payload.user_id,
        metadata={"device_name": payload.device_name or "Unknown Device"},
    )

    await redis.delete(challenge_key)

    return {"success": True, "message": "Passkey registered successfully"}


@router.post("/login/begin")
async def begin_passkey_login(
    redis: Redis = Depends(get_redis),
):
    options = generate_authentication_options(
        rp_id=RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    challenge_id = secrets.token_urlsafe(32)
    await redis.setex(
        f"webauthn_auth_challenge:{challenge_id}",
        300,
        _urlsafe_b64encode(options.challenge),
    )

    return {
        "challenge_id": challenge_id,
        "options": options.model_dump_json() if hasattr(options, "model_dump_json") else json.dumps(options.model_dump()),
    }


@router.post("/login/complete")
async def complete_passkey_login(
    payload: PasskeyLoginCompleteRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    auth_service = AuthService(db)

    challenge = await redis.get(f"webauthn_auth_challenge:{payload.challenge_id}")
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge expired")

    credential_data = payload.credential
    stored_credential_record = await auth_service.get_passkey_credential_by_id(credential_data["id"])
    if stored_credential_record is None:
        raise HTTPException(status_code=400, detail="Credential not found")
    stored_credential = dict(stored_credential_record)

    authentication_credential = AuthenticationCredential(
        id=credential_data["id"],
        raw_id=_ensure_base64url(credential_data.get("rawId", "")),
        response=AuthenticatorAssertionResponse(
            client_data_json=_decode_base64(credential_data["response"].get("clientDataJSON")),
            authenticator_data=_decode_base64(credential_data["response"].get("authenticatorData")),
            signature=_decode_base64(credential_data["response"].get("signature")),
            user_handle=_decode_base64(credential_data["response"].get("userHandle")),
        ),
        authenticator_attachment=credential_data.get("authenticatorAttachment"),
        client_extension_results=credential_data.get("clientExtensionResults", {}),
        type=credential_data.get("type", "public-key"),
    )

    try:
        verification = verify_authentication_response(
            credential=authentication_credential,
            expected_challenge=_decode_base64(challenge),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=base64.urlsafe_b64decode(stored_credential["public_key"] + "=" * (-len(stored_credential["public_key"]) % 4)),
            credential_current_sign_count=stored_credential["counter"],
            require_user_verification=True,
        )
    except Exception as exc:
        await auth_service.log_auth_event(
            "login_failed",
            user_id=stored_credential["user_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"error": str(exc)},
        )
        raise HTTPException(status_code=401, detail="Authentication failed") from exc

    await auth_service.update_passkey_credential(
        stored_credential["id"],
        {
            "counter": verification.new_sign_count,
            "last_used_at": datetime.now(timezone.utc),
        },
    )

    session_token = secrets.token_urlsafe(48)
    session = await auth_service.create_session(
        user_id=stored_credential["user_id"],
        token=session_token,
        device_name=stored_credential.get("device_name"),
        device_type="web",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await auth_service.log_auth_event(
        "login_success",
        user_id=stored_credential["user_id"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"device_name": stored_credential.get("device_name")},
    )

    await redis.delete(f"webauthn_auth_challenge:{payload.challenge_id}")

    return {
        "success": True,
        "session_token": session_token,
        "expires_at": session["expires_at"].isoformat(),
    }


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(verify_token),
    db: asyncpg.Connection = Depends(get_db),
):
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
        "username": user.get("display_name") or user.get("email", "").split("@")[0],
        "email": user.get("email"),
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
    }
