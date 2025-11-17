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
  due_at_local: string;
  timezone: string;
  status: 'active' | 'completed' | 'snoozed';
  repeat_rrule?: string;
  category_id?: string;
  category_name?: string;
  task_id?: string;
  task_title?: string;
  calendar_event_id?: string;
  event_title?: string;
  offset_days?: number;
  offset_type?: 'before' | 'after';
  created_at: string;
  updated_at: string;
}

export interface CreateReminderRequest {
  title: string;
  body?: string;
  due_at_utc: string;
  due_at_local: string;
  timezone: string;
  repeat_rrule?: string;
  category_id?: string;
  task_id?: string;
  calendar_event_id?: string;
  offset_days?: number;
  offset_type?: 'before' | 'after';
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
  category_id?: string;
  category_name?: string;
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
  category_id?: string;
}

// Tasks
export interface Task {
  id: string;
  user_id: string;
  parent_task_id?: string;
  title: string;
  description?: string;
  category_id?: string;
  category_name?: string;
  starts_at?: string;
  ends_at?: string;
  all_day: boolean;
  timezone: string;
  rrule?: string;
  status: 'active' | 'completed' | 'cancelled';
  completed_at?: string;
  created_at: string;
  updated_at: string;
  subtasks?: Task[];
}

export interface CreateTaskRequest {
  title: string;
  description?: string;
  category_id?: string;
  starts_at?: string;
  ends_at?: string;
  all_day?: boolean;
  timezone: string;
  rrule?: string;
  parent_task_id?: string;
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  category_id?: string;
  starts_at?: string;
  ends_at?: string;
  all_day?: boolean;
  timezone?: string;
  rrule?: string;
  status?: 'active' | 'completed' | 'cancelled';
  completed_at?: string;
  parent_task_id?: string;
}

// Categories
export interface Category {
  id: string;
  user_id: string;
  name: string;
  color?: string;
  created_at: string;
}

export interface CreateCategoryRequest {
  name: string;
  color?: string;
}

export interface UpdateCategoryRequest {
  name?: string;
  color?: string;
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
  model_id?: string | null;
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

// Settings
export interface UserSettings {
  notifications_enabled: boolean;
  email_notifications: boolean;
  reminder_notifications: boolean;
  calendar_notifications: boolean;
  theme: 'light' | 'dark' | 'auto';
  font_size: 'small' | 'medium' | 'large';
  timezone?: string;
}

export interface UpdateProfileRequest {
  username?: string;
  email?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface GoogleCalendarSettings {
  connected: boolean;
  sync_enabled: boolean;
  calendar_id?: string;
  last_synced_at?: string;
}

export interface OpenMemorySettings {
  enabled: boolean;
  url?: string;
}

// Chat Conversations
export interface ChatConversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ChatMessagePersisted {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: any[];
  citations?: any[];
  created_at: string;
}

export interface ConversationWithMessages {
  conversation: ChatConversation;
  messages: ChatMessagePersisted[];
}

export interface CreateMessageRequest {
  conversation_id?: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: any[];
  citations?: any[];
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
