import os
import structlog
import httpx

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

async def send_apns(device: dict, payload: dict) -> bool:
    """Send APNs notification (iOS) - stub for now"""
    if should_mock_delivery(device):
        logger.info(
            "apns_push_mock_delivery",
            device_id=str(device.get('id')),
            platform=device.get('platform', 'ios')
        )
        return True
    logger.warning("apns_not_implemented", device_id=str(device['id']))
    return False # TODO: Implement APNs
