# Calendar Event Creation Endpoint Analysis - Stage 6 Failure

## Summary

The calendar event creation endpoint (`POST /api/v1/calendar/events`) is returning an **unparseable JSON response** due to improper serialization of UUID and datetime objects, causing the test to fail with `jq: parse error: Invalid numeric literal`.

---

## Issue Details

### Test Failure Location
- **File**: `tests/stage6.sh:155-168`
- **Error**: 
  ```
  jq: parse error: Invalid numeric literal at line 1, column 2
  ✗ Calendar event ID returned (value empty)
  ```

### Root Cause

The calendar service returns asyncpg Record objects converted to plain dictionaries containing **non-JSON-serializable types**:

```python
# app/api/services/calendar_service.py:86
return {"success": True, "data": dict(record)}
```

When `dict(record)` is called on an asyncpg Record, it creates a dictionary containing:
- **UUID objects** (not JSON serializable)
- **datetime objects** (not JSON serializable)

When FastAPI attempts to JSON-serialize this response, it fails because there's **no custom JSONEncoder** configured to handle these types.

---

## 1. Endpoint Implementation

### Location
- **File**: `/home/user/brainda/app/api/routers/calendar.py:31-41`
- **Route**: `POST /api/v1/calendar/events`

```python
@router.post("/events", response_model=dict)
async def create_calendar_event(
    payload: CalendarEventCreate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.create_event(user_id, payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
```

### Problem #1: Incorrect response_model
- **Current**: `response_model=dict`
- **Should be**: `response_model=dict` (but with proper serialization)
- **Issue**: A proper Pydantic model exists but isn't being used

---

## 2. Response Format Issues

### What the Code Does
The service layer (`app/api/services/calendar_service.py:59-86`) inserts a calendar event and returns:

```python
record = await self.db.fetchrow(
    """
    INSERT INTO calendar_events (...)
    VALUES (...)
    RETURNING *
    """,
    ...
)

logger.info(
    "calendar_event_created",
    user_id=str(user_id),
    event_id=str(record["id"]),  # ✓ Correctly converts to string for logging
    ...
)

return {"success": True, "data": dict(record)}  # ✗ PROBLEM: raw dict with UUID/datetime
```

### Why Event ID is Empty
Line 91 in `tests/stage6.sh`:
```bash
event_id=$(echo "$body" | jq -r '.data.id // .id // empty')
```

The jq error happens BEFORE it can even parse the `.data.id` field because:
1. FastAPI tries to serialize the response
2. Python UUID objects can't be JSON-serialized
3. An error response is returned instead of proper JSON
4. jq fails to parse the error response

---

## 3. Database Schema

### Table: calendar_events
**File**: `/home/user/brainda/migrations/005_add_calendar.sql`

```sql
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    timezone TEXT NOT NULL,
    location_id UUID REFERENCES locations(id),
    location_text TEXT,
    rrule TEXT,
    source TEXT DEFAULT 'internal',
    google_event_id TEXT UNIQUE,
    google_calendar_id TEXT,
    status TEXT DEFAULT 'confirmed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key Fields Causing Serialization Issues**:
- `id` (UUID) - Cannot be directly JSON serialized
- `user_id` (UUID) - Cannot be directly JSON serialized
- `starts_at` (TIMESTAMPTZ) - Cannot be directly JSON serialized without ISO format
- `ends_at` (TIMESTAMPTZ) - Cannot be directly JSON serialized
- `created_at` (TIMESTAMPTZ) - Cannot be directly JSON serialized
- `updated_at` (TIMESTAMPTZ) - Cannot be directly JSON serialized

---

## 4. Model Definitions

### CalendarEventCreate (Input Schema)
**File**: `/home/user/brainda/app/api/models/calendar.py:12-44`

```python
class CalendarEventCreate(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    starts_at: datetime  # ✓ Pydantic handles datetime serialization
    ends_at: Optional[datetime] = None
    timezone: str = Field("UTC", min_length=2, max_length=64)
    location_text: Optional[str] = Field(None, max_length=512)
    rrule: Optional[str] = None
```

### CalendarEventResponse (Output Schema)
**File**: `/home/user/brainda/app/api/models/calendar.py:91-104`

```python
class CalendarEventResponse(BaseModel):
    id: UUID  # ✓ Pydantic serializes UUID to string
    user_id: UUID  # ✓ Pydantic serializes UUID to string
    title: str
    description: Optional[str]
    starts_at: datetime  # ✓ Pydantic serializes to ISO format
    ends_at: Optional[datetime]
    timezone: str
    location_text: Optional[str]
    rrule: Optional[str]
    status: str
    source: str
    created_at: datetime  # ✓ Pydantic serializes to ISO format
    updated_at: datetime  # ✓ Pydantic serializes to ISO format
```

**Critical Issue**: This model exists but is NOT used in the router!

---

## 5. Serialization Problems

### Problem #1: Raw dict() Conversion
```python
# app/api/services/calendar_service.py:86
return {"success": True, "data": dict(record)}
```

When asyncpg returns a Record and we convert it with `dict()`:
- All UUID fields remain as Python `uuid.UUID` objects
- All TIMESTAMPTZ fields remain as Python `datetime` objects
- These **cannot be JSON serialized** by FastAPI's default encoder

### Problem #2: No Custom JSONEncoder
**File**: `/home/user/brainda/app/api/main.py`

Searching for JSONEncoder configuration:
```bash
$ grep -n "json_encoders\|JSONEncoder" app/api/main.py
$ # No results - no custom encoder is configured!
```

**FastAPI Version Issue**: Older FastAPI versions required explicit `json_encoders` in FastAPI() constructor. Newer versions handle Pydantic models automatically but NOT raw dicts with non-serializable objects.

### Problem #3: response_model=dict
```python
@router.post("/events", response_model=dict)  # ✗ Bypasses Pydantic validation
async def create_calendar_event(...):
    ...
    return result  # Raw dict with UUID/datetime objects
```

Using `response_model=dict` tells FastAPI:
- "This endpoint returns a dict"
- "Don't validate it with a Pydantic model"
- "Don't use Pydantic's JSON serialization"

**Result**: Raw dictionaries with non-JSON-serializable objects are returned directly.

---

## 6. Comparison with Working Endpoints

### Reminders Endpoint (PARTIALLY WORKING)
**File**: `/home/user/brainda/app/api/routers/reminders.py`

**For LIST endpoint** (works):
```python
@router.get("", response_model=List[ReminderResponse])  # ✓ Proper model
async def list_reminders(...):
    service = ReminderService(db)
    reminders = await service.list_reminders(user_id, status, limit)
    return reminders  # ✓ Pydantic validates each item
```

**For CREATE endpoint** (might fail):
```python
@router.post("", response_model=dict)  # ✗ Same problem!
async def create_reminder(...):
    service = ReminderService(db)
    result = await service.create_reminder(user_id, data)
    return result  # Raw dict with potential UUID/datetime issues
```

---

## 7. Test Expectations

### Test Code (stage6.sh:155-168)
```bash
test_calendar_event_create() {
  log "Testing calendar event creation via API..."
  local title="Test Event $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")

  local event_id
  event_id=$(create_calendar_event "$payload") || return 1
  assert_json_field "$STAGE6_LAST_EVENT_RESPONSE" '.data.title // .title' "$title" \
    "Calendar event title returned" || return 1
  local stored_title
  stored_title=$(psql_query "SELECT title FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$stored_title" "$title" "Calendar event persisted with correct title"
}
```

### Test's create_calendar_event Function (stage6.sh:74-96)
```bash
create_calendar_event() {
  local payload="$1"
  response=$(curl ... -X POST "$BASE_URL/api/v1/calendar/events" ...)
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Calendar event creation failed (status $status)"
    echo "Response: $body" >&2
    return 1
  fi

  local event_id
  event_id=$(echo "$body" | jq -r '.data.id // .id // empty')  # ✗ jq parse error here
  assert_not_empty "$event_id" "Calendar event ID returned" || return 1
  STAGE6_LAST_EVENT_RESPONSE="$body"
  stage6_register_event_cleanup "$event_id"
  echo "$event_id"
}
```

**Expected Response**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "550e8400-e29b-41d4-a716-446655440001",
    "title": "Test Event 20251113-...",
    "starts_at": "2025-11-13T10:30:00+00:00",
    "timezone": "UTC",
    ...
  }
}
```

**Actual Response** (inferred from error):
Something that's not valid JSON, possibly:
```
uuid.UUID('...')  # Python repr of UUID object
TypeError: Object of type UUID is not JSON serializable
```

---

## 8. Why Event ID is Empty

The chain of failure:
1. ✓ Database insert succeeds → record with UUID id created
2. ✓ Service logging works → converts UUID to string for logging
3. ✗ Service returns raw dict with UUID object
4. ✗ FastAPI tries to JSON-serialize the dict
5. ✗ JSON encoder fails on UUID object
6. ✗ Error response returned (not JSON-encoded)
7. ✗ jq tries to parse error response → parse error
8. ✗ `event_id=""` because jq failed
9. ✗ Test fails: "Calendar event ID returned (value empty)"

---

## Root Cause Summary

| Component | Issue | Impact |
|-----------|-------|--------|
| `calendar_service.py:86` | Returns `dict(record)` with UUID/datetime | Non-JSON-serializable objects |
| `calendar_service.py:86` | No conversion to strings | asyncpg Record not properly serialized |
| `calendar.py:91-104` | `CalendarEventResponse` model exists | Unused response model |
| `routers/calendar.py:31` | `response_model=dict` | Bypasses Pydantic serialization |
| `main.py` | No custom JSONEncoder | No fallback for UUID/datetime serialization |
| Test: `stage6.sh:91` | Expects JSON response | jq parse error when response is invalid |

---

## 9. Verification Steps

To confirm this is the issue:

```bash
# Test the endpoint directly
curl -X POST "http://localhost:8000/api/v1/calendar/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Event",
    "starts_at": "2025-11-15T10:00:00Z",
    "timezone": "UTC"
  }' \
  -v

# Look for error in response body or:
# - TypeError: Object of type UUID is not JSON serializable
# - TypeError: Object of type datetime is not JSON serializable
# - Invalid JSON response
```

---

## 10. Solution Options

### Option A: Use Proper Response Model (RECOMMENDED)
```python
# app/api/routers/calendar.py:31-41
@router.post("/events", response_model=dict)  # Or create a wrapper model
async def create_calendar_event(
    payload: CalendarEventCreate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    service = CalendarService(db)
    result = await service.create_event(user_id, payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Wrap the result with proper Pydantic serialization
    if result.get("success") and result.get("data"):
        # Convert to CalendarEventResponse for proper serialization
        result["data"] = CalendarEventResponse(**result["data"]).dict()
    
    return result
```

### Option B: Convert Objects to Strings in Service
```python
# app/api/services/calendar_service.py:86
def dict_from_record(record):
    """Convert asyncpg record to JSON-serializable dict"""
    d = dict(record)
    for key, value in d.items():
        if isinstance(value, UUID):
            d[key] = str(value)
        elif isinstance(value, datetime):
            d[key] = value.isoformat()
    return d

return {"success": True, "data": dict_from_record(record)}
```

### Option C: Configure Custom JSONEncoder in FastAPI
```python
# app/api/main.py
from fastapi.encoders import jsonable_encoder

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app = FastAPI(
    ...,
    json_encoder=CustomJSONEncoder  # FastAPI v0.64+
)
```

---

## Files to Review

1. **Endpoint**: `/home/user/brainda/app/api/routers/calendar.py` (lines 31-41)
2. **Service**: `/home/user/brainda/app/api/services/calendar_service.py` (line 86)
3. **Models**: `/home/user/brainda/app/api/models/calendar.py` (lines 91-104)
4. **Main**: `/home/user/brainda/app/api/main.py` (JSON encoder config)
5. **Test**: `/home/user/brainda/tests/stage6.sh` (lines 155-168, 74-96)
6. **Database**: `/home/user/brainda/migrations/005_add_calendar.sql`

---

## Summary Table

| Question | Answer |
|----------|--------|
| **Where is the endpoint?** | `/home/user/brainda/app/api/routers/calendar.py:31-41` |
| **What's the response format?** | `{"success": bool, "data": {...event_dict...}}` |
| **Why is event ID empty?** | jq fails to parse response due to UUID serialization error |
| **Why is response malformed?** | `dict(record)` contains non-JSON-serializable UUID/datetime objects |
| **Root cause?** | No proper Pydantic model validation; `response_model=dict` bypasses serialization |
| **Where's the bug?** | `calendar_service.py:86` and `routers/calendar.py:31` |
| **Fix location?** | Either the service layer or router needs to properly serialize the response |

