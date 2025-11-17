# System Prompt: Stage 7 - Google Calendar Sync

## Context

You are implementing **Stage 7** of the Brainda project. The previous stages are **already complete**:

- ✅ Stages 0-4: MVP
- ✅ Stage 5: Mobile app with full idempotency
- ✅ Stage 6: Internal calendar with RRULE and weekly views

## Your Mission: Stage 7

Build **Google Calendar synchronization** with:
- OAuth2 authentication flow
- One-way sync (internal → Google Calendar)
- Optional two-way sync with conflict resolution
- Incremental sync using sync tokens

## Why This Stage Matters

Users want to:
- **Consolidate schedules**: See Brainda events in their main Google Calendar
- **Share availability**: Google Calendar is their "source of truth" for external meetings
- **Reduce friction**: Don't maintain two separate calendars
- **Preserve existing workflow**: Keep using Google Calendar for work/school events

---

## Deliverables

### 1. Google Cloud Project Setup

#### A. Create OAuth2 Credentials

**Manual Steps** (document for users):

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Brainda Calendar Sync"
3. Enable Google Calendar API
4. Create OAuth2 credentials:
   - Application type: Web application
   - Authorized redirect URIs:
     - `http://localhost:8000/api/v1/calendar/google/callback`
     - `https://yourdomain.com/api/v1/calendar/google/callback`
5. Download `client_secret.json`
6. Add to `.env`:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=https://yourdomain.com/api/v1/calendar/google/callback
   ```

#### B. Required Scopes

```python
GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",  # Full access
    "https://www.googleapis.com/auth/calendar.events",  # Events only
]

# For one-way sync (safer, recommended):
GOOGLE_CALENDAR_SCOPES_READONLY = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
```

---

### 2. Backend Implementation

#### A. OAuth2 Flow

**File**: `app/api/routers/google_calendar.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os

router = APIRouter(prefix="/api/v1/calendar/google", tags=["google-calendar"])

# OAuth2 flow configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
    }
}


@router.get("/connect")
async def connect_google_calendar(current_user = Depends(get_current_user)):
    """
    Initiate OAuth2 flow.
    Returns authorization URL for user to visit.
    """
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI"),
    )

    # Generate state token for CSRF protection
    state = generate_state_token(current_user.id)

    authorization_url, _ = flow.authorization_url(
        access_type='offline',  # Get refresh token
        include_granted_scopes='true',
        state=state,
        prompt='consent',  # Force consent to get refresh token
    )

    return {
        "authorization_url": authorization_url,
        "state": state,
    }


@router.get("/callback")
async def google_calendar_callback(
    code: str,
    state: str,
):
    """
    OAuth2 callback handler.
    Exchanges authorization code for access + refresh tokens.
    """
    # Verify state token
    user_id = verify_state_token(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state token")

    # Exchange code for tokens
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI"),
    )
    flow.fetch_token(code=code)

    credentials = flow.credentials

    # Save tokens to database
    await db.save_google_credentials(
        user_id=user_id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        scopes=credentials.scopes,
        expiry=credentials.expiry,
    )

    # Initialize sync state
    await db.update_calendar_sync_state(
        user_id=user_id,
        sync_enabled=True,
        sync_direction='one_way',  # Default to one-way
        last_sync_at=None,
    )

    logger.info("google_calendar_connected", extra={"user_id": str(user_id)})

    return {"success": True, "message": "Google Calendar connected successfully"}


@router.post("/disconnect")
async def disconnect_google_calendar(current_user = Depends(get_current_user)):
    """Disconnect Google Calendar sync."""

    await db.update_calendar_sync_state(
        user_id=current_user.id,
        sync_enabled=False,
    )

    await db.delete_google_credentials(current_user.id)

    return {"success": True, "message": "Google Calendar disconnected"}


@router.get("/status")
async def get_sync_status(current_user = Depends(get_current_user)):
    """Get current sync status."""

    sync_state = await db.get_calendar_sync_state(current_user.id)

    return {
        "connected": sync_state.sync_enabled if sync_state else False,
        "sync_direction": sync_state.sync_direction if sync_state else None,
        "last_sync": sync_state.last_sync_at if sync_state else None,
    }
```

#### B. One-Way Sync (Internal → Google)

**File**: `app/worker/tasks/google_calendar_sync.py`

```python
from celery import shared_task
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime

@shared_task
def sync_to_google_calendar(user_id: str):
    """
    One-way sync: Push Brainda events to Google Calendar.

    Strategy:
    1. Fetch all internal events (source='internal')
    2. For each event:
       - If google_event_id is NULL: create in Google
       - If google_event_id exists: update in Google
    3. Mark events with status='cancelled' as deleted in Google
    """

    # Get user's Google credentials
    creds_data = await db.get_google_credentials(user_id)
    if not creds_data:
        logger.warning("google_sync_no_credentials", extra={"user_id": user_id})
        return

    # Build Google Calendar client
    creds = Credentials(
        token=creds_data["access_token"],
        refresh_token=creds_data["refresh_token"],
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"],
    )

    service = build('calendar', 'v3', credentials=creds)

    # Get or create dedicated Brainda calendar
    calendar_id = await get_or_create_vib_calendar(service, user_id)

    # Fetch internal events to sync
    internal_events = await db.get_calendar_events(
        user_id=user_id,
        source='internal',
    )

    synced = 0
    errors = 0

    for event in internal_events:
        try:
            if event.status == 'cancelled' and event.google_event_id:
                # Delete from Google
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=event.google_event_id,
                ).execute()

                logger.info("google_event_deleted", extra={
                    "event_id": str(event.id),
                    "google_event_id": event.google_event_id,
                })

            elif not event.google_event_id:
                # Create in Google
                google_event = to_google_event_format(event)
                created = service.events().insert(
                    calendarId=calendar_id,
                    body=google_event,
                ).execute()

                # Save Google event ID
                await db.update_calendar_event(event.id, {
                    "google_event_id": created['id'],
                    "google_calendar_id": calendar_id,
                })

                synced += 1
                logger.info("google_event_created", extra={
                    "event_id": str(event.id),
                    "google_event_id": created['id'],
                })

            else:
                # Update in Google
                google_event = to_google_event_format(event)
                service.events().update(
                    calendarId=calendar_id,
                    eventId=event.google_event_id,
                    body=google_event,
                ).execute()

                synced += 1
                logger.info("google_event_updated", extra={
                    "event_id": str(event.id),
                    "google_event_id": event.google_event_id,
                })

        except Exception as e:
            errors += 1
            logger.error("google_sync_error", extra={
                "event_id": str(event.id),
                "error": str(e),
            })

    # Update sync state
    await db.update_calendar_sync_state(
        user_id=user_id,
        last_sync_at=datetime.utcnow(),
    )

    logger.info("google_sync_completed", extra={
        "user_id": user_id,
        "synced": synced,
        "errors": errors,
    })

    return {"synced": synced, "errors": errors}


async def get_or_create_vib_calendar(service, user_id: str) -> str:
    """
    Get or create a dedicated 'Brainda' calendar in Google.
    Prevents polluting the user's primary calendar.
    """
    # Check if we already have a calendar_id stored
    sync_state = await db.get_calendar_sync_state(user_id)
    if sync_state and sync_state.google_calendar_id:
        return sync_state.google_calendar_id

    # Search for existing Brainda calendar
    calendars = service.calendarList().list().execute()
    for cal in calendars.get('items', []):
        if cal['summary'] == 'Brainda':
            calendar_id = cal['id']
            await db.update_calendar_sync_state(
                user_id=user_id,
                google_calendar_id=calendar_id,
            )
            return calendar_id

    # Create new calendar
    calendar_body = {
        'summary': 'Brainda',
        'description': 'Events synced from Brainda personal assistant',
        'timeZone': 'UTC',
    }

    created = service.calendars().insert(body=calendar_body).execute()
    calendar_id = created['id']

    await db.update_calendar_sync_state(
        user_id=user_id,
        google_calendar_id=calendar_id,
    )

    logger.info("vib_calendar_created", extra={
        "user_id": user_id,
        "calendar_id": calendar_id,
    })

    return calendar_id


def to_google_event_format(event) -> dict:
    """
    Convert Brainda event to Google Calendar API format.
    """
    google_event = {
        'summary': event.title,
        'description': event.description or '',
        'start': {
            'dateTime': event.starts_at.isoformat(),
            'timeZone': event.timezone,
        },
        'end': {
            'dateTime': (event.ends_at or event.starts_at).isoformat(),
            'timeZone': event.timezone,
        },
    }

    if event.location_text:
        google_event['location'] = event.location_text

    if event.rrule:
        google_event['recurrence'] = [f'RRULE:{event.rrule}']

    return google_event
```

#### C. Two-Way Sync (Optional)

**File**: `app/worker/tasks/google_calendar_sync.py` (continued)

```python
@shared_task
def sync_from_google_calendar(user_id: str):
    """
    Two-way sync: Pull Google Calendar events to Brainda.

    Strategy:
    1. Use incremental sync with sync tokens
    2. For each Google event:
       - If not in Brainda: create with source='google'
       - If in Brainda: check updated_at, apply conflict resolution
    3. Handle deletions
    """

    creds_data = await db.get_google_credentials(user_id)
    if not creds_data:
        return

    creds = Credentials(**creds_data)
    service = build('calendar', 'v3', credentials=creds)

    sync_state = await db.get_calendar_sync_state(user_id)
    calendar_id = sync_state.google_calendar_id

    # Incremental sync using sync token
    sync_token = sync_state.sync_token if sync_state else None

    try:
        if sync_token:
            # Incremental sync (only changes since last sync)
            events_result = service.events().list(
                calendarId=calendar_id,
                syncToken=sync_token,
            ).execute()
        else:
            # Full sync (first time)
            events_result = service.events().list(
                calendarId=calendar_id,
                maxResults=2500,
            ).execute()

        google_events = events_result.get('items', [])
        new_sync_token = events_result.get('nextSyncToken')

        # Process events
        for google_event in google_events:
            await process_google_event(user_id, google_event, calendar_id)

        # Save new sync token
        await db.update_calendar_sync_state(
            user_id=user_id,
            sync_token=new_sync_token,
            last_sync_at=datetime.utcnow(),
        )

        logger.info("google_import_completed", extra={
            "user_id": user_id,
            "events_processed": len(google_events),
        })

    except Exception as e:
        logger.error("google_import_error", extra={
            "user_id": user_id,
            "error": str(e),
        })


async def process_google_event(user_id: str, google_event: dict, calendar_id: str):
    """
    Process a single Google Calendar event.

    Conflict resolution strategy:
    - If event exists in Brainda with source='google': update from Google (Google wins)
    - If event exists with source='internal': skip (user created it in Brainda, don't overwrite)
    - If deleted in Google: mark as cancelled in Brainda
    """

    google_event_id = google_event['id']
    status = google_event.get('status', 'confirmed')

    # Check if event exists in Brainda
    existing = await db.get_calendar_event_by_google_id(google_event_id)

    if status == 'cancelled':
        # Event deleted in Google
        if existing:
            await db.update_calendar_event(existing.id, {"status": "cancelled"})
            logger.info("google_event_deleted_locally", extra={"event_id": str(existing.id)})
        return

    # Parse Google event
    vib_event = from_google_event_format(google_event, user_id, calendar_id)

    if not existing:
        # Create new event in Brainda
        created = await db.create_calendar_event(**vib_event)
        logger.info("google_event_imported", extra={"event_id": str(created.id)})

    elif existing.source == 'google':
        # Update from Google (Google is source of truth)
        await db.update_calendar_event(existing.id, vib_event)
        logger.info("google_event_updated_locally", extra={"event_id": str(existing.id)})

    else:
        # Event exists with source='internal'
        # Conflict! Apply resolution strategy

        # Strategy 1: Last-write-wins (use updated_at)
        google_updated = datetime.fromisoformat(google_event['updated'].replace('Z', '+00:00'))
        if google_updated > existing.updated_at:
            # Google version is newer
            await db.update_calendar_event(existing.id, vib_event)
            logger.info("google_event_conflict_resolved", extra={
                "event_id": str(existing.id),
                "resolution": "google_wins",
            })
        else:
            # Brainda version is newer, skip update
            logger.info("google_event_conflict_resolved", extra={
                "event_id": str(existing.id),
                "resolution": "vib_wins",
            })


def from_google_event_format(google_event: dict, user_id: str, calendar_id: str) -> dict:
    """
    Convert Google Calendar event to Brainda format.
    """
    start = google_event['start'].get('dateTime', google_event['start'].get('date'))
    end = google_event['end'].get('dateTime', google_event['end'].get('date'))

    return {
        "user_id": user_id,
        "title": google_event['summary'],
        "description": google_event.get('description'),
        "starts_at": datetime.fromisoformat(start.replace('Z', '+00:00')),
        "ends_at": datetime.fromisoformat(end.replace('Z', '+00:00')) if end else None,
        "timezone": google_event['start'].get('timeZone', 'UTC'),
        "location_text": google_event.get('location'),
        "rrule": parse_google_recurrence(google_event.get('recurrence')),
        "source": "google",
        "google_event_id": google_event['id'],
        "google_calendar_id": calendar_id,
        "status": google_event.get('status', 'confirmed'),
    }


def parse_google_recurrence(recurrence: list) -> str:
    """
    Extract RRULE from Google's recurrence array.
    Google format: ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    """
    if not recurrence:
        return None

    for rule in recurrence:
        if rule.startswith('RRULE:'):
            return rule[6:]  # Strip "RRULE:" prefix

    return None
```

#### D. Scheduled Sync

**File**: `app/worker/celeryconfig.py`

```python
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # ... existing schedules ...

    'sync-google-calendar-one-way': {
        'task': 'app.worker.tasks.google_calendar_sync.sync_to_google_calendar',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },

    'sync-google-calendar-two-way': {
        'task': 'app.worker.tasks.google_calendar_sync.sync_from_google_calendar',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        # Only runs for users with two_way sync enabled
    },
}
```

---

### 3. Frontend UI

#### A. Connection Flow (Web)

**File**: `app/web/components/GoogleCalendarConnect.tsx`

```typescript
import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export default function GoogleCalendarConnect() {
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ['google-calendar-status'],
    queryFn: async () => {
      const response = await api.get('/calendar/google/status');
      return response.data;
    },
  });

  const connect = useMutation({
    mutationFn: async () => {
      const response = await api.get('/calendar/google/connect');
      return response.data;
    },
    onSuccess: (data) => {
      // Redirect to Google OAuth page
      window.location.href = data.authorization_url;
    },
  });

  const disconnect = useMutation({
    mutationFn: async () => {
      const response = await api.post('/calendar/google/disconnect');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-calendar-status'] });
    },
  });

  const triggerSync = useMutation({
    mutationFn: async () => {
      const response = await api.post('/calendar/google/sync');
      return response.data;
    },
  });

  if (!status) return <div>Loading...</div>;

  return (
    <div className="google-calendar-settings">
      <h3>Google Calendar Sync</h3>

      {status.connected ? (
        <div>
          <p>✅ Connected to Google Calendar</p>
          <p>Sync direction: {status.sync_direction}</p>
          <p>Last synced: {status.last_sync ? new Date(status.last_sync).toLocaleString() : 'Never'}</p>

          <button onClick={() => triggerSync.mutate()}>
            Sync Now
          </button>

          <button onClick={() => disconnect.mutate()} className="danger">
            Disconnect
          </button>
        </div>
      ) : (
        <div>
          <p>Connect your Google Calendar to sync events.</p>
          <button onClick={() => connect.mutate()}>
            Connect Google Calendar
          </button>
        </div>
      )}
    </div>
  );
}
```

#### B. Callback Handler (Web)

**File**: `app/web/app/calendar/google/callback/page.tsx`

```typescript
'use client';

import { useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

export default function GoogleCalendarCallback() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');

    if (error) {
      console.error('Google OAuth error:', error);
      router.push('/settings?error=google_auth_failed');
      return;
    }

    if (code && state) {
      // Backend handles the callback via direct API call
      // Just redirect to settings
      router.push('/settings?success=google_connected');
    }
  }, [searchParams, router]);

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h2>Connecting to Google Calendar...</h2>
      <p>Please wait while we complete the setup.</p>
    </div>
  );
}
```

---

## Acceptance Criteria

### OAuth Flow

- [ ] User clicks "Connect Google Calendar" → redirected to Google consent page
- [ ] User grants permission → redirected back to Brainda with success message
- [ ] Access token and refresh token stored securely in database (encrypted)
- [ ] Token refresh works automatically when access token expires

### One-Way Sync (Internal → Google)

- [ ] Creating event in Brainda → appears in Google Calendar within 15 minutes (or immediate with manual sync)
- [ ] Updating event in Brainda → updated in Google Calendar
- [ ] Cancelling event in Brainda → deleted from Google Calendar
- [ ] Recurring events synced with RRULE preserved
- [ ] Events appear in dedicated "Brainda" calendar in Google (not primary calendar)

### Two-Way Sync (Optional)

- [ ] Creating event in Google → appears in Brainda within 15 minutes
- [ ] Updating event in Google → updated in Brainda
- [ ] Deleting event in Google → marked cancelled in Brainda
- [ ] Conflict resolution: Last-write-wins based on `updated_at` timestamp
- [ ] Incremental sync using sync tokens (efficient, doesn't re-fetch all events)

### UI

- [ ] Settings page shows connection status
- [ ] "Sync Now" button triggers immediate sync
- [ ] Last sync timestamp displayed
- [ ] Disconnect button works, removes credentials

---

## Testing Strategy

### Manual Testing

**Test 1: One-Way Sync**

1. Connect Google Calendar
2. Create event in Brainda: "Test Event on Monday at 10am"
3. Click "Sync Now" or wait 15 minutes
4. Open Google Calendar web interface
5. Verify event appears in "Brainda" calendar

**Test 2: Two-Way Sync**

1. Enable two-way sync in settings
2. Create event in Google Calendar: "Google Event on Tuesday at 2pm"
3. Wait 15 minutes or trigger sync
4. Check Brainda calendar
5. Verify event appears with source='google'

**Test 3: Conflict Resolution**

1. Create event "Conflict Test" in Brainda
2. Sync to Google
3. Edit title in Brainda: "Conflict Test - Brainda Edit"
4. Edit title in Google: "Conflict Test - Google Edit"
5. Trigger two-way sync
6. Verify: Most recent edit wins (based on updated_at)

**Test 4: Token Refresh**

1. Wait for access token to expire (1 hour)
2. Trigger sync
3. Verify: Sync succeeds using refresh token
4. Check logs: No "401 Unauthorized" errors

---

## Security Checklist

- [ ] **Token storage**: Encrypt tokens at rest (use PostgreSQL pgcrypto or application-level encryption)
- [ ] **State token**: Generate cryptographically secure random state for CSRF protection
- [ ] **Scopes**: Request minimum required scopes (calendar.events, not full calendar access)
- [ ] **Token rotation**: Handle refresh token rotation (some Google flows rotate refresh tokens)
- [ ] **Revocation**: When user disconnects, revoke tokens via Google API
- [ ] **Audit logging**: Log all sync operations with user_id and timestamp

---

## Performance Targets

- [ ] OAuth flow: <5s from consent to redirect
- [ ] One-way sync (50 events): <10s
- [ ] Two-way sync (100 events, first run): <30s
- [ ] Incremental sync (10 changes): <5s
- [ ] Token refresh: <2s

---

## Migration Guide

### For Existing Users (Stage 6 → Stage 7)

```bash
# Install Google API client
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Update .env with Google credentials
echo "GOOGLE_CLIENT_ID=your-client-id" >> .env
echo "GOOGLE_CLIENT_SECRET=your-client-secret" >> .env
echo "GOOGLE_REDIRECT_URI=https://yourdomain.com/api/v1/calendar/google/callback" >> .env

# Restart services
docker-compose restart orchestrator worker
```

---

## Risk Checklist

- [ ] **Rate limiting**: Google Calendar API has quotas (10,000 requests/day), implement backoff
- [ ] **Token expiry**: Handle expired refresh tokens gracefully (prompt user to re-authenticate)
- [ ] **Sync loops**: Prevent infinite loops (event updated in Brainda → synced to Google → synced back to Brainda)
- [ ] **Data loss**: Never delete events without user confirmation (soft delete only)
- [ ] **Privacy**: Inform users that event data will be sent to Google
- [ ] **Network failures**: Retry failed syncs with exponential backoff

---

## Success Metrics

After 2 weeks of usage:

- **Adoption**: >60% of users connect Google Calendar
- **Sync reliability**: >98% of syncs complete successfully
- **Conflict rate**: <5% of events trigger conflict resolution
- **User satisfaction**: Users report Google Calendar feels "seamlessly integrated"

---

## Next Steps After Stage 7

Once Google Calendar sync is stable:

1. Use for 2 weeks, monitor sync logs
2. Evaluate: Do you need passkeys for multi-user scenarios?
3. If yes: Proceed to Stage 8
4. If no: Consider Stage 10 (Advanced agent routing) or call MVP "complete"

---

## References

- [Google Calendar API](https://developers.google.com/calendar/api/guides/overview)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Sync Tokens](https://developers.google.com/calendar/api/guides/sync)

---

## Remember

**Do NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

Good luck! 🚀
