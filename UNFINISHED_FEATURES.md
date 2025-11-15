# Unfinished Features - Frontend-Backend Integration

This document lists frontend features that have UI implementations but are missing backend endpoints. These are likely planned features that need backend implementation.

## 1. User Profile Management

**Frontend Implementation:** `app/web/src/services/settingsService.ts:21-23`

```typescript
async updateProfile(data: UpdateProfileRequest): Promise<void> {
  return api.put<void>('/user/profile', data);
}
```

**Status:** ⚠️ Missing backend endpoint

**Expected Endpoint:** `PUT /api/v1/user/profile`

**Request Body:**
```typescript
interface UpdateProfileRequest {
  display_name?: string;
  email?: string;
  avatar_url?: string;
  // Add other profile fields as needed
}
```

**Priority:** Medium - Users cannot update their profile information

**Notes:**
- Current auth system has `/auth/users/me` (GET only)
- Could extend this to support PATCH method for profile updates
- Alternatively, create dedicated `/user/profile` endpoint

---

## 2. Password Change

**Frontend Implementation:** `app/web/src/services/settingsService.ts:26-28`

```typescript
async changePassword(data: ChangePasswordRequest): Promise<void> {
  return api.post<void>('/user/change-password', data);
}
```

**Status:** ⚠️ Missing backend endpoint

**Expected Endpoint:** `POST /api/v1/user/change-password`

**Request Body:**
```typescript
interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}
```

**Priority:** High - Important security feature

**Implementation Requirements:**
1. Verify current password against database
2. Hash new password with bcrypt (cost factor 12)
3. Update `users` table
4. Invalidate existing sessions (optional for security)
5. Return success response

**Recommended Location:** `app/api/routers/auth.py`

---

## 3. OpenMemory Settings Management

**Frontend Implementation:** `app/web/src/services/settingsService.ts:48-54`

```typescript
async getOpenMemorySettings(): Promise<OpenMemorySettings> {
  return api.get<OpenMemorySettings>('/memory/settings');
}

async updateOpenMemorySettings(settings: Partial<OpenMemorySettings>): Promise<OpenMemorySettings> {
  return api.put<OpenMemorySettings>('/memory/settings', settings);
}
```

**Status:** ⚠️ Missing backend endpoints

**Expected Endpoints:**
- `GET /api/v1/memory/settings`
- `PUT /api/v1/memory/settings`

**Response/Request Body:**
```typescript
interface OpenMemorySettings {
  enabled: boolean;
  server_url?: string;
  api_key?: string;
  auto_store_conversations?: boolean;
  retention_days?: number;
}
```

**Priority:** Medium - Users cannot configure OpenMemory integration

**Implementation Options:**

### Option 1: Database Storage (Recommended)
Store settings in `user_settings` table or create dedicated `openmemory_user_settings` table:

```sql
CREATE TABLE openmemory_user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    enabled BOOLEAN DEFAULT false,
    server_url TEXT,
    api_key_encrypted TEXT, -- Encrypt with Fernet
    auto_store_conversations BOOLEAN DEFAULT true,
    retention_days INTEGER DEFAULT 90,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Option 2: Client-Side Storage Only
If settings are user-specific and don't affect backend behavior, store in localStorage only. In this case, **remove these methods from settingsService** and implement in client-side settings manager.

**Recommended Location:** `app/api/routers/memory.py` (add new endpoints)

---

## Implementation Priority

### High Priority (Security/Core Functionality)
1. **Password Change** - Critical security feature

### Medium Priority (User Experience)
2. **User Profile Management** - Users expect to update their info
3. **OpenMemory Settings** - Needed for memory feature configuration

---

## Next Steps

### For Password Change:
1. Add endpoint to `app/api/routers/auth.py`
2. Add Pydantic model for request validation
3. Implement bcrypt password verification
4. Add integration test to `tests/`
5. Update API documentation

### For User Profile:
1. Decide: Extend `/auth/users/me` with PATCH or create `/user/profile`
2. Add endpoint implementation
3. Add validation for email format, display name length, etc.
4. Consider adding avatar upload support
5. Add integration test

### For OpenMemory Settings:
1. Decide: Database storage vs client-side only
2. If database: Create migration for settings table
3. Add endpoints to `app/api/routers/memory.py`
4. Encrypt API keys with Fernet (similar to Google Calendar tokens)
5. Add integration test

---

## Alternative: Remove Frontend Code

If these features are not planned for implementation in the near future, consider:

1. **Comment out the methods** in `settingsService.ts` with TODO comments
2. **Disable UI elements** that call these methods
3. **Add feature flags** to hide incomplete features from users

This prevents user confusion when features appear available but don't work.

---

## Testing Checklist (Once Implemented)

- [ ] Password change with correct current password succeeds
- [ ] Password change with incorrect current password fails
- [ ] Password change updates password hash in database
- [ ] Profile update modifies user record
- [ ] Profile update validates email format
- [ ] OpenMemory settings are persisted across sessions
- [ ] OpenMemory API key is encrypted in database
- [ ] All endpoints require authentication
- [ ] All endpoints filter by user_id (user isolation)

---

**Document Created:** 2025-11-15
**Last Updated:** 2025-11-15
**Status:** Awaiting implementation decisions
