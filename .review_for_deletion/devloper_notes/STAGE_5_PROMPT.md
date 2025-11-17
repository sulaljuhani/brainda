# System Prompt: Stage 5 - Mobile App + Full Idempotency

## Context

You are implementing **Stage 5** of the Brainda project (chat-first notes, reminders & knowledge assistant). The MVP (Stages 0-4) is **already complete** and working:

- ✅ Infrastructure with Docker services
- ✅ Chat interface with streaming responses
- ✅ Notes (create/update/search) with Markdown vault
- ✅ Time-based reminders with push notifications
- ✅ Document ingestion with RAG and structured citations
- ✅ Unified vector database (Qdrant)
- ✅ Simple 5-minute deduplication for notes and reminders
- ✅ Observability, backups, data retention

## Your Mission: Stage 5

Build a **native mobile app** (React Native/Expo) with **full idempotency infrastructure** to support offline operation and reliable sync.

## Why This Stage Matters

Mobile introduces new challenges:
- **Unreliable networks**: Users retry requests when they think they failed
- **Offline mode**: Queue operations locally, sync when connection returns
- **Background tasks**: Handle push notifications in all app states
- **Race conditions**: Multiple devices creating the same reminder/note

The current simple deduplication (5-minute window) is insufficient for mobile. We need **full idempotency** to guarantee exactly-once semantics even with aggressive retries.

---

## Deliverables

### 1. Full Idempotency Infrastructure (Backend)

**Critical**: Implement this BEFORE mobile app to prevent duplicate data.

#### A. Database Schema

Create `migrations/004_add_idempotency.sql`:

```sql
-- Stage 5: Full idempotency infrastructure

CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,  -- /api/v1/reminders, /api/v1/notes, etc.
    request_hash TEXT NOT NULL,  -- SHA256 of request body
    response_status INTEGER NOT NULL,  -- HTTP status code
    response_body JSONB NOT NULL,  -- Cached response
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',

    -- Composite unique constraint: one key per user+endpoint
    CONSTRAINT unique_idempotency_key UNIQUE (user_id, idempotency_key, endpoint)
);

-- Index for cleanup job
CREATE INDEX idx_idempotency_keys_expires_at ON idempotency_keys(expires_at);

-- Index for fast lookups
CREATE INDEX idx_idempotency_keys_user_key ON idempotency_keys(user_id, idempotency_key);
```

#### B. Idempotency Middleware

**File**: `app/api/middleware/idempotency.py`

```python
from fastapi import Request, Response
from typing import Optional
import hashlib
import json

class IdempotencyMiddleware:
    """
    Ensures exactly-once semantics for state-changing operations.

    How it works:
    1. Client sends Idempotency-Key header (UUID v4)
    2. Middleware checks if key exists in cache
    3. If exists: return cached response (idempotent replay)
    4. If new: execute request, cache response for 24h
    5. Auto-cleanup expired keys via scheduled job
    """

    IDEMPOTENT_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
    IDEMPOTENT_ENDPOINTS = {
        "/api/v1/notes",
        "/api/v1/reminders",
        "/api/v1/calendar/events",
        "/api/v1/ingest",
    }

    async def __call__(self, request: Request, call_next):
        # Only apply to state-changing operations
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        # Only apply to specific endpoints
        if not any(request.url.path.startswith(ep) for ep in self.IDEMPOTENT_ENDPOINTS):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # No key provided: proceed normally (backward compatible)
            return await call_next(request)

        user_id = request.state.user_id  # Set by auth middleware
        endpoint = request.url.path

        # Check cache
        cached = await self.get_cached_response(user_id, idempotency_key, endpoint)
        if cached:
            logger.info("idempotency_cache_hit", extra={
                "user_id": str(user_id),
                "idempotency_key": idempotency_key,
                "endpoint": endpoint
            })
            return Response(
                content=cached["response_body"],
                status_code=cached["response_status"],
                headers={"X-Idempotency-Replay": "true"}
            )

        # Execute request
        response = await call_next(request)

        # Cache response (only for successful state changes)
        if 200 <= response.status_code < 300:
            await self.cache_response(
                user_id,
                idempotency_key,
                endpoint,
                request,
                response
            )

        return response

    async def get_cached_response(self, user_id, key, endpoint):
        """Fetch cached response from database"""
        query = """
            SELECT response_status, response_body
            FROM idempotency_keys
            WHERE user_id = $1 AND idempotency_key = $2 AND endpoint = $3
            AND expires_at > NOW()
        """
        return await db.fetchrow(query, user_id, key, endpoint)

    async def cache_response(self, user_id, key, endpoint, request, response):
        """Store response in cache for 24 hours"""
        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()

        query = """
            INSERT INTO idempotency_keys
            (idempotency_key, user_id, endpoint, request_hash, response_status, response_body, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '24 hours')
            ON CONFLICT (user_id, idempotency_key, endpoint) DO NOTHING
        """
        await db.execute(
            query,
            key,
            user_id,
            endpoint,
            request_hash,
            response.status_code,
            response.body
        )
```

#### C. Cleanup Job

**File**: `app/worker/tasks/cleanup_idempotency.py`

```python
from celery import shared_task

@shared_task
def cleanup_expired_idempotency_keys():
    """
    Delete idempotency keys older than 24 hours.
    Runs every hour via Celery Beat.
    """
    deleted = db.execute("""
        DELETE FROM idempotency_keys
        WHERE expires_at < NOW()
    """)

    logger.info("idempotency_cleanup_completed", extra={
        "deleted_count": deleted
    })
```

**Register in Celery Beat**:
```python
# app/worker/celeryconfig.py
CELERYBEAT_SCHEDULE = {
    'cleanup-idempotency-keys': {
        'task': 'app.worker.tasks.cleanup_idempotency.cleanup_expired_idempotency_keys',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

#### D. Update Tool Response Contract

**All tools must now handle idempotency properly**:

```python
# Remove old 5-minute deduplication logic from tools
# The idempotency middleware handles this now

# Example: create_reminder tool
@tool(schema_version="1.1")
def create_reminder(title: str, due_at_utc: datetime, timezone: str, user_id: UUID):
    """
    No more manual deduplication checking!
    Idempotency middleware handles it.
    """
    # Just create the reminder
    reminder = db.create(Reminder(
        user_id=user_id,
        title=title,
        due_at_utc=due_at_utc,
        timezone=timezone
    ))

    return tool_success(reminder.to_dict())
```

**Remove deduplication constraints from database**:
```sql
-- migrations/004_add_idempotency.sql (continued)

-- Drop old 5-minute deduplication indexes
DROP INDEX IF EXISTS idx_notes_dedup;
DROP INDEX IF EXISTS idx_reminders_dedup;

-- Add simpler uniqueness constraints (optional, for data integrity)
CREATE UNIQUE INDEX idx_notes_user_title ON notes(user_id, lower(title));
CREATE UNIQUE INDEX idx_reminders_unique ON reminders(user_id, title, due_at_utc) WHERE status = 'active';
```

---

### 2. Mobile App (React Native / Expo)

#### A. Project Setup

```bash
# Create Expo app
npx create-expo-app vib-mobile --template blank-typescript
cd vib-mobile

# Install dependencies
npx expo install expo-notifications expo-secure-store expo-linking
npm install @tanstack/react-query axios uuid
npm install @react-navigation/native @react-navigation/stack
```

#### B. API Client with Idempotency

**File**: `src/lib/api.ts`

```typescript
import axios, { AxiosRequestConfig } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import * as SecureStore from 'expo-secure-store';

const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
});

// Add auth token
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add idempotency key for state-changing operations
api.interceptors.request.use((config) => {
  const methods = ['POST', 'PATCH', 'PUT', 'DELETE'];
  if (methods.includes(config.method?.toUpperCase() || '')) {
    // Generate idempotency key if not provided
    if (!config.headers['Idempotency-Key']) {
      config.headers['Idempotency-Key'] = uuidv4();
    }
  }
  return config;
});

// Handle idempotency replays
api.interceptors.response.use((response) => {
  if (response.headers['x-idempotency-replay'] === 'true') {
    console.log('Idempotency replay detected');
  }
  return response;
});

export default api;
```

#### C. Offline Queue

**File**: `src/lib/offline-queue.ts`

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import api from './api';

interface QueuedRequest {
  id: string;
  method: string;
  url: string;
  data: any;
  headers: Record<string, string>;
  idempotencyKey: string;
  createdAt: number;
  retries: number;
}

class OfflineQueue {
  private queue: QueuedRequest[] = [];
  private processing = false;

  async init() {
    // Load queue from storage
    const stored = await AsyncStorage.getItem('offline_queue');
    if (stored) {
      this.queue = JSON.parse(stored);
    }

    // Listen for connectivity changes
    NetInfo.addEventListener(state => {
      if (state.isConnected) {
        this.processQueue();
      }
    });
  }

  async enqueue(method: string, url: string, data: any) {
    const idempotencyKey = uuidv4();

    const request: QueuedRequest = {
      id: uuidv4(),
      method,
      url,
      data,
      headers: { 'Idempotency-Key': idempotencyKey },
      idempotencyKey,
      createdAt: Date.now(),
      retries: 0,
    };

    this.queue.push(request);
    await this.saveQueue();

    // Try processing immediately
    this.processQueue();

    return idempotencyKey;
  }

  async processQueue() {
    if (this.processing || this.queue.length === 0) return;

    const netInfo = await NetInfo.fetch();
    if (!netInfo.isConnected) return;

    this.processing = true;

    while (this.queue.length > 0) {
      const request = this.queue[0];

      try {
        await api.request({
          method: request.method,
          url: request.url,
          data: request.data,
          headers: request.headers,
        });

        // Success: remove from queue
        this.queue.shift();
        await this.saveQueue();
      } catch (error) {
        request.retries++;

        // Max retries exceeded or client error: remove
        if (request.retries >= 5 || (error.response?.status >= 400 && error.response?.status < 500)) {
          this.queue.shift();
          await this.saveQueue();
          console.error('Request failed permanently', error);
        } else {
          // Retry later
          break;
        }
      }
    }

    this.processing = false;
  }

  async saveQueue() {
    await AsyncStorage.setItem('offline_queue', JSON.stringify(this.queue));
  }
}

export default new OfflineQueue();
```

#### D. Core Screens

**File**: `src/screens/ChatScreen.tsx`

```typescript
import React, { useState } from 'react';
import { View, TextInput, Button, ScrollView, Text } from 'react-native';
import { useMutation } from '@tanstack/react-query';
import api from '../lib/api';
import offlineQueue from '../lib/offline-queue';

export default function ChatScreen() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<any[]>([]);

  const sendMessage = useMutation({
    mutationFn: async (text: string) => {
      try {
        const response = await api.post('/chat', { message: text });
        return response.data;
      } catch (error) {
        // Queue for offline sync
        await offlineQueue.enqueue('POST', '/chat', { message: text });
        throw error;
      }
    },
    onSuccess: (data) => {
      setMessages(prev => [...prev, { role: 'user', content: message }, data]);
      setMessage('');
    },
  });

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <ScrollView style={{ flex: 1 }}>
        {messages.map((msg, i) => (
          <Text key={i}>{msg.role}: {msg.content}</Text>
        ))}
      </ScrollView>

      <TextInput
        value={message}
        onChangeText={setMessage}
        placeholder="Type a message..."
        style={{ borderWidth: 1, padding: 8, marginBottom: 8 }}
      />

      <Button
        title="Send"
        onPress={() => sendMessage.mutate(message)}
        disabled={sendMessage.isPending}
      />
    </View>
  );
}
```

**File**: `src/screens/RemindersScreen.tsx`

```typescript
import React from 'react';
import { View, Text, FlatList, Button } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';

export default function RemindersScreen() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['reminders'],
    queryFn: async () => {
      const response = await api.get('/reminders');
      return response.data;
    },
  });

  if (isLoading) return <Text>Loading...</Text>;

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <FlatList
        data={data?.data || []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={{ padding: 12, borderBottomWidth: 1 }}>
            <Text style={{ fontWeight: 'bold' }}>{item.title}</Text>
            <Text>{new Date(item.due_at_utc).toLocaleString()}</Text>
          </View>
        )}
      />

      <Button title="Refresh" onPress={() => refetch()} />
    </View>
  );
}
```

#### E. Push Notifications

**File**: `src/lib/notifications.ts`

```typescript
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import api from './api';

// Configure notification handler
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications() {
  if (!Device.isDevice) {
    console.log('Push notifications only work on physical devices');
    return;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.log('Push permission denied');
    return;
  }

  const token = (await Notifications.getExpoPushTokenAsync()).data;

  // Register with backend
  await api.post('/devices/register', {
    platform: Platform.OS,
    push_token: token,
  });

  console.log('Push token registered:', token);
}

export function setupNotificationHandlers() {
  // Handle notification received while app is foregrounded
  Notifications.addNotificationReceivedListener(notification => {
    console.log('Notification received:', notification);
  });

  // Handle user tapping notification
  Notifications.addNotificationResponseReceivedListener(response => {
    const data = response.notification.request.content.data;

    // Handle actions
    if (data.action === 'snooze_15m') {
      api.post(`/reminders/${data.reminder_id}/snooze`, { duration_minutes: 15 });
    } else if (data.action === 'done') {
      api.patch(`/reminders/${data.reminder_id}`, { status: 'done' });
    } else if (data.deep_link) {
      // Navigate to deep link
      Linking.openURL(data.deep_link);
    }
  });
}
```

#### F. Deep Linking

**File**: `app.json` (Expo config)

```json
{
  "expo": {
    "scheme": "vib",
    "ios": {
      "bundleIdentifier": "com.yourname.vib"
    },
    "android": {
      "package": "com.yourname.vib"
    }
  }
}
```

**File**: `App.tsx`

```typescript
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import * as Linking from 'expo-linking';

const Stack = createStackNavigator();

const linking = {
  prefixes: ['vib://'],
  config: {
    screens: {
      Reminders: 'reminders/:id',
      Notes: 'notes/:id',
    },
  },
};

export default function App() {
  return (
    <NavigationContainer linking={linking}>
      <Stack.Navigator>
        <Stack.Screen name="Chat" component={ChatScreen} />
        <Stack.Screen name="Reminders" component={RemindersScreen} />
        <Stack.Screen name="Notes" component={NotesScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

---

## Acceptance Criteria

### Backend (Idempotency)

- [ ] Idempotency middleware installed and working
- [ ] Duplicate requests (same `Idempotency-Key`) return cached response with `X-Idempotency-Replay: true` header
- [ ] Creating 10 identical reminders with same key → only 1 reminder in database
- [ ] Aggressive retry test: 50 rapid POST requests with same key → 1 reminder created, 49 cache hits
- [ ] Expired keys (>24h) cleaned up by scheduled job
- [ ] Old 5-minute deduplication logic removed from all tools
- [ ] Database constraints simplified (no more complex time-based dedup indexes)

### Mobile App

- [ ] App builds and runs on iOS and Android (Expo Go)
- [ ] User can login with API token
- [ ] Chat screen works: send message, receive response
- [ ] Reminders screen lists all reminders
- [ ] Push notifications work in all states:
  - Foreground: shows in-app alert
  - Background: shows system notification
  - Killed: shows notification, opens app on tap
- [ ] Deep linking works: `vib://reminders/{id}` opens reminder details
- [ ] Offline mode: create reminder while offline → queued → syncs when online
- [ ] No duplicate reminders from offline queue retries
- [ ] Notification actions work: Snooze 15m, Done

### Integration Tests

- [ ] Web creates reminder → mobile receives push notification within 5s
- [ ] Mobile creates reminder offline → syncs when online → appears in web
- [ ] Same idempotency key from web and mobile → only 1 entity created

---

## Testing Strategy

### 1. Idempotency Tests

```bash
#!/bin/bash
# test-idempotency.sh

TOKEN=$(grep API_TOKEN .env | cut -d= -f2)
KEY="test-key-$(uuidv4)"

# Test 1: Create reminder with idempotency key
echo "Test 1: First request..."
RESPONSE1=$(curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test",
    "due_at_utc": "2025-01-20T10:00:00Z",
    "due_at_local": "10:00:00",
    "timezone": "UTC"
  }')

ID1=$(echo $RESPONSE1 | jq -r '.data.id')
echo "Created: $ID1"

# Test 2: Retry with same key
echo "Test 2: Retry with same key..."
RESPONSE2=$(curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test",
    "due_at_utc": "2025-01-20T10:00:00Z",
    "due_at_local": "10:00:00",
    "timezone": "UTC"
  }')

ID2=$(echo $RESPONSE2 | jq -r '.data.id')
REPLAY=$(echo $RESPONSE2 | grep -i "x-idempotency-replay")

if [ "$ID1" != "$ID2" ]; then
  echo "✗ Different IDs returned"
  exit 1
fi

if [ -z "$REPLAY" ]; then
  echo "✗ Replay header missing"
  exit 1
fi

echo "✓ Idempotency working"

# Test 3: Aggressive retries
echo "Test 3: Aggressive retries (50 requests)..."
KEY2="test-key-2-$(uuidv4)"
for i in {1..50}; do
  curl -s -X POST http://localhost:8000/api/v1/reminders \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $KEY2" \
    -d '{"title":"Dup test","due_at_utc":"2025-01-20T12:00:00Z","due_at_local":"12:00:00","timezone":"UTC"}' \
    > /dev/null &
done

wait

# Count reminders with this title
COUNT=$(docker exec brainda-postgres psql -U postgres -d vib -c \
  "SELECT COUNT(*) FROM reminders WHERE title = 'Dup test';" | grep -oP '\d+' | head -1)

if [ "$COUNT" != "1" ]; then
  echo "✗ Expected 1 reminder, got $COUNT"
  exit 1
fi

echo "✓ Aggressive retry test passed"
```

### 2. Mobile Offline Tests

**Manual Test Plan**:

1. **Offline Creation**
   - Put device in airplane mode
   - Create reminder: "Call bank at 5pm"
   - Verify queued in AsyncStorage
   - Turn on network
   - Verify reminder synced to server
   - Check database: only 1 reminder exists

2. **Push Notification States**
   - Foreground: Create reminder → fires → verify in-app alert
   - Background: Lock device → reminder fires → verify notification appears
   - Killed: Force quit app → reminder fires → tap notification → app opens to reminder

3. **Deep Linking**
   - Send test notification with `vib://reminders/{id}`
   - Tap notification
   - Verify app opens to reminder details

---

## Migration Guide

### For Existing Users (MVP → Stage 5)

**Step 1**: Deploy backend changes

```bash
# Apply migration
docker exec brainda-postgres psql -U vib -d vib -f /app/migrations/004_add_idempotency.sql

# Restart services
docker-compose restart orchestrator worker
```

**Step 2**: Verify idempotency working

```bash
# Run test script
./test-idempotency.sh
```

**Step 3**: Deploy mobile app

```bash
cd vib-mobile
eas build --platform all
```

**Step 4**: Distribute to users (TestFlight / Play Store Beta)

---

## Risk Checklist

- [ ] **Idempotency key collisions**: Use UUID v4 (collision probability negligible)
- [ ] **24h expiry edge cases**: Test creation near midnight UTC
- [ ] **Storage growth**: Monitor `idempotency_keys` table size, cleanup job running
- [ ] **Offline queue bloat**: Max queue size (100 items), auto-discard oldest
- [ ] **Push token refresh**: Handle token updates on app reinstall
- [ ] **Deep link security**: Validate reminder belongs to user before opening

---

## Performance Targets

- [ ] Idempotency lookup: <10ms (indexed query)
- [ ] Cache hit response: <50ms (no business logic execution)
- [ ] Offline queue processing: <500ms per item
- [ ] Push notification delivery: <5s from reminder fire
- [ ] App cold start: <2s on mid-range device

---

## Success Metrics

After 2 weeks of usage:

- **Duplicate prevention**: 0 duplicate reminders/notes from retries
- **Offline reliability**: >95% of queued operations sync successfully
- **Push delivery**: >98% success rate across all device states
- **User satisfaction**: Mobile app feels "instant" even offline

---

## Next Steps After Stage 5

Once Stage 5 is stable:

1. Use mobile app for 2 weeks
2. Gather feedback on UX and reliability
3. Prioritize Stage 6 (Calendar) or Stage 7 (Google Sync) based on needs

---

## References

- [Idempotency Keys - Stripe Guide](https://stripe.com/docs/api/idempotent_requests)
- [Expo Push Notifications](https://docs.expo.dev/push-notifications/overview/)
- [React Query Offline](https://tanstack.com/query/latest/docs/react/guides/offline)

---

## Remember

**Do NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

Good luck! 🚀
