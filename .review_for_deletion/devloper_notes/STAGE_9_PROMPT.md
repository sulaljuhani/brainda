# System Prompt: Stage 9 - Location Reminders (Geofencing)

## Context

You are implementing **Stage 9** of the Brainda project. The previous stages are **already complete**:

- ✅ Stages 0-4: MVP
- ✅ Stage 5: Mobile app with full idempotency
- ✅ Stage 6: Internal calendar
- ✅ Stage 7: Google Calendar sync
- ✅ Stage 8: Passkey authentication

## Your Mission: Stage 9

Implement **location-based reminders** using geofencing:
- "Remind me to buy milk when I'm near the grocery store"
- Mobile app monitors user location in background
- Triggers notification when entering/exiting geofence

## ⚠️ CRITICAL DECISION GATE

**DO NOT PROCEED** unless ALL conditions are met:

- [ ] **100+ users requesting it**: Is there real demand?
- [ ] **Battery testing complete**: Measured impact <5% daily battery drain
- [ ] **Privacy policy updated**: Location tracking disclosure added
- [ ] **Fallback implemented**: Manual "check location" button works first
- [ ] **Risk acceptance**: You understand location tracking is HIGH RISK feature

**Why this is HIGH RISK**:
1. **Battery drain**: Background location monitoring kills battery
2. **Privacy concerns**: Continuous location tracking is invasive
3. **Permission fatigue**: Users increasingly deny location permissions
4. **Accuracy issues**: GPS unreliable indoors, tunnels, dense cities
5. **Regulatory**: GDPR/CCPA require strict controls for location data

**Recommended Alternative**: Implement **manual location check** first:
- User taps "Check Location Reminders" button
- App gets current location once (foreground only)
- Shows nearby reminders: "You're near grocery store - reminder: buy milk"
- No background tracking, no battery drain

---

## Deliverables (If Proceeding Despite Warnings)

### 1. Database Schema

Already exists from MVP (`locations` table). Add location reminder fields:

```sql
-- migrations/007_add_location_reminders.sql

-- Update reminders table
ALTER TABLE reminders
ADD COLUMN location_id UUID REFERENCES locations(id) ON DELETE SET NULL,
ADD COLUMN geofence_event TEXT,  -- enter, exit, dwell
ADD COLUMN dwell_time_minutes INTEGER DEFAULT 5;  -- Min time inside geofence

-- Location trigger log (audit trail)
CREATE TABLE location_triggers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reminder_id UUID NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    trigger_lat NUMERIC(10, 7),
    trigger_lon NUMERIC(10, 7),
    trigger_accuracy_m NUMERIC(8, 2),
    event_type TEXT NOT NULL,  -- enter, exit, dwell
    triggered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_location_triggers_reminder ON location_triggers(reminder_id);
CREATE INDEX idx_location_triggers_user ON location_triggers(user_id, triggered_at);
```

---

### 2. Backend API

#### A. Location Management

**File**: `app/api/routers/locations.py`

```python
from fastapi import APIRouter, Depends
from app.api.models.location import LocationCreate, LocationUpdate

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])

@router.post("")
async def create_location(
    location: LocationCreate,
    current_user = Depends(get_current_user),
):
    """
    Create a named location for geofencing.

    Example:
    {
        "name": "Grocery Store",
        "lat": 24.4539,
        "lon": 54.3773,
        "radius_m": 100
    }
    """

    # Validate coordinates
    if not (-90 <= location.lat <= 90) or not (-180 <= location.lon <= 180):
        return tool_error("VALIDATION_ERROR", "Invalid coordinates")

    # Create location
    loc = await db.create_location(
        user_id=current_user.id,
        name=location.name,
        lat=location.lat,
        lon=location.lon,
        radius_m=location.radius_m or 100,
    )

    return {"success": True, "data": loc.to_dict()}


@router.get("")
async def list_locations(current_user = Depends(get_current_user)):
    """List all user locations."""
    locations = await db.list_locations(current_user.id)
    return {"data": locations}


@router.patch("/{location_id}")
async def update_location(
    location_id: UUID,
    update: LocationUpdate,
    current_user = Depends(get_current_user),
):
    """Update location details."""
    location = await db.get_location(location_id)

    if not location or location.user_id != current_user.id:
        return tool_error("NOT_FOUND", "Location not found")

    updated = await db.update_location(location_id, update.dict(exclude_none=True))
    return {"success": True, "data": updated.to_dict()}
```

#### B. Location Reminder Creation

**File**: `app/api/tools/reminders.py` (extend existing)

```python
@tool(schema_version="1.1")
async def create_location_reminder(
    title: str,
    location_id: UUID,
    user_id: UUID,
    geofence_event: str = "enter",  # enter, exit, dwell
    dwell_time_minutes: int = 5,
) -> dict:
    """
    Create a location-based reminder.

    Args:
        title: Reminder text
        location_id: ID of saved location
        geofence_event: Trigger on enter, exit, or dwell
        dwell_time_minutes: For dwell events, min time inside geofence
    """

    # Validate location
    location = await db.get_location(location_id)
    if not location or location.user_id != user_id:
        return tool_error("NOT_FOUND", "Location not found")

    # Validate event type
    if geofence_event not in ["enter", "exit", "dwell"]:
        return tool_error("VALIDATION_ERROR", "Invalid geofence_event", "geofence_event")

    # Create reminder (no due_at_utc for location reminders)
    reminder = await db.create_reminder(
        user_id=user_id,
        title=title,
        location_id=location_id,
        geofence_event=geofence_event,
        dwell_time_minutes=dwell_time_minutes,
        status="active",
    )

    return tool_success(reminder.to_dict())
```

#### C. Location Check Endpoint

**File**: `app/api/routers/reminders.py` (extend existing)

```python
@router.post("/check-location")
async def check_location_reminders(
    lat: float,
    lon: float,
    accuracy: float,  # GPS accuracy in meters
    current_user = Depends(get_current_user),
):
    """
    Check if user is near any location reminders.
    Called by mobile app (foreground or background).

    Returns list of reminders that should fire based on current location.
    """

    # Get all active location reminders for user
    reminders = await db.get_location_reminders(current_user.id, status="active")

    nearby_reminders = []

    for reminder in reminders:
        location = await db.get_location(reminder.location_id)

        # Calculate distance
        distance = haversine_distance(lat, lon, location.lat, location.lon)

        # Check if inside geofence
        inside = distance <= location.radius_m

        # Determine if should trigger
        should_trigger = False

        if reminder.geofence_event == "enter" and inside:
            # Check if we weren't inside before (requires state tracking)
            prev_state = await redis.get(f"geofence:{reminder.id}")
            if prev_state != "inside":
                should_trigger = True
                await redis.set(f"geofence:{reminder.id}", "inside", ex=3600)

        elif reminder.geofence_event == "exit" and not inside:
            prev_state = await redis.get(f"geofence:{reminder.id}")
            if prev_state == "inside":
                should_trigger = True
                await redis.delete(f"geofence:{reminder.id}")

        elif reminder.geofence_event == "dwell" and inside:
            # Track dwell time
            dwell_key = f"geofence_dwell:{reminder.id}"
            dwell_start = await redis.get(dwell_key)

            if not dwell_start:
                # First time inside, start dwell timer
                await redis.set(dwell_key, datetime.utcnow().isoformat(), ex=7200)
            else:
                # Check if dwell time met
                elapsed = (datetime.utcnow() - datetime.fromisoformat(dwell_start)).total_seconds() / 60
                if elapsed >= reminder.dwell_time_minutes:
                    should_trigger = True
                    await redis.delete(dwell_key)

        if should_trigger:
            # Log trigger
            await db.create_location_trigger(
                reminder_id=reminder.id,
                location_id=location.id,
                user_id=current_user.id,
                trigger_lat=lat,
                trigger_lon=lon,
                trigger_accuracy_m=accuracy,
                event_type=reminder.geofence_event,
            )

            nearby_reminders.append({
                "reminder": reminder.to_dict(),
                "location": location.to_dict(),
                "distance_m": round(distance, 1),
            })

    return {
        "success": True,
        "reminders": nearby_reminders,
        "count": len(nearby_reminders),
    }


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """
    Calculate distance between two coordinates in meters.
    Uses Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371000  # Earth radius in meters

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c
```

---

### 3. Mobile App (React Native)

#### A. Geofencing Service (iOS)

**File**: `src/services/geofencing.ios.ts`

```typescript
import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import api from '../lib/api';

const GEOFENCE_TASK = 'GEOFENCE_BACKGROUND_TASK';

// Define background task
TaskManager.defineTask(GEOFENCE_TASK, async ({ data: { eventType, region }, error }) => {
  if (error) {
    console.error('Geofence error:', error);
    return;
  }

  console.log('Geofence event:', eventType, region);

  // Get current location
  const location = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.Balanced,
  });

  // Check with server
  try {
    const response = await api.post('/reminders/check-location', {
      lat: location.coords.latitude,
      lon: location.coords.longitude,
      accuracy: location.coords.accuracy,
    });

    // Send notifications for triggered reminders
    for (const item of response.data.reminders) {
      await Notifications.scheduleNotificationAsync({
        content: {
          title: item.reminder.title,
          body: `You're near ${item.location.name} (${item.distance_m}m away)`,
        },
        trigger: null, // Immediate
      });
    }
  } catch (error) {
    console.error('Failed to check location reminders:', error);
  }
});

export async function startGeofencing(locations: Array<{ lat: number; lon: number; radius: number; identifier: string }>) {
  // Request permissions
  const { status } = await Location.requestBackgroundPermissionsAsync();

  if (status !== 'granted') {
    throw new Error('Background location permission denied');
  }

  // Start geofencing
  await Location.startGeofencingAsync(GEOFENCE_TASK, locations.map(loc => ({
    latitude: loc.lat,
    longitude: loc.lon,
    radius: loc.radius,
    identifier: loc.identifier,
  })));

  console.log('Geofencing started for', locations.length, 'locations');
}

export async function stopGeofencing() {
  await Location.stopGeofencingAsync(GEOFENCE_TASK);
  console.log('Geofencing stopped');
}
```

#### B. Manual Check (Foreground Only)

**File**: `src/screens/LocationRemindersScreen.tsx`

```typescript
import React, { useState } from 'react';
import { View, Text, Button, FlatList } from 'react-native';
import * as Location from 'expo-location';
import api from '../lib/api';

export default function LocationRemindersScreen() {
  const [checking, setChecking] = useState(false);
  const [nearby, setNearby] = useState([]);

  const checkLocation = async () => {
    setChecking(true);

    try {
      // Request foreground permission
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        alert('Location permission denied');
        return;
      }

      // Get current location
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      // Check with server
      const response = await api.post('/reminders/check-location', {
        lat: location.coords.latitude,
        lon: location.coords.longitude,
        accuracy: location.coords.accuracy,
      });

      setNearby(response.data.reminders);

      if (response.data.count === 0) {
        alert('No location reminders nearby');
      }
    } catch (error) {
      console.error('Location check failed:', error);
      alert('Failed to check location');
    } finally {
      setChecking(false);
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 16 }}>
        Location Reminders
      </Text>

      <Button
        title={checking ? 'Checking...' : 'Check My Location'}
        onPress={checkLocation}
        disabled={checking}
      />

      <FlatList
        data={nearby}
        keyExtractor={(item, index) => index.toString()}
        renderItem={({ item }) => (
          <View style={{ padding: 12, backgroundColor: '#f0f0f0', marginTop: 8, borderRadius: 8 }}>
            <Text style={{ fontWeight: 'bold' }}>{item.reminder.title}</Text>
            <Text>📍 {item.location.name}</Text>
            <Text style={{ color: '#666' }}>{item.distance_m}m away</Text>
          </View>
        )}
      />

      {nearby.length === 0 && (
        <Text style={{ marginTop: 16, color: '#999', textAlign: 'center' }}>
          Tap button to check for nearby reminders
        </Text>
      )}
    </View>
  );
}
```

---

## Acceptance Criteria

### Backend

- [ ] Can create location: "Grocery Store" at lat/lon with 100m radius
- [ ] Can create location reminder: "Buy milk when I enter grocery store"
- [ ] `/check-location` endpoint calculates distance correctly (±10m accuracy)
- [ ] "Enter" event triggers only once when entering geofence
- [ ] "Exit" event triggers when leaving geofence
- [ ] "Dwell" event triggers after 5 minutes inside geofence
- [ ] Location triggers logged in `location_triggers` table

### Mobile (Manual Check)

- [ ] "Check My Location" button requests foreground permission
- [ ] Nearby reminders displayed with distance
- [ ] No background location tracking (preserves battery)
- [ ] Works offline: queues check for when connection returns

### Mobile (Background Geofencing)

**Only test if proceeding with full implementation**:

- [ ] Background location permission requested and explained
- [ ] Geofence monitoring starts with max 20 regions (iOS limit)
- [ ] Battery drain measured: <5% per day with 10 active geofences
- [ ] Notification fires when entering geofence
- [ ] App killed: geofence still works (iOS/Android background task)

---

## Privacy & Compliance

### Required Disclosures

**Privacy Policy** must include:

```
Location Data Usage

Brainda collects and processes your location data when you:
1. Manually check nearby location reminders (one-time access)
2. Enable background geofencing for automatic location reminders

Location data is:
- Processed on your device and our server
- Stored with location triggers for audit purposes
- Never shared with third parties
- Retained for 90 days, then deleted

You can disable location features at any time in Settings.

Battery Impact: Background geofencing may reduce battery life by 5-10%.
```

**iOS Info.plist**:

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Brainda needs your location to check nearby reminders when you tap "Check My Location".</string>

<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>Brainda needs background location access to automatically notify you of nearby reminders. This may impact battery life.</string>
```

**Android AndroidManifest.xml**:

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
```

---

## Battery Optimization Strategies

If proceeding with background geofencing:

1. **Limit geofence count**: Max 20 active geofences (iOS limit)
2. **Larger radius**: Use 100-200m, not 10m (fewer false triggers)
3. **Dwell filtering**: Require 5+ minutes inside to avoid driving-by triggers
4. **Smart scheduling**: Only monitor 9am-9pm, sleep at night
5. **Accuracy trade-off**: Use `Balanced` accuracy, not `High`
6. **Deduplication**: Don't trigger same reminder twice in 1 hour

**Measurement**:

```typescript
// Battery tracking
import * as Battery from 'expo-battery';

const batteryLevel = await Battery.getBatteryLevelAsync();
// Log to analytics: correlate with geofence activity
```

---

## Testing Strategy

### Manual Testing

**Test 1: Create Location Reminder**

1. Add location: "Coffee Shop" at your current coordinates + 100m radius
2. Create reminder: "Grab coffee when near coffee shop"
3. Walk toward coffee shop
4. Tap "Check My Location" when <100m away
5. Verify: Reminder appears in nearby list

**Test 2: Enter Geofence (Background)**

1. Enable background geofencing (if implemented)
2. Create reminder: "Enter test" for location
3. Walk outside geofence (>150m away)
4. Walk inside geofence
5. Verify: Notification fires within 2 minutes

**Test 3: Dwell Time**

1. Create reminder: "Dwell test" with 5min dwell time
2. Enter geofence, wait 5 minutes
3. Verify: Notification fires after 5 minutes, not immediately

**Test 4: Battery Drain**

1. Charge phone to 100%
2. Enable geofencing with 5 locations
3. Use phone normally for 24 hours
4. Check battery usage: Brainda should be <5%

---

## Risk Checklist

- [ ] **Battery drain**: Measured and documented, <5% daily
- [ ] **Permission denial**: Fallback to manual check works
- [ ] **GPS accuracy**: Tested in urban areas, indoors, tunnels
- [ ] **False triggers**: Dwell time and radius tuned to avoid noise
- [ ] **Privacy**: Location data retention policy enforced (90 days)
- [ ] **Regulatory**: GDPR/CCPA compliance verified

---

## Success Metrics

After 1 month (if implemented):

- **Adoption**: >40% of users create at least one location reminder
- **Battery**: <5% daily drain from geofencing
- **Accuracy**: >90% of triggers fire within 50m of geofence boundary
- **Complaints**: <10% of users complain about battery drain

---

## Alternative: Manual Check Only (RECOMMENDED)

If risks too high, implement **manual check only**:

- User taps button to check location
- Foreground permission only
- No background tracking
- No battery drain
- Still useful: "Show me nearby reminders"

**Acceptance Criteria**:

- [ ] "Check My Location" button works
- [ ] Shows reminders within 500m radius
- [ ] No background location access requested
- [ ] Battery impact: <0.1% per check

---

## Remember

**DO NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

⚠️ **FINAL WARNING**: Location reminders are HIGH RISK. Consider carefully before implementing.

Good luck! 🚀
