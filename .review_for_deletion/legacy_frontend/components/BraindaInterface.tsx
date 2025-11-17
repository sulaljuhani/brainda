'use client';

import { formatDistanceToNow } from 'date-fns';
import type { KeyboardEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';

import WeeklyCalendar from './WeeklyCalendar';

type MessageRole = 'user' | 'assistant';

type ToolCall = {
  icon: string;
  name: string;
  result: string;
  status?: 'success' | 'error';
};

type Message = {
  id: string;
  role: MessageRole;
  text: string;
  timestamp: Date;
  toolCall?: ToolCall;
  actions?: string[];
};

type NavItem = {
  id: string;
  label: string;
  icon: string;
};

const GLOBAL_STYLES = `
  :root {
    --bg-primary: #1a1a1a;
    --bg-secondary: #212121;
    --bg-tertiary: #2a2a2a;
    --bg-elevated: #242424;
    --text-primary: #e8e8e8;
    --text-secondary: #a8a8a8;
    --text-tertiary: #6e6e6e;
    --text-inverse: #1a1a1a;
    --accent-primary: #d97706;
    --accent-hover: #ea9c3e;
    --accent-active: #b45309;
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
    --info: #3b82f6;
    --border-subtle: #2a2a2a;
    --border-default: #3a3a3a;
    --border-strong: #4a4a4a;
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.6);
    --glass-bg: rgba(33, 33, 33, 0.7);
    --glass-border: rgba(255, 255, 255, 0.1);
    --backdrop-blur: blur(20px);
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji';
    --font-mono: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
    --font-display: 'Inter', var(--font-sans);
    --text-xs: 0.75rem;
    --text-sm: 0.875rem;
    --text-base: 1rem;
    --text-lg: 1.125rem;
    --text-xl: 1.25rem;
    --text-2xl: 1.5rem;
    --text-3xl: 1.875rem;
    --text-4xl: 2.25rem;
    --font-normal: 400;
    --font-medium: 500;
    --font-semibold: 600;
    --font-bold: 700;
    --space-1: 0.25rem;
    --space-2: 0.5rem;
    --space-3: 0.75rem;
    --space-4: 1rem;
    --space-5: 1.25rem;
    --space-6: 1.5rem;
    --space-8: 2rem;
    --space-10: 2.5rem;
    --space-12: 3rem;
    --space-16: 4rem;
    --space-20: 5rem;
    --container-xs: 480px;
    --container-sm: 640px;
    --container-md: 768px;
    --container-lg: 1024px;
    --container-xl: 1280px;
    --container-2xl: 1536px;
    --header-height: 56px;
    --sidebar-width: 280px;
    --sidebar-collapsed: 64px;
    --max-chat-width: 768px;
    --radius-sm: 0.375rem;
    --radius-md: 0.5rem;
    --radius-lg: 0.75rem;
    --radius-xl: 1rem;
    --radius-2xl: 1.5rem;
    --radius-full: 9999px;
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
  }

  .brainda-app {
    min-height: 100vh;
    background: radial-gradient(circle at top left, rgba(234, 156, 62, 0.12), transparent 50%),
      var(--bg-primary);
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
  }

  .brainda-header {
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-6);
    background: color-mix(in srgb, var(--bg-secondary) 85%, transparent);
    border-bottom: 1px solid var(--border-default);
    position: sticky;
    top: 0;
    z-index: 10;
    backdrop-filter: var(--backdrop-blur);
  }

  .brainda-header-section {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .brainda-logo {
    font-family: var(--font-display);
    font-weight: var(--font-semibold);
    font-size: var(--text-xl);
    letter-spacing: 0.12em;
  }

  .brainda-search {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 240px;
    background: color-mix(in srgb, var(--bg-tertiary) 80%, transparent);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-2) var(--space-3);
    transition: all 0.2s ease;
    box-shadow: var(--shadow-sm);
  }

  .brainda-search:focus-within {
    width: 320px;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 1px var(--accent-primary);
    background: var(--bg-elevated);
  }

  .brainda-search input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-primary);
    font-size: var(--text-sm);
  }

  .brainda-icon-button {
    position: relative;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
    background: color-mix(in srgb, var(--bg-tertiary) 90%, transparent);
    color: var(--text-secondary);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .brainda-icon-button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .brainda-notification-badge {
    position: absolute;
    top: -6px;
    right: -4px;
    background: var(--accent-primary);
    color: var(--text-inverse);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    padding: 2px 6px;
    box-shadow: var(--shadow-md);
  }

  .brainda-avatar {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    background: linear-gradient(135deg, rgba(234, 156, 62, 0.4), rgba(217, 119, 6, 0.6));
    color: var(--text-inverse);
    display: grid;
    place-items: center;
    font-weight: var(--font-semibold);
    letter-spacing: 0.04em;
    box-shadow: var(--shadow-md);
  }

  .brainda-main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .brainda-sidebar {
    width: var(--sidebar-width);
    background: color-mix(in srgb, var(--bg-primary) 85%, transparent);
    border-right: 1px solid var(--border-subtle);
    padding: var(--space-6) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    transition: width 0.25s ease;
  }

  .brainda-sidebar.collapsed {
    width: var(--sidebar-collapsed);
    padding-left: var(--space-3);
    padding-right: var(--space-3);
    align-items: center;
  }

  .brainda-nav {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .brainda-nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: var(--text-sm);
    border-left: 2px solid transparent;
  }

  .brainda-nav-item:hover {
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.04);
  }

  .brainda-nav-item.active {
    color: var(--accent-primary);
    background: rgba(217, 119, 6, 0.14);
    border-left-color: var(--accent-primary);
  }

  .brainda-nav-icon {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-full);
    background: rgba(234, 156, 62, 0.12);
    display: grid;
    place-items: center;
    font-size: var(--text-sm);
  }

  .brainda-sidebar.collapsed .brainda-nav-item {
    justify-content: center;
  }

  .brainda-sidebar.collapsed .brainda-nav-item span {
    display: none;
  }

  .brainda-section-title {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-tertiary);
    margin-bottom: var(--space-2);
  }

  .brainda-recent-item {
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    transition: background 0.2s ease;
    font-size: var(--text-sm);
    cursor: pointer;
  }

  .brainda-recent-item:hover {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
  }

  .brainda-divider {
    height: 1px;
    background: var(--border-subtle);
  }

  .brainda-collapse {
    margin-top: auto;
  }

  .brainda-collapse button {
    width: 100%;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-2);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .brainda-collapse button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .brainda-sidebar.collapsed .brainda-collapse button span {
    display: none;
  }

  .brainda-chat {
    flex: 1;
    display: flex;
    justify-content: center;
    overflow: hidden;
    padding: var(--space-6);
  }

  .brainda-calendar-pane {
    width: 360px;
    border-left: 1px solid var(--border-subtle);
    background: color-mix(in srgb, var(--bg-tertiary) 85%, transparent);
    padding: var(--space-6) var(--space-4);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .weekly-calendar {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .weekly-calendar .calendar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .weekly-calendar .calendar-header h2 {
    font-size: var(--text-lg);
    margin: 0;
  }

  .weekly-calendar .calendar-header button {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-2);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .weekly-calendar .calendar-header button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
  }

  .weekly-calendar .calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 1px;
    background: rgba(255, 255, 255, 0.04);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .weekly-calendar .calendar-day {
    background: rgba(24, 24, 24, 0.8);
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 160px;
  }

  .weekly-calendar .day-header {
    font-weight: var(--font-semibold);
    color: var(--text-secondary);
  }

  .weekly-calendar .day-events {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .weekly-calendar .event {
    background: rgba(25, 118, 210, 0.15);
    border-left: 3px solid rgba(25, 118, 210, 0.7);
    padding: var(--space-2);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .weekly-calendar .event.recurring {
    background: rgba(123, 31, 162, 0.15);
    border-left-color: rgba(123, 31, 162, 0.7);
  }

  .weekly-calendar .event.empty {
    background: transparent;
    border-left: none;
    color: var(--text-tertiary);
    text-align: center;
    padding: var(--space-2) 0;
  }

  .weekly-calendar .event-time {
    font-weight: var(--font-semibold);
    color: var(--accent-primary);
  }

  .weekly-calendar .event-title {
    font-weight: var(--font-medium);
  }

  .weekly-calendar .event-location {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .weekly-calendar .calendar-loading,
  .weekly-calendar .calendar-error {
    padding: var(--space-3);
    text-align: center;
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.05);
  }

  .weekly-calendar .calendar-error {
    color: var(--error);
  }

  .brainda-chat-surface {
    max-width: var(--max-chat-width);
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .brainda-message-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    overflow-y: auto;
    padding-right: var(--space-2);
    scrollbar-width: thin;
    scrollbar-color: rgba(255, 255, 255, 0.12) transparent;
  }

  .brainda-message-list::-webkit-scrollbar {
    width: 6px;
  }

  .brainda-message-list::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-full);
  }

  .brainda-message {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    animation: brainda-fade-in 0.25s ease;
  }

  .brainda-message.user {
    flex-direction: row-reverse;
    text-align: right;
  }

  .brainda-avatar-ring {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    display: grid;
    place-items: center;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.04);
  }

  .brainda-avatar-ring.ai {
    background: radial-gradient(circle at 30% 30%, rgba(234, 156, 62, 0.3), rgba(33, 33, 33, 0.9));
    border-color: rgba(217, 119, 6, 0.4);
  }

  .brainda-message-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    max-width: 100%;
  }

  .brainda-message-bubble {
    font-size: var(--text-base);
    line-height: 1.6;
    letter-spacing: 0.01em;
    color: var(--text-primary);
  }

  .brainda-message.user .brainda-message-bubble {
    background: rgba(217, 119, 6, 0.14);
    border: 1px solid rgba(234, 156, 62, 0.3);
    border-radius: var(--radius-lg);
    padding: var(--space-3) var(--space-4);
    box-shadow: var(--shadow-sm);
  }

  .brainda-message.assistant .brainda-message-bubble {
    padding: var(--space-1) 0;
  }

  .brainda-tool-call {
    border: 1px solid rgba(16, 185, 129, 0.24);
    background: rgba(16, 185, 129, 0.1);
    border-radius: var(--radius-lg);
    padding: var(--space-3) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }

  .brainda-tool-call-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: var(--font-medium);
  }

  .brainda-tool-call-result {
    color: var(--success);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }

  .brainda-message-meta {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  .brainda-message-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .brainda-message-actions button {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-full);
    color: var(--text-secondary);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .brainda-message-actions button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .brainda-chat-input {
    background: color-mix(in srgb, var(--bg-elevated) 85%, transparent);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-2xl);
    box-shadow: var(--shadow-lg);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    position: sticky;
    bottom: var(--space-6);
  }

  .brainda-textarea {
    background: transparent;
    border: none;
    resize: none;
    color: var(--text-primary);
    font-size: var(--text-base);
    line-height: 1.6;
    font-family: var(--font-sans);
    max-height: 200px;
    outline: none;
  }

  .brainda-composer-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .brainda-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .brainda-toolbar button {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-secondary);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .brainda-toolbar button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .brainda-send-button {
    border: none;
    border-radius: var(--radius-full);
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-hover));
    color: var(--text-inverse);
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }

  .brainda-send-button:disabled {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-tertiary);
    cursor: not-allowed;
    box-shadow: none;
  }

  .brainda-send-button:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  .brainda-status {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .brainda-status-dot {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    background: var(--accent-primary);
    animation: brainda-pulse 1.2s infinite;
  }

  .brainda-empty-state {
    text-align: center;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    padding: var(--space-6);
    border: 1px dashed var(--border-subtle);
    border-radius: var(--radius-xl);
    background: rgba(255, 255, 255, 0.02);
  }

  @keyframes brainda-fade-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes brainda-pulse {
    0%, 100% {
      opacity: 0.2;
      transform: scale(1);
    }
    50% {
      opacity: 1;
      transform: scale(1.3);
    }
  }

  @media (max-width: 1024px) {
    .brainda-sidebar {
      display: none;
    }

    .brainda-chat {
      padding: var(--space-4);
    }

    .brainda-calendar-pane {
      display: none;
    }

    .brainda-chat-input {
      border-radius: var(--radius-xl);
    }
  }

  @media (max-width: 640px) {
    .brainda-header {
      flex-wrap: wrap;
      gap: var(--space-3);
      padding: 0 var(--space-4);
    }

    .brainda-search {
      width: 100%;
    }

    .brainda-search:focus-within {
      width: 100%;
    }

    .brainda-header-section {
      width: 100%;
      justify-content: space-between;
    }

    .brainda-chat {
      padding: var(--space-3);
    }

    .brainda-chat-input {
      padding: var(--space-3);
    }
  }
`;

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'notes', label: 'Notes', icon: '📝' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'reminders', label: 'Reminders', icon: '⏰' },
  { id: 'calendar', label: 'Calendar', icon: '📆' },
  { id: 'search', label: 'Search', icon: '🔎' },
];

const INITIAL_MESSAGES: Message[] = [
  {
    id: 'welcome',
    role: 'assistant',
    text: 'Good afternoon! Ready to capture notes, schedule reminders, or search your workspace.',
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
    actions: ['Copy', 'Regenerate'],
  },
  {
    id: 'user-1',
    role: 'user',
    text: 'Remind me to call the bank at 5pm about the mortgage paperwork.',
    timestamp: new Date(Date.now() - 4 * 60 * 1000),
  },
  {
    id: 'assistant-1',
    role: 'assistant',
    text: "I've set a reminder for 5:00 PM today to call the bank about the mortgage paperwork.",
    timestamp: new Date(Date.now() - 4 * 60 * 1000 + 45 * 1000),
    toolCall: {
      icon: '⏰',
      name: 'create_reminder',
      result: '✓ Reminder scheduled for 5:00 PM today',
      status: 'success',
    },
    actions: ['Copy', 'Regenerate'],
  },
];

function generateAssistantResponse(input: string): { text: string; toolCall?: ToolCall } {
  const trimmed = input.trim().toLowerCase();

  if (!trimmed) {
    return { text: '' };
  }

  if (trimmed.includes('remind')) {
    return {
      text: "Reminder created! I'll let you know when it's time.",
      toolCall: {
        icon: '⏰',
        name: 'create_reminder',
        result: '✓ Reminder scheduled with natural language parsing',
        status: 'success',
      },
    };
  }

  if (trimmed.includes('note')) {
    return {
      text: 'Captured a new note and tagged it with your latest context. Anything else to add?',
      toolCall: {
        icon: '📝',
        name: 'save_note',
        result: '✓ Note stored with current workspace tags',
        status: 'success',
      },
    };
  }

  if (trimmed.includes('document')) {
    return {
      text: 'Document search is complete. I found a few relevant matches in your workspace.',
      toolCall: {
        icon: '📄',
        name: 'semantic_search',
        result: '• Project roadmap v2\n• Contract summary draft\n• Meeting notes — finance sync',
        status: 'success',
      },
    };
  }

  return {
    text: "Here's what I found: I searched your workspace and summarized the highlights for you.",
  };
}

export default function BraindaInterface() {
  const [activeNav, setActiveNav] = useState<string>('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const streamingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (streamingIntervalRef.current) {
        window.clearInterval(streamingIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputValue]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const notificationCount = useMemo(() => 3, []);
  const recentItems = useMemo(() => ['Project kickoff notes', 'Weekly planning', 'Finance summary'], []);

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      text: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    const { text, toolCall } = generateAssistantResponse(trimmed);
    if (!text && !toolCall) {
      return;
    }

    const assistantId = `assistant-${Date.now()}`;

    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      text: '',
      timestamp: new Date(),
      toolCall,
      actions: ['Copy', 'Regenerate'],
    };

    setMessages((prev) => [...prev, assistantMessage]);
    setIsStreaming(true);

    const fullText = text;
    let index = 0;

    if (streamingIntervalRef.current) {
      window.clearInterval(streamingIntervalRef.current);
    }

    streamingIntervalRef.current = window.setInterval(() => {
      index += 1;
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                text: fullText.slice(0, index),
              }
            : message,
        ),
      );

      if (index >= fullText.length) {
        if (streamingIntervalRef.current) {
          window.clearInterval(streamingIntervalRef.current);
        }
        streamingIntervalRef.current = null;
        setIsStreaming(false);
      }
    }, 18);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const formattedMessages = useMemo(
    () =>
      messages.map((message) => ({
        ...message,
        relativeTime: formatDistanceToNow(message.timestamp, { addSuffix: true }),
      })),
    [messages],
  );

  return (
    <div className="brainda-app">
      <style>{GLOBAL_STYLES}</style>
      <header className="brainda-header">
        <div className="brainda-header-section">
          <div className="brainda-logo">Brainda</div>
          <label className="brainda-search" aria-label="Search conversations and notes">
            <span role="img" aria-hidden="true">
              🔍
            </span>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search workspace"
            />
          </label>
        </div>
        <div className="brainda-header-section">
          <button className="brainda-icon-button" type="button" aria-label="Notifications">
            <span role="img" aria-hidden="true">
              🔔
            </span>
            {notificationCount > 0 ? (
              <span className="brainda-notification-badge">{notificationCount}</span>
            ) : null}
          </button>
          <button className="brainda-icon-button" type="button" aria-label="Settings">
            <span role="img" aria-hidden="true">
              ⚙️
            </span>
          </button>
          <div className="brainda-avatar" aria-label="User avatar">
            JD
          </div>
        </div>
      </header>
      <div className="brainda-main">
        <aside className={`brainda-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`} aria-label="Primary navigation">
          <nav className="brainda-nav">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`brainda-nav-item ${activeNav === item.id ? 'active' : ''}`}
                onClick={() => setActiveNav(item.id)}
              >
                <span className="brainda-nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          <div className="brainda-divider" aria-hidden="true" />
          <div>
            <div className="brainda-section-title">Recent</div>
            <div>
              {recentItems.map((item) => (
                <div key={item} className="brainda-recent-item">
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="brainda-collapse">
            <button type="button" onClick={() => setSidebarCollapsed((previous) => !previous)}>
              <span role="img" aria-hidden="true">
                {sidebarCollapsed ? '➡️' : '⬅️'}
              </span>
              <span>{sidebarCollapsed ? 'Expand' : 'Collapse'}</span>
            </button>
          </div>
        </aside>
        <main className="brainda-chat">
          <section className="brainda-chat-surface" aria-label="Chat conversation">
            <div className="brainda-message-list">
              {formattedMessages.length === 0 ? (
                <div className="brainda-empty-state">Start a conversation to see messages here.</div>
              ) : (
                formattedMessages.map((message) => (
                  <article
                    key={message.id}
                    className={`brainda-message ${message.role}`}
                    aria-live={message.role === 'assistant' ? 'polite' : undefined}
                  >
                    <div className={`brainda-avatar-ring ${message.role === 'assistant' ? 'ai' : ''}`} aria-hidden="true">
                      {message.role === 'assistant' ? '✨' : '🙂'}
                    </div>
                    <div className="brainda-message-content">
                      {message.toolCall ? (
                        <div className="brainda-tool-call" role="status">
                          <div className="brainda-tool-call-header">
                            <span aria-hidden="true">{message.toolCall.icon}</span>
                            <span>{message.toolCall.name}</span>
                          </div>
                          <div className="brainda-tool-call-result">{message.toolCall.result}</div>
                        </div>
                      ) : null}
                      <div className="brainda-message-bubble">{message.text}</div>
                      <div className="brainda-message-meta">
                        <span>{message.relativeTime}</span>
                      </div>
                      {message.actions && message.actions.length > 0 ? (
                        <div className="brainda-message-actions">
                          {message.actions.map((action) => (
                            <button key={action} type="button">
                              {action}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </article>
                ))
              )}
              <div ref={messageEndRef} />
            </div>
            <form
              className="brainda-chat-input"
              onSubmit={(event) => {
                event.preventDefault();
                handleSend();
              }}
            >
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything, create notes, set reminders..."
                className="brainda-textarea"
                aria-label="Message composer"
                rows={1}
              />
              <div className="brainda-composer-footer">
                <div className="brainda-toolbar">
                  <button type="button" aria-label="Attach a document">
                    📎
                  </button>
                  <button type="button" aria-label="Record a voice memo">
                    🎤
                  </button>
                  <button type="button" aria-label="Open quick commands">
                    ⚡
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  {isStreaming ? (
                    <div className="brainda-status">
                      <span className="brainda-status-dot" aria-hidden="true" />
                      <span>Assistant is responding...</span>
                    </div>
                  ) : null}
                  <button className="brainda-send-button" type="submit" disabled={!inputValue.trim()}>
                    Send
                  </button>
                </div>
              </div>
            </form>
          </section>
        </main>
        <aside className="brainda-calendar-pane" aria-label="Weekly calendar overview">
          <WeeklyCalendar />
        </aside>
      </div>
    </div>
  );
}
