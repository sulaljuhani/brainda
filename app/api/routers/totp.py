from __future__ import annotations

import base64
import io
import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import asyncpg
import bcrypt
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.dependencies import get_current_user, get_db
from api.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TotpVerifyRequest(BaseModel):
    code: str


class TotpAuthenticateRequest(BaseModel):
    user_id: UUID
    code: str


@router.post("/totp/setup")
async def setup_totp(
    current_user: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(current_user)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    secret = pyotp.random_base32()
    backup_codes = [secrets.token_hex(4) for _ in range(10)]

    await auth_service.create_totp_secret(
        user_id=current_user,
        secret=secret,
        backup_codes=backup_codes,
        enabled=False,
    )

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user["email"],
        issuer_name="Brainda",
    )

    qr = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    await auth_service.log_auth_event(
        "totp_setup_started",
        user_id=current_user,
    )

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "backup_codes": backup_codes,
    }


@router.post("/totp/verify")
async def verify_totp(
    payload: TotpVerifyRequest,
    current_user: UUID = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    auth_service = AuthService(db)
    totp_record = await auth_service.get_totp_secret(current_user)
    if totp_record is None:
        raise HTTPException(status_code=400, detail="TOTP not set up")

    totp = pyotp.TOTP(totp_record["secret"])
    if not totp.verify(payload.code, valid_window=1):
        await auth_service.log_auth_event(
            "totp_verify_failed",
            user_id=current_user,
        )
        raise HTTPException(status_code=400, detail="Invalid code")

    await auth_service.update_totp_secret(
        totp_record["id"],
        {
            "enabled": True,
            "verified_at": datetime.now(timezone.utc),
        },
    )

    await auth_service.log_auth_event(
        "totp_enabled",
        user_id=current_user,
    )

    return {"success": True, "message": "TOTP enabled"}


@router.post("/totp/authenticate")
async def authenticate_with_totp(
    payload: TotpAuthenticateRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
):
    auth_service = AuthService(db)
    totp_record = await auth_service.get_totp_secret(payload.user_id)
    if totp_record is None or not totp_record["enabled"]:
        raise HTTPException(status_code=400, detail="TOTP not enabled")

    totp_data = dict(totp_record)
    totp = pyotp.TOTP(totp_data["secret"])

    ip_address: Optional[str] = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if totp.verify(payload.code, valid_window=1):
        session_token, session = await _create_session(auth_service, payload.user_id, ip_address, user_agent)
        await auth_service.log_auth_event(
            "login_success_totp",
            user_id=payload.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"method": "totp"},
        )
        return {
            "success": True,
            "session_token": session_token,
            "expires_at": session["expires_at"].isoformat(),
        }

    hashed_codes = totp_data.get("backup_codes") or []
    for index, hashed in enumerate(hashed_codes):
        if bcrypt.checkpw(payload.code.encode("utf-8"), hashed.encode("utf-8")):
            remaining = hashed_codes[:index] + hashed_codes[index + 1 :]
            await auth_service.update_totp_secret(
                totp_data["id"],
                {"backup_codes": remaining},
            )
            session_token, session = await _create_session(auth_service, payload.user_id, ip_address, user_agent)
            await auth_service.log_auth_event(
                "login_success_backup_code",
                user_id=payload.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"remaining_backup_codes": len(remaining)},
            )
            return {
                "success": True,
                "session_token": session_token,
                "expires_at": session["expires_at"].isoformat(),
                "message": f"Backup code used. {len(remaining)} remaining.",
            }

    await auth_service.log_auth_event(
        "login_failed_totp",
        user_id=payload.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    raise HTTPException(status_code=401, detail="Invalid code")


async def _create_session(
    auth_service: AuthService,
    user_id: UUID,
    ip_address: Optional[str],
    user_agent: Optional[str],
):
    session_token = secrets.token_urlsafe(48)
    session = await auth_service.create_session(
        user_id=user_id,
        token=session_token,
        device_type="web",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return session_token, session
