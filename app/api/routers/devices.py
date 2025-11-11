from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import structlog

from api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
logger = structlog.get_logger()

class DeviceRegister(BaseModel):
    platform: str # web, ios, android
    push_token: str
    push_endpoint: Optional[str] = None # For Web Push

@router.post("/register")
async def register_device(
    data: DeviceRegister,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Register device for push notifications"""
    
    # Check if device already exists
    existing = await db.fetchrow("""
        SELECT * FROM devices 
        WHERE user_id = $1 AND platform = $2 AND push_token = $3
    """, user_id, data.platform, data.push_token)
    
    if existing:
        # Update last_seen
        await db.execute("""
            UPDATE devices SET last_seen_at = NOW() WHERE id = $1
        """, existing['id'])
        logger.info("device_updated", device_id=str(existing['id']))
        return {"success": True, "device_id": str(existing['id'])}
    
    # Register new device
    device_id = await db.fetchval("""
        INSERT INTO devices (user_id, platform, push_token, push_endpoint)
        VALUES ($1, $2, $3, $4)
        RETURNING id
    """, user_id, data.platform, data.push_token, data.push_endpoint)
    
    logger.info(
        "device_registered",
        user_id=str(user_id),
        device_id=str(device_id),
        platform=data.platform
    )
    
    return {"success": True, "device_id": str(device_id)}

@router.post("/{device_id}/unregister")
async def unregister_device(
    device_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Unregister device"""
    await db.execute("""
        DELETE FROM devices 
        WHERE id = $1 AND user_id = $2
    """, device_id, user_id)
    
    logger.info("device_unregistered", device_id=str(device_id))
    return {"success": True}

@router.post("/test")
async def test_notification(
    user_id: UUID = Depends(get_current_user),
    db = Depends(get_db)
):
    """Send test notification to all user's devices"""
    from api.services.notification_service import send_web_push, send_fcm
    
    devices = await db.fetch("""
        SELECT * FROM devices WHERE user_id = $1 AND push_token IS NOT NULL
    """, user_id)
    
    if not devices:
        raise HTTPException(status_code=404, detail="No devices registered")
    
    test_payload = {
        "title": "Test Notification",
        "body": "VIB notifications are working!",
        "data": {"test": True}
    }
    
    results = []
    for device in devices:
        if device['platform'] == 'web':
            success = await send_web_push(device, test_payload)
        elif device['platform'] == 'android':
            success = await send_fcm(device, test_payload)
        else:
            success = False
        
        results.append({
            "device_id": str(device['id']),
            "platform": device['platform'],
            "success": success
        })
    
    return {"results": results}
