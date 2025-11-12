'use client';

import { formatDistanceToNow } from 'date-fns';
import type { KeyboardEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';

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

  .vib-app {
    min-height: 100vh;
    background: radial-gradient(circle at top left, rgba(234, 156, 62, 0.12), transparent 50%),
      var(--bg-primary);
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
  }

  .vib-header {
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

  .vib-header-section {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .vib-logo {
    font-family: var(--font-display);
    font-weight: var(--font-semibold);
    font-size: var(--text-xl);
    letter-spacing: 0.12em;
  }

  .vib-search {
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

  .vib-search:focus-within {
    width: 320px;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 1px var(--accent-primary);
    background: var(--bg-elevated);
  }

  .vib-search input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-primary);
    font-size: var(--text-sm);
  }

  .vib-icon-button {
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

  .vib-icon-button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .vib-notification-badge {
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

  .vib-avatar {
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

  .vib-main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .vib-sidebar {
    width: var(--sidebar-width);
    background: color-mix(in srgb, var(--bg-primary) 85%, transparent);
    border-right: 1px solid var(--border-subtle);
    padding: var(--space-6) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    transition: width 0.25s ease;
  }

  .vib-sidebar.collapsed {
    width: var(--sidebar-collapsed);
    padding-left: var(--space-3);
    padding-right: var(--space-3);
    align-items: center;
  }

  .vib-nav {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .vib-nav-item {
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

  .vib-nav-item:hover {
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.04);
  }

  .vib-nav-item.active {
    color: var(--accent-primary);
    background: rgba(217, 119, 6, 0.14);
    border-left-color: var(--accent-primary);
  }

  .vib-nav-icon {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-full);
    background: rgba(234, 156, 62, 0.12);
    display: grid;
    place-items: center;
    font-size: var(--text-sm);
  }

  .vib-sidebar.collapsed .vib-nav-item {
    justify-content: center;
  }

  .vib-sidebar.collapsed .vib-nav-item span {
    display: none;
  }

  .vib-section-title {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-tertiary);
    margin-bottom: var(--space-2);
  }

  .vib-recent-item {
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    transition: background 0.2s ease;
    font-size: var(--text-sm);
    cursor: pointer;
  }

  .vib-recent-item:hover {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
  }

  .vib-divider {
    height: 1px;
    background: var(--border-subtle);
  }

  .vib-collapse {
    margin-top: auto;
  }

  .vib-collapse button {
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

  .vib-collapse button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .vib-sidebar.collapsed .vib-collapse button span {
    display: none;
  }

  .vib-chat {
    flex: 1;
    display: flex;
    justify-content: center;
    overflow: hidden;
    padding: var(--space-6);
  }

  .vib-chat-surface {
    max-width: var(--max-chat-width);
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .vib-message-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    overflow-y: auto;
    padding-right: var(--space-2);
    scrollbar-width: thin;
    scrollbar-color: rgba(255, 255, 255, 0.12) transparent;
  }

  .vib-message-list::-webkit-scrollbar {
    width: 6px;
  }

  .vib-message-list::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-full);
  }

  .vib-message {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    animation: vib-fade-in 0.25s ease;
  }

  .vib-message.user {
    flex-direction: row-reverse;
    text-align: right;
  }

  .vib-avatar-ring {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    display: grid;
    place-items: center;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.04);
  }

  .vib-avatar-ring.ai {
    background: radial-gradient(circle at 30% 30%, rgba(234, 156, 62, 0.3), rgba(33, 33, 33, 0.9));
    border-color: rgba(217, 119, 6, 0.4);
  }

  .vib-message-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    max-width: 100%;
  }

  .vib-message-bubble {
    font-size: var(--text-base);
    line-height: 1.6;
    letter-spacing: 0.01em;
    color: var(--text-primary);
  }

  .vib-message.user .vib-message-bubble {
    background: rgba(217, 119, 6, 0.14);
    border: 1px solid rgba(234, 156, 62, 0.3);
    border-radius: var(--radius-lg);
    padding: var(--space-3) var(--space-4);
    box-shadow: var(--shadow-sm);
  }

  .vib-message.assistant .vib-message-bubble {
    padding: var(--space-1) 0;
  }

  .vib-tool-call {
    border: 1px solid rgba(16, 185, 129, 0.24);
    background: rgba(16, 185, 129, 0.1);
    border-radius: var(--radius-lg);
    padding: var(--space-3) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }

  .vib-tool-call-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: var(--font-medium);
  }

  .vib-tool-call-result {
    color: var(--success);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }

  .vib-message-meta {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  .vib-message-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .vib-message-actions button {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-full);
    color: var(--text-secondary);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .vib-message-actions button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .vib-chat-input {
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

  .vib-textarea {
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

  .vib-composer-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .vib-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .vib-toolbar button {
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

  .vib-toolbar button:hover {
    color: var(--accent-primary);
    border-color: var(--accent-primary);
    transform: translateY(-1px);
  }

  .vib-send-button {
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

  .vib-send-button:disabled {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-tertiary);
    cursor: not-allowed;
    box-shadow: none;
  }

  .vib-send-button:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  .vib-status {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .vib-status-dot {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    background: var(--accent-primary);
    animation: vib-pulse 1.2s infinite;
  }

  .vib-empty-state {
    text-align: center;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    padding: var(--space-6);
    border: 1px dashed var(--border-subtle);
    border-radius: var(--radius-xl);
    background: rgba(255, 255, 255, 0.02);
  }

  @keyframes vib-fade-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes vib-pulse {
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
    .vib-sidebar {
      display: none;
    }

    .vib-chat {
      padding: var(--space-4);
    }

    .vib-chat-input {
      border-radius: var(--radius-xl);
    }
  }

  @media (max-width: 640px) {
    .vib-header {
      flex-wrap: wrap;
      gap: var(--space-3);
      padding: 0 var(--space-4);
    }

    .vib-search {
      width: 100%;
    }

    .vib-search:focus-within {
      width: 100%;
    }

    .vib-header-section {
      width: 100%;
      justify-content: space-between;
    }

    .vib-chat {
      padding: var(--space-3);
    }

    .vib-chat-input {
      padding: var(--space-3);
    }
  }
`;

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'notes', label: 'Notes', icon: '📝' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'reminders', label: 'Reminders', icon: '⏰' },
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

export default function VibInterface() {
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
    <div className="vib-app">
      <style>{GLOBAL_STYLES}</style>
      <header className="vib-header">
        <div className="vib-header-section">
          <div className="vib-logo">VIB</div>
          <label className="vib-search" aria-label="Search conversations and notes">
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
        <div className="vib-header-section">
          <button className="vib-icon-button" type="button" aria-label="Notifications">
            <span role="img" aria-hidden="true">
              🔔
            </span>
            {notificationCount > 0 ? (
              <span className="vib-notification-badge">{notificationCount}</span>
            ) : null}
          </button>
          <button className="vib-icon-button" type="button" aria-label="Settings">
            <span role="img" aria-hidden="true">
              ⚙️
            </span>
          </button>
          <div className="vib-avatar" aria-label="User avatar">
            JD
          </div>
        </div>
      </header>
      <div className="vib-main">
        <aside className={`vib-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`} aria-label="Primary navigation">
          <nav className="vib-nav">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`vib-nav-item ${activeNav === item.id ? 'active' : ''}`}
                onClick={() => setActiveNav(item.id)}
              >
                <span className="vib-nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          <div className="vib-divider" aria-hidden="true" />
          <div>
            <div className="vib-section-title">Recent</div>
            <div>
              {recentItems.map((item) => (
                <div key={item} className="vib-recent-item">
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="vib-collapse">
            <button type="button" onClick={() => setSidebarCollapsed((previous) => !previous)}>
              <span role="img" aria-hidden="true">
                {sidebarCollapsed ? '➡️' : '⬅️'}
              </span>
              <span>{sidebarCollapsed ? 'Expand' : 'Collapse'}</span>
            </button>
          </div>
        </aside>
        <main className="vib-chat">
          <section className="vib-chat-surface" aria-label="Chat conversation">
            <div className="vib-message-list">
              {formattedMessages.length === 0 ? (
                <div className="vib-empty-state">Start a conversation to see messages here.</div>
              ) : (
                formattedMessages.map((message) => (
                  <article
                    key={message.id}
                    className={`vib-message ${message.role}`}
                    aria-live={message.role === 'assistant' ? 'polite' : undefined}
                  >
                    <div className={`vib-avatar-ring ${message.role === 'assistant' ? 'ai' : ''}`} aria-hidden="true">
                      {message.role === 'assistant' ? '✨' : '🙂'}
                    </div>
                    <div className="vib-message-content">
                      {message.toolCall ? (
                        <div className="vib-tool-call" role="status">
                          <div className="vib-tool-call-header">
                            <span aria-hidden="true">{message.toolCall.icon}</span>
                            <span>{message.toolCall.name}</span>
                          </div>
                          <div className="vib-tool-call-result">{message.toolCall.result}</div>
                        </div>
                      ) : null}
                      <div className="vib-message-bubble">{message.text}</div>
                      <div className="vib-message-meta">
                        <span>{message.relativeTime}</span>
                      </div>
                      {message.actions && message.actions.length > 0 ? (
                        <div className="vib-message-actions">
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
              className="vib-chat-input"
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
                className="vib-textarea"
                aria-label="Message composer"
                rows={1}
              />
              <div className="vib-composer-footer">
                <div className="vib-toolbar">
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
                    <div className="vib-status">
                      <span className="vib-status-dot" aria-hidden="true" />
                      <span>Assistant is responding...</span>
                    </div>
                  ) : null}
                  <button className="vib-send-button" type="submit" disabled={!inputValue.trim()}>
                    Send
                  </button>
                </div>
              </div>
            </form>
          </section>
        </main>
      </div>
    </div>
  );
}
