# Stage 4: Chat Page (Primary Interface)

**Duration**: 3-4 days
**Priority**: CRITICAL (Main page)
**Dependencies**: Stages 1, 2, 3

---

## Goal

Build the main chat interface with streaming responses, tool calls, citations, and real-time interaction.

---

## Key Features

- Chat is the default/home page (/)
- Streaming message responses
- Tool call visualization
- Citation display
- Message history
- Auto-scroll to latest message
- Markdown rendering
- Code syntax highlighting
- Copy message functionality

---

## Components to Build

### 1. ChatPage (Main Container)
**File**: `src/pages/ChatPage.tsx`

Responsibilities:
- Manage message state
- Handle message sending
- Integrate chat streaming
- Scroll management

### 2. MessageList
**File**: `src/components/chat/MessageList.tsx`

Responsibilities:
- Display all messages
- Auto-scroll to bottom
- Virtualization for performance
- Empty state

### 3. MessageBubble
**File**: `src/components/chat/MessageBubble.tsx`

Responsibilities:
- Render user/assistant messages
- Markdown rendering
- Code blocks with syntax highlighting
- Copy button
- Timestamp display

### 4. ToolCallCard
**File**: `src/components/chat/ToolCallCard.tsx`

Responsibilities:
- Display tool name and icon
- Show parameters (collapsible)
- Show result with status
- Success/error states

### 5. CitationInline
**File**: `src/components/chat/CitationInline.tsx`

Responsibilities:
- Superscript number
- Hover popover with preview
- Click to expand
- Source metadata

### 6. ChatInput
**File**: `src/components/chat/ChatInput.tsx`

Responsibilities:
- Auto-resizing textarea
- Send button
- Attachment button (future)
- Character count
- Enter to send, Shift+Enter for newline
- Loading state while streaming

### 7. TypingIndicator
**File**: `src/components/chat/TypingIndicator.tsx`

Responsibilities:
- Animated dots
- Show while streaming

---

## Implementation Details

### Streaming Chat Implementation

```typescript
async function sendMessage(text: string) {
  const stream = await chatService.sendMessage(text);
  const reader = stream.getReader();
  const decoder = new TextDecoder();

  let assistantMessage = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    assistantMessage += chunk;

    // Update UI incrementally
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === 'assistant' && !last.complete) {
        return [...prev.slice(0, -1), { ...last, text: assistantMessage }];
      }
      return [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        text: assistantMessage,
        timestamp: new Date(),
        complete: false,
      }];
    });
  }

  // Mark message as complete
  setMessages(prev => {
    const last = prev[prev.length - 1];
    return [...prev.slice(0, -1), { ...last, complete: true }];
  });
}
```

---

## Dependencies to Install

```bash
npm install react-markdown remark-gfm rehype-highlight
npm install date-fns
```

---

## Testing Checklist

- [ ] Can send messages
- [ ] Streaming works (char by char)
- [ ] Tool calls display correctly
- [ ] Citations show in popover
- [ ] Auto-scroll works
- [ ] Copy message works
- [ ] Code blocks have syntax highlighting
- [ ] Empty state shows initially
- [ ] Enter sends, Shift+Enter adds newline
- [ ] Mobile responsive

---

## Deliverables

- [x] Full chat interface
- [x] Streaming responses
- [x] Tool call visualization
- [x] Citation display
- [x] Message history
- [x] Markdown support
- [x] Code highlighting
- [x] Empty state

---

## Next Stage

Can proceed to other pages (Stages 5-11) in parallel.
