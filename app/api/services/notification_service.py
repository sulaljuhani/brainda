import base64
import json
import os
import time
from typing import Optional

import httpx
import structlog

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from common.db import connect_with_json_codec

from api.metrics import push_delivery_success_total, push_delivery_failure_total

logger = structlog.get_logger()
PUSH_DELIVERY_ENABLED = os.getenv("ENABLE_PUSH_DELIVERY", "false").lower() == "true"
PLACEHOLDER_ENDPOINT_PREFIXES = ("https://example.com", "http://example.com")
PLACEHOLDER_PUSH_TOKENS = {"testauth:testkey"}


def should_mock_delivery(device: dict) -> bool:
    endpoint = (device.get("push_endpoint") or "").strip()
    token = (device.get("push_token") or "").strip()
    if not PUSH_DELIVERY_ENABLED:
        return True
    if token in PLACEHOLDER_PUSH_TOKENS:
        return True
    if endpoint and endpoint.startswith(PLACEHOLDER_ENDPOINT_PREFIXES):
        return True
    return False

async def send_reminder_notification(reminder: dict, device: dict):
    """
    Send push notification for a reminder.
    Tracks delivery in notification_delivery table.
    """
    platform = device['platform']
    
    # Build notification payload
    payload = {
        "title": reminder['title'],
        "body": reminder.get('body') or f"Reminder set for {reminder['due_at_local']}",
        "data": {
            "reminder_id": str(reminder['id']),
            "deep_link": f"vib://reminders/{reminder['id']}"
        },
        "actions": [
            {"id": "snooze_15m", "title": "Snooze 15m"},
            {"id": "snooze_1h", "title": "Snooze 1h"},
            {"id": "done", "title": "Done"},
            {"id": "open", "title": "Open Chat"}
        ],
        "ttl_seconds": 3600,
        "collapse_key": f"reminder:{reminder['id']}",
        "priority": "high"
    }
    
    # Track delivery attempt
    conn = await connect_with_json_codec(os.getenv("DATABASE_URL"))
    delivery_id = await conn.fetchval("""
        INSERT INTO notification_delivery (
            reminder_id, device_id, sent_at, status
        ) VALUES ($1, $2, NOW(), 'sent')
        RETURNING id
    """, reminder['id'], device['id'])
    
    # Send based on platform
    success = False
    error_message = None
    
    try:
        if platform == 'web':
            success = await send_web_push(device, payload)
        elif platform == 'ios':
            success = await send_apns(device, payload)
        elif platform == 'android':
            success = await send_fcm(device, payload)
        else:
            error_message = f"Unknown platform: {platform}"
        
        # Update delivery status
        if success:
            await conn.execute("""
                UPDATE notification_delivery 
                SET status = 'delivered', delivered_at = NOW()
                WHERE id = $1
            """, delivery_id)
            logger.info(
                "notification_sent",
                reminder_id=str(reminder['id']),
                device_id=str(device['id']),
                platform=platform
            )
            push_delivery_success_total.labels(platform=platform).inc()
        else:
            await conn.execute("""
                UPDATE notification_delivery 
                SET status = 'failed', error_message = $1
                WHERE id = $2
            """, error_message or "Send failed", delivery_id)
            logger.warning(
                "notification_failed",
                reminder_id=str(reminder['id']),
                device_id=str(device['id']),
                platform=platform,
                error=error_message
            )
            error_type = error_message or "unknown"
            push_delivery_failure_total.labels(platform=platform, error_type=error_type).inc()
    
    except Exception as e:
        error_message = str(e)
        await conn.execute("""
            UPDATE notification_delivery 
            SET status = 'failed', error_message = $1
            WHERE id = $2
        """, error_message, delivery_id)
        logger.error(
            "notification_exception",
            reminder_id=str(reminder['id']),
            error=error_message
        )
        push_delivery_failure_total.labels(
            platform=platform,
            error_type=type(e).__name__
        ).inc()
    
    await conn.close()
    return success

async def send_web_push(device: dict, payload: dict) -> bool:
    """Send Web Push notification using VAPID"""
    if should_mock_delivery(device):
        logger.info(
            "web_push_mock_delivery",
            device_id=str(device.get('id')),
            platform=device.get('platform', 'web')
        )
        return True

    from pywebpush import webpush
    import os
    import json
    
    try:
        subscription_info = {
            "endpoint": device['push_endpoint'],
            "keys": {
                "auth": device['push_token'].split(':')[0], # Simplified
                "p256dh": device['push_token'].split(':')[1]
            }
        }
        
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=os.getenv('VAPID_PRIVATE_KEY'),
            vapid_claims={
                "sub": f"mailto:{os.getenv('VAPID_SUBJECT')}"
            }
        )
        return True
    except Exception as e:
        logger.error("web_push_failed", error=str(e))
        return False

async def send_fcm(device: dict, payload: dict) -> bool:
    """Send FCM notification (Android)"""
    if should_mock_delivery(device):
        logger.info(
            "fcm_push_mock_delivery",
            device_id=str(device.get('id')),
            platform=device.get('platform', 'android')
        )
        return True

    import os
    
    fcm_url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Authorization": f"key={os.getenv('FCM_SERVER_KEY')}",
        "Content-Type": "application/json"
    }
    
    data = {
        "to": device['push_token'],
        "priority": "high",
        "notification": {
            "title": payload['title'],
            "body": payload['body']
        },
        "data": payload['data']
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(fcm_url, json=data, headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error("fcm_failed", error=str(e))
            return False

_APNS_KEY_ID = os.getenv("APNS_KEY_ID")
_APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")
_APNS_TOPIC = os.getenv("APNS_TOPIC")
_APNS_AUTH_KEY_PATH = os.getenv("APNS_AUTH_KEY_PATH")
_APNS_AUTH_KEY = os.getenv("APNS_AUTH_KEY")
_APNS_USE_SANDBOX = os.getenv("APNS_USE_SANDBOX", "false").lower() == "true"
_APNS_JWT_TTL = 50 * 60  # Refresh token every 50 minutes per Apple guidance
_APNS_PRIVATE_KEY: Optional[ec.EllipticCurvePrivateKey] = None
_APNS_JWT: Optional[str] = None
_APNS_JWT_EXPIRES_AT: float = 0.0


def _load_apns_private_key() -> ec.EllipticCurvePrivateKey:
    global _APNS_PRIVATE_KEY
    if _APNS_PRIVATE_KEY is not None:
        return _APNS_PRIVATE_KEY

    key_data: Optional[bytes] = None
    if _APNS_AUTH_KEY_PATH:
        try:
            with open(_APNS_AUTH_KEY_PATH, "rb") as key_file:
                key_data = key_file.read()
        except FileNotFoundError as exc:
            raise RuntimeError("APNs auth key file not found") from exc
    elif _APNS_AUTH_KEY:
        key_data = _APNS_AUTH_KEY.encode("utf-8")
    else:
        raise RuntimeError("APNS_AUTH_KEY_PATH or APNS_AUTH_KEY must be configured")

    try:
        _APNS_PRIVATE_KEY = serialization.load_pem_private_key(key_data, password=None)
        return _APNS_PRIVATE_KEY
    except ValueError as exc:
        raise RuntimeError("Failed to parse APNs auth key") from exc


def _generate_apns_jwt() -> str:
    global _APNS_JWT, _APNS_JWT_EXPIRES_AT
    now = int(time.time())
    if _APNS_JWT and now < (_APNS_JWT_EXPIRES_AT - 60):
        return _APNS_JWT

    if not _APNS_KEY_ID or not _APNS_TEAM_ID:
        raise RuntimeError("APNS_KEY_ID and APNS_TEAM_ID must be configured")

    private_key = _load_apns_private_key()

    header = {"alg": "ES256", "kid": _APNS_KEY_ID, "typ": "JWT"}
    claims = {"iss": _APNS_TEAM_ID, "iat": now}

    def _encode(segment: dict) -> bytes:
        raw = json.dumps(segment, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = b".".join((_encode(header), _encode(claims)))
    signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(signature)
    signature_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    encoded_signature = base64.urlsafe_b64encode(signature_bytes).rstrip(b"=")
    jwt_token = b".".join((signing_input, encoded_signature)).decode("utf-8")

    _APNS_JWT = jwt_token
    _APNS_JWT_EXPIRES_AT = now + _APNS_JWT_TTL
    return jwt_token


async def send_apns(device: dict, payload: dict) -> bool:
    """Send APNs notification (iOS)."""
    if should_mock_delivery(device):
        logger.info(
            "apns_push_mock_delivery",
            device_id=str(device.get('id')),
            platform=device.get('platform', 'ios')
        )
        return True

    device_token = (device.get("push_token") or "").strip()
    if not device_token:
        logger.error("apns_missing_device_token", device_id=str(device.get("id")))
        return False

    missing = [
        name
        for name, value in (
            ("APNS_KEY_ID", _APNS_KEY_ID),
            ("APNS_TEAM_ID", _APNS_TEAM_ID),
            ("APNS_TOPIC", _APNS_TOPIC),
        )
        if not value
    ]
    if missing:
        logger.error("apns_configuration_missing", missing=",".join(missing))
        return False

    try:
        auth_token = _generate_apns_jwt()
    except Exception as exc:
        logger.error("apns_auth_token_failed", error=str(exc))
        return False

    aps_payload = {
        "alert": {
            "title": payload.get("title"),
            "body": payload.get("body"),
        },
        "sound": payload.get("sound", "default"),
    }

    priority = payload.get("priority", "high")
    apns_priority = "10" if priority == "high" else "5"

    request_body = {"aps": aps_payload}
    custom_data = payload.get("data") or {}
    if custom_data:
        request_body.update(custom_data)

    actions = payload.get("actions")
    if actions:
        request_body["actions"] = actions

    endpoint_host = "https://api.sandbox.push.apple.com" if _APNS_USE_SANDBOX else "https://api.push.apple.com"
    url = f"{endpoint_host}/3/device/{device_token}"

    headers = {
        "authorization": f"bearer {auth_token}",
        "apns-topic": _APNS_TOPIC,
        "apns-priority": apns_priority,
    }

    ttl_seconds = payload.get("ttl_seconds")
    if ttl_seconds is not None:
        try:
            ttl_int = int(ttl_seconds)
            headers["apns-expiration"] = str(int(time.time()) + max(ttl_int, 0))
        except (TypeError, ValueError):
            logger.warning("apns_invalid_ttl", ttl=ttl_seconds)

    collapse_key = payload.get("collapse_key")
    if collapse_key:
        headers["apns-collapse-id"] = collapse_key[:64]

    async with httpx.AsyncClient(http2=True, timeout=10) as client:
        try:
            response = await client.post(url, json=request_body, headers=headers)
        except httpx.HTTPError as exc:
            logger.error("apns_http_error", error=str(exc))
            return False

    if response.status_code == 200:
        return True

    try:
        response_reason = response.json().get("reason")
    except ValueError:
        response_reason = response.text
    logger.warning(
        "apns_delivery_failed",
        status=response.status_code,
        reason=response_reason,
    )
    return False
