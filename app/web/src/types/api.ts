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
