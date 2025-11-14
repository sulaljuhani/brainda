# UX Components Usage Guide

This guide explains how to use the UX polish components added in Stage 12.

## Table of Contents
- [Toast Notifications](#toast-notifications)
- [Error Boundary](#error-boundary)
- [Skeleton Screens](#skeleton-screens)
- [Empty States](#empty-states)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Animations](#animations)

---

## Toast Notifications

Show toast notifications to users for feedback on actions.

### Basic Usage

```tsx
import { useToast } from '../../contexts/ToastContext';

function MyComponent() {
  const toast = useToast();

  const handleSuccess = () => {
    toast.success('Note saved successfully!');
  };

  const handleError = () => {
    toast.error('Failed to save note');
  };

  const handleWarning = () => {
    toast.warning('This action cannot be undone');
  };

  const handleInfo = () => {
    toast.info('New feature available!');
  };

  return (
    <button onClick={handleSuccess}>Save</button>
  );
}
```

### Custom Duration

```tsx
// Show for 3 seconds (default is 5 seconds)
toast.success('Quick message', 3000);

// Show indefinitely (until user closes)
toast.error('Critical error', 0);
```

---

## Error Boundary

Catch and display errors gracefully in your components.

### Basic Usage

```tsx
import { ErrorBoundary } from '../../components/shared/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      <MyComponent />
    </ErrorBoundary>
  );
}
```

### Custom Fallback

```tsx
<ErrorBoundary fallback={<div>Custom error message</div>}>
  <MyComponent />
</ErrorBoundary>
```

### Wrapping Routes

```tsx
<ErrorBoundary>
  <Routes>
    <Route path="/" element={<ChatPage />} />
    <Route path="/notes" element={<NotesPage />} />
  </Routes>
</ErrorBoundary>
```

---

## Skeleton Screens

Show loading placeholders while content is loading.

### Basic Skeleton

```tsx
import { Skeleton } from '../../components/shared/SkeletonScreen';

function MyComponent() {
  const { loading, data } = useData();

  if (loading) {
    return (
      <div>
        <Skeleton width="70%" height={24} variant="text" />
        <Skeleton width="100%" height={16} variant="text" />
        <Skeleton width={40} height={40} variant="circular" />
      </div>
    );
  }

  return <div>{data}</div>;
}
```

### Pre-built Skeletons

```tsx
import {
  SkeletonNote,
  SkeletonChatMessage,
  SkeletonReminder,
  SkeletonDocument,
  SkeletonCalendarEvent,
  SkeletonList
} from '../../components/shared/SkeletonScreen';

// Notes page
if (loading) return <SkeletonNote />;

// Chat page
if (loading) return <SkeletonChatMessage />;

// Reminders page
if (loading) return <SkeletonReminder />;

// Documents page
if (loading) return <SkeletonDocument />;

// Calendar page
if (loading) return <SkeletonCalendarEvent />;

// Generic list
if (loading) return <SkeletonList count={5} />;
```

---

## Empty States

Display friendly messages when there's no data.

### Basic Usage

```tsx
import { EmptyState } from '../../components/shared/EmptyState';
import { FileText } from 'lucide-react';

function NotesPage() {
  const { notes } = useNotes();

  if (notes.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No notes yet"
        description="Create your first note to get started"
        action={{
          label: 'Create Note',
          onClick: () => setShowCreateModal(true)
        }}
      />
    );
  }

  return <NotesList notes={notes} />;
}
```

### Without Action Button

```tsx
<EmptyState
  icon={Search}
  title="No results found"
  description="Try adjusting your search terms"
/>
```

### With Custom Content

```tsx
<EmptyState
  icon={Calendar}
  title="No events today"
  description="Your calendar is clear"
>
  <button onClick={createEvent}>Add Event</button>
</EmptyState>
```

---

## Keyboard Shortcuts

Add keyboard shortcuts help to your app.

### Global Shortcuts Button

Add this to your header or sidebar:

```tsx
import { KeyboardShortcutsButton } from '../../components/shared/KeyboardShortcuts';

function Header() {
  return (
    <header>
      <h1>Brainda</h1>
      <KeyboardShortcutsButton />
    </header>
  );
}
```

### Using the Hook

```tsx
import { useKeyboardShortcuts } from '../../components/shared/KeyboardShortcuts';

function MyComponent() {
  const [showHelp, setShowHelp] = useState(false);

  // Automatically listens for '?' key press
  useKeyboardShortcuts(() => setShowHelp(true));

  return (
    <div>
      <KeyboardShortcuts
        isOpen={showHelp}
        onClose={() => setShowHelp(false)}
      />
    </div>
  );
}
```

### Customizing Shortcuts

Edit the `shortcuts` array in `KeyboardShortcuts.tsx` to add/remove shortcuts:

```tsx
const shortcuts: Shortcut[] = [
  { keys: ['Ctrl', 'S'], description: 'Save', category: 'General' },
  // Add more shortcuts...
];
```

---

## Animations

Use pre-built animation utilities for smooth transitions.

### CSS Animation Classes

```tsx
// Fade in animation
<div className="animate-fade-in">Content</div>

// Fade in from bottom
<div className="animate-fade-in-up">Content</div>

// Slide in from left
<div className="animate-slide-in-left">Content</div>

// Scale in
<div className="animate-scale-in">Content</div>

// Bounce
<div className="animate-bounce">Content</div>

// Pulse (infinite)
<div className="animate-pulse">Loading...</div>

// Spin (infinite)
<div className="animate-spin">⚙️</div>

// Shake
<div className="animate-shake">Error!</div>
```

### Transition Utilities

```tsx
// Smooth transitions for all properties
<button className="transition-all">Hover me</button>

// Only transition colors
<div className="transition-colors">Content</div>

// Only transition transform
<div className="transition-transform">Content</div>

// Only transition opacity
<div className="transition-opacity">Content</div>
```

### Hover Effects

```tsx
// Lift on hover
<div className="hover-lift">Card</div>

// Scale on hover
<div className="hover-scale">Button</div>

// Glow on hover
<div className="hover-glow">Input</div>
```

### Staggered List Animations

```tsx
<div>
  {items.map((item, index) => (
    <div key={item.id} className="stagger-item">
      {item.name}
    </div>
  ))}
</div>
```

### Framer Motion Animations

For more complex animations, use framer-motion directly:

```tsx
import { motion } from 'framer-motion';

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: -20 }}
  transition={{ duration: 0.3 }}
>
  Content
</motion.div>
```

---

## Complete Example

Here's a complete example using multiple UX components:

```tsx
import { useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { ErrorBoundary } from '../../components/shared/ErrorBoundary';
import { EmptyState } from '../../components/shared/EmptyState';
import { SkeletonNote } from '../../components/shared/SkeletonScreen';
import { KeyboardShortcutsButton } from '../../components/shared/KeyboardShortcuts';
import { FileText } from 'lucide-react';
import { useNotes } from '../../hooks/useNotes';

function NotesPage() {
  const toast = useToast();
  const { notes, loading, error, createNote } = useNotes();

  const handleCreateNote = async () => {
    try {
      await createNote({ title: 'New Note', body: '' });
      toast.success('Note created successfully!');
    } catch (err) {
      toast.error('Failed to create note');
    }
  };

  if (loading) {
    return (
      <div>
        <SkeletonNote />
        <SkeletonNote />
        <SkeletonNote />
      </div>
    );
  }

  if (error) {
    throw error; // Caught by ErrorBoundary
  }

  if (notes.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No notes yet"
        description="Create your first note to get started"
        action={{
          label: 'Create Note',
          onClick: handleCreateNote
        }}
      />
    );
  }

  return (
    <ErrorBoundary>
      <div className="notes-page">
        <header className="notes-header">
          <h1>Notes</h1>
          <KeyboardShortcutsButton />
        </header>
        <div className="notes-list">
          {notes.map((note) => (
            <div key={note.id} className="note-card animate-fade-in-up stagger-item">
              <h3>{note.title}</h3>
              <p>{note.body}</p>
            </div>
          ))}
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default NotesPage;
```

---

## Best Practices

### Toast Notifications
- ✅ Use success toasts for confirmations
- ✅ Use error toasts with longer duration (7s)
- ✅ Keep messages short and actionable
- ❌ Don't show toasts for every action
- ❌ Don't stack too many toasts at once

### Error Boundaries
- ✅ Wrap entire routes or major sections
- ✅ Use multiple boundaries for granular error handling
- ✅ Log errors to monitoring service in production
- ❌ Don't wrap every small component
- ❌ Don't hide critical errors

### Skeleton Screens
- ✅ Match the shape of actual content
- ✅ Use pre-built skeletons when possible
- ✅ Show skeletons immediately (don't delay)
- ❌ Don't show skeletons for < 200ms loads
- ❌ Don't use spinners when skeletons work better

### Empty States
- ✅ Provide clear next steps
- ✅ Use friendly, encouraging language
- ✅ Include relevant icons
- ❌ Don't use technical error messages
- ❌ Don't leave users with no action

### Animations
- ✅ Keep animations subtle (< 300ms)
- ✅ Use consistent timing across app
- ✅ Respect `prefers-reduced-motion`
- ❌ Don't animate on every interaction
- ❌ Don't use slow or distracting animations

---

## Accessibility

All components are built with accessibility in mind:

- **Toast**: Uses `role="alert"` and `aria-live="polite"`
- **ErrorBoundary**: Provides clear error messages
- **Skeleton**: Uses `aria-busy="true"` and `aria-live="polite"`
- **EmptyState**: Semantic HTML with proper headings
- **KeyboardShortcuts**: Full keyboard navigation support
- **Animations**: Respects `prefers-reduced-motion` setting

---

## Browser Support

- Chrome/Edge: Last 2 versions ✅
- Firefox: Last 2 versions ✅
- Safari: Last 2 versions ✅
- iOS Safari: Last 2 versions ✅
- Android Chrome: Last 2 versions ✅

---

**Last Updated**: 2025-01-14
**Stage**: 12 - Polish & UX Enhancements
