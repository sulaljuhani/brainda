# Stage 3: API Integration Layer

**Duration**: 2-3 days
**Priority**: HIGH
**Dependencies**: Stage 1 (Foundation)
**Can Be Parallel With**: Stage 2 (Layout)

---

## Goal

Create type-safe API client with proper error handling, authentication, and custom hooks for all backend endpoints.

---

## Tasks

### Task 3.1: Define TypeScript Types

**File**: `src/types/api.ts`

```typescript
// User & Auth
export interface User {
  id: string;
  username: string;
  email?: string;
  created_at: string;
}

export interface Session {
  session_token: string;
  expires_at: string;
}

// Notes
export interface Note {
  id: string;
  user_id: string;
  title: string;
  body: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface CreateNoteRequest {
  title: string;
  body: string;
  tags?: string[];
}

// Reminders
export interface Reminder {
  id: string;
  user_id: string;
  title: string;
  body?: string;
  due_at_utc: string;
  status: 'active' | 'completed' | 'snoozed';
  repeat_rrule?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateReminderRequest {
  title: string;
  body?: string;
  due_at_utc: string;
  repeat_rrule?: string;
}

// Documents
export interface Document {
  id: string;
  user_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  upload_path: string;
  content_hash: string;
  created_at: string;
}

export interface UploadDocumentResponse {
  success: boolean;
  job_id?: string;
  document_id?: string;
  message?: string;
  deduplicated?: boolean;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

// Calendar
export interface CalendarEvent {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  starts_at: string;
  ends_at?: string;
  timezone: string;
  location_text?: string;
  rrule?: string;
  status: string;
  is_recurring_instance?: boolean;
}

export interface CreateEventRequest {
  title: string;
  description?: string;
  starts_at: string;
  ends_at?: string;
  timezone?: string;
  location_text?: string;
  rrule?: string;
}

// Chat
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  toolCall?: ToolCall;
  citations?: Citation[];
}

export interface ToolCall {
  icon: string;
  name: string;
  result: string;
  status: 'success' | 'error' | 'pending';
}

export interface Citation {
  source_type: string;
  source_title: string;
  content_snippet: string;
  score: number;
}

export interface ChatRequest {
  message: string;
}

// Search
export interface SearchResult {
  id: string;
  type: 'note' | 'document' | 'reminder' | 'event';
  title: string;
  snippet: string;
  score: number;
  metadata: Record<string, any>;
}

export interface SearchResponse {
  results: SearchResult[];
  count: number;
}

// API Responses
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    message: string;
    code?: string;
  };
}
```

**File**: `src/types/index.ts`

```typescript
export * from './api';
```

---

### Task 3.2: Create Base API Client

**File**: `src/services/api.ts`

```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const API_BASE_PATH = import.meta.env.VITE_API_BASE_PATH || '/api/v1';

class ApiClient {
  private baseURL = `${API_BASE_URL}${API_BASE_PATH}`;

  private getAuthToken(): string | null {
    return (
      localStorage.getItem('session_token') ||
      localStorage.getItem('api_token')
    );
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getAuthToken();
    const url = `${this.baseURL}${endpoint}`;

    const headers: HeadersInit = {
      ...options.headers,
    };

    // Add auth header if token exists
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Add content-type for JSON requests
    if (options.body && typeof options.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        message: response.statusText,
      }));
      throw new Error(error.message || 'Request failed');
    }

    // Handle no-content responses
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async uploadFile(endpoint: string, file: File): Promise<any> {
    const token = this.getAuthToken();
    const url = `${this.baseURL}${endpoint}`;
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(url, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        message: response.statusText,
      }));
      throw new Error(error.message || 'Upload failed');
    }

    return response.json();
  }

  async stream(endpoint: string, data: any): Promise<ReadableStream> {
    const token = this.getAuthToken();
    const url = `${this.baseURL}${endpoint}`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error('Stream request failed');
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    return response.body;
  }
}

export const api = new ApiClient();
```

---

### Task 3.3: Create Service Modules

**File**: `src/services/notesService.ts`

```typescript
import { api } from './api';
import type { Note, CreateNoteRequest } from '@types';

export const notesService = {
  getAll: () => api.get<Note[]>('/notes'),

  getById: (id: string) => api.get<Note>(`/notes/${id}`),

  create: (data: CreateNoteRequest) => api.post<Note>('/notes', data),

  update: (id: string, data: Partial<CreateNoteRequest>) =>
    api.put<Note>(`/notes/${id}`, data),

  delete: (id: string) => api.delete<void>(`/notes/${id}`),
};
```

**File**: `src/services/remindersService.ts`

```typescript
import { api } from './api';
import type { Reminder, CreateReminderRequest } from '@types';

export const remindersService = {
  getAll: () => api.get<Reminder[]>('/reminders'),

  create: (data: CreateReminderRequest) =>
    api.post<Reminder>('/reminders', data),

  snooze: (id: string, minutes: number) =>
    api.post<Reminder>(`/reminders/${id}/snooze`, { duration_minutes: minutes }),

  complete: (id: string) =>
    api.post<Reminder>(`/reminders/${id}/complete`, {}),

  delete: (id: string) => api.delete<void>(`/reminders/${id}`),
};
```

**File**: `src/services/documentsService.ts`

```typescript
import { api } from './api';
import type { Document, UploadDocumentResponse, JobStatus } from '@types';

export const documentsService = {
  getAll: () => api.get<Document[]>('/documents'),

  upload: (file: File) =>
    api.uploadFile('/ingest', file) as Promise<UploadDocumentResponse>,

  getJobStatus: (jobId: string) => api.get<JobStatus>(`/jobs/${jobId}`),

  delete: (id: string) => api.delete<void>(`/documents/${id}`),
};
```

**File**: `src/services/calendarService.ts`

```typescript
import { api } from './api';
import type { CalendarEvent, CreateEventRequest } from '@types';

export const calendarService = {
  getEvents: (start: string, end: string) =>
    api.get<{ events: CalendarEvent[]; count: number }>(
      `/calendar/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
    ),

  create: (data: CreateEventRequest) =>
    api.post<CalendarEvent>('/calendar/events', data),

  delete: (id: string) => api.delete<void>(`/calendar/events/${id}`),
};
```

**File**: `src/services/chatService.ts`

```typescript
import { api } from './api';
import type { ChatRequest } from '@types';

export const chatService = {
  sendMessage: (message: string) =>
    api.stream('/chat', { message } as ChatRequest),
};
```

**File**: `src/services/searchService.ts`

```typescript
import { api } from './api';
import type { SearchResponse } from '@types';

export const searchService = {
  search: (query: string, limit = 20) =>
    api.get<SearchResponse>(
      `/search?query=${encodeURIComponent(query)}&limit=${limit}`
    ),
};
```

---

### Task 3.4: Create Custom Hooks

**File**: `src/hooks/useNotes.ts`

```typescript
import { useState, useEffect } from 'react';
import { notesService } from '@services/notesService';
import type { Note, CreateNoteRequest } from '@types';

export function useNotes() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await notesService.getAll();
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch notes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
  }, []);

  const createNote = async (data: CreateNoteRequest) => {
    const newNote = await notesService.create(data);
    setNotes((prev) => [newNote, ...prev]);
    return newNote;
  };

  const updateNote = async (id: string, data: Partial<CreateNoteRequest>) => {
    const updated = await notesService.update(id, data);
    setNotes((prev) => prev.map((n) => (n.id === id ? updated : n)));
    return updated;
  };

  const deleteNote = async (id: string) => {
    await notesService.delete(id);
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  return {
    notes,
    loading,
    error,
    createNote,
    updateNote,
    deleteNote,
    refetch: fetchNotes,
  };
}
```

Create similar hooks for:
- `src/hooks/useReminders.ts`
- `src/hooks/useDocuments.ts`
- `src/hooks/useCalendar.ts`

---

### Task 3.5: Create Auth Context

**File**: `src/contexts/AuthContext.tsx`

```typescript
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { User } from '@types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('session_token');
    if (token) {
      // TODO: Validate token with backend
      setUser({ id: '1', username: 'demo', created_at: new Date().toISOString() });
    }
    setLoading(false);
  }, []);

  const login = (token: string) => {
    localStorage.setItem('session_token', token);
    // TODO: Fetch user data
    setUser({ id: '1', username: 'demo', created_at: new Date().toISOString() });
  };

  const logout = () => {
    localStorage.removeItem('session_token');
    localStorage.removeItem('api_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

**Update**: `src/App.tsx`

```typescript
import { AuthProvider } from '@contexts/AuthContext';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        {/* ... routes */}
      </BrowserRouter>
    </AuthProvider>
  );
}
```

---

## Testing & Verification

### Test 1: API Client Works

Create test file: `src/services/__tests__/api.test.ts`

```typescript
import { api } from '../api';

// Manual test (run in browser console)
async function testApi() {
  try {
    const health = await api.get('/health');
    console.log('Health check:', health);
  } catch (error) {
    console.error('API test failed:', error);
  }
}
```

### Test 2: Services Work

```bash
# In browser console (with dev server running)
import { notesService } from './services/notesService';
const notes = await notesService.getAll();
console.log(notes);
```

### Test 3: Hooks Work

Create a test component that uses `useNotes()` and verify data loads.

---

## Deliverables

- [x] TypeScript types for all API models
- [x] Base API client with auth
- [x] Service modules for all endpoints
- [x] Custom hooks for data fetching
- [x] Auth context and hook
- [x] Error handling throughout
- [x] File upload support
- [x] Streaming support for chat

---

## Next Stages

**Can Now Start**:
- Stage 4: Chat Page
- Stage 5: Notes Management
- Stage 6: Reminders Interface
- Stage 7: Documents & Upload
- Stage 8: Calendar View
- Stage 9: Search Interface
- Stage 10: Authentication Flow

All page implementation stages can now proceed in parallel!
