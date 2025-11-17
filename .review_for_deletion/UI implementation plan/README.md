# Brainda Web UI - Implementation Plan

## Project Overview

**Application Name**: Brainda
**Primary Interface**: Chat (main page)
**Architecture**: React 18 + TypeScript + Vite
**Backend**: FastAPI (existing)
**Target**: Modern browsers, mobile responsive

---

## Technical Stack

### Core Technologies
- **Frontend Framework**: React 18+ (functional components, hooks)
- **Language**: TypeScript (strict mode)
- **Build Tool**: Vite 5+
- **Routing**: React Router v6
- **State Management**: React Context + Custom Hooks
- **HTTP Client**: Native Fetch API
- **Date Library**: date-fns (already installed)
- **Icons**: Lucide React
- **Markdown**: react-markdown

### Development Tools
- **Package Manager**: npm
- **Linter**: ESLint
- **Formatter**: Prettier
- **Testing**: Vitest + React Testing Library
- **E2E Testing**: Playwright

---

## Project Structure

```
app/web/
├── src/
│   ├── main.tsx                    # Application entry point
│   ├── App.tsx                     # Root component with routing
│   │
│   ├── components/                 # Reusable components
│   │   ├── auth/                   # Authentication components
│   │   ├── chat/                   # Chat-specific components
│   │   ├── notes/                  # Note components
│   │   ├── reminders/              # Reminder components
│   │   ├── documents/              # Document components
│   │   ├── calendar/               # Calendar components
│   │   ├── search/                 # Search components
│   │   ├── settings/               # Settings components
│   │   ├── shared/                 # Shared UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   └── layout/                 # Layout components
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── MainLayout.tsx
│   │
│   ├── pages/                      # Page-level components
│   │   ├── ChatPage.tsx            # Main chat interface (default)
│   │   ├── NotesPage.tsx
│   │   ├── NoteDetailPage.tsx
│   │   ├── RemindersPage.tsx
│   │   ├── DocumentsPage.tsx
│   │   ├── CalendarPage.tsx
│   │   ├── SearchPage.tsx
│   │   ├── SettingsPage.tsx
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   └── NotFoundPage.tsx
│   │
│   ├── hooks/                      # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useNotes.ts
│   │   ├── useReminders.ts
│   │   ├── useDocuments.ts
│   │   ├── useCalendar.ts
│   │   ├── useChat.ts
│   │   ├── useSearch.ts
│   │   └── useLocalStorage.ts
│   │
│   ├── services/                   # API client services
│   │   ├── api.ts                  # Base API client
│   │   ├── notesService.ts
│   │   ├── remindersService.ts
│   │   ├── documentsService.ts
│   │   ├── calendarService.ts
│   │   ├── chatService.ts
│   │   └── authService.ts
│   │
│   ├── contexts/                   # React contexts
│   │   ├── AuthContext.tsx
│   │   ├── ThemeContext.tsx
│   │   └── SidebarContext.tsx
│   │
│   ├── types/                      # TypeScript type definitions
│   │   ├── api.ts                  # API response types
│   │   ├── models.ts               # Data models
│   │   └── index.ts                # Exports
│   │
│   ├── utils/                      # Utility functions
│   │   ├── formatters.ts           # Date, number formatters
│   │   ├── validators.ts           # Input validation
│   │   ├── constants.ts            # App constants
│   │   └── helpers.ts              # General helpers
│   │
│   └── styles/                     # Global styles
│       ├── global.css              # Global styles & CSS variables
│       ├── reset.css               # CSS reset
│       └── animations.css          # Reusable animations
│
├── public/                         # Static assets
│   ├── favicon.ico
│   └── service-worker.js           # PWA service worker
│
├── index.html                      # HTML entry point
├── vite.config.ts                  # Vite configuration
├── tsconfig.json                   # TypeScript configuration
├── package.json                    # Dependencies & scripts
├── .env.example                    # Environment variables template
└── README.md                       # Project documentation
```

---

## Code Standards

### TypeScript Guidelines

1. **Strict Mode**: Always use TypeScript strict mode
2. **Type Everything**: No `any` types except when absolutely necessary
3. **Interfaces over Types**: Prefer `interface` for object shapes
4. **Named Exports**: Use named exports instead of default exports (except for pages)
5. **Null Safety**: Handle null/undefined explicitly

```typescript
// ✅ Good
interface User {
  id: string;
  username: string;
  email?: string;
}

export function getUser(id: string): User | null {
  // Implementation
}

// ❌ Bad
export default function getUser(id: any): any {
  // Implementation
}
```

### React Guidelines

1. **Functional Components**: Always use functional components with hooks
2. **Component Structure**:
   ```typescript
   // 1. Imports
   import { useState, useEffect } from 'react';

   // 2. Types/Interfaces
   interface Props {
     title: string;
   }

   // 3. Component
   export function MyComponent({ title }: Props) {
     // 4. Hooks
     const [state, setState] = useState('');

     // 5. Effects
     useEffect(() => {}, []);

     // 6. Handlers
     const handleClick = () => {};

     // 7. Render
     return <div>{title}</div>;
   }
   ```

3. **Hooks Rules**:
   - Only call hooks at the top level
   - Custom hooks start with `use`
   - Keep hooks in separate files

4. **Props**:
   - Destructure props
   - Define prop types with interfaces
   - Use optional props sparingly

5. **State Management**:
   - Keep state as close to usage as possible
   - Lift state only when needed
   - Use Context for global state

### Naming Conventions

1. **Files**: PascalCase for components, camelCase for utilities
   - `UserProfile.tsx` (component)
   - `formatDate.ts` (utility)

2. **Components**: PascalCase
   - `ChatMessage`, `NoteCard`, `UserMenu`

3. **Functions**: camelCase
   - `getUserById`, `formatTimestamp`, `handleSubmit`

4. **Constants**: UPPER_SNAKE_CASE
   - `API_BASE_URL`, `MAX_FILE_SIZE`

5. **Types/Interfaces**: PascalCase
   - `User`, `ChatMessage`, `ApiResponse`

### CSS Guidelines

1. **Use CSS Modules** for component-specific styles
2. **CSS Variables** for theming and design tokens
3. **BEM-like naming** for class names
4. **Mobile-first** responsive design
5. **Avoid inline styles** except for dynamic values

```css
/* CSS Variables */
:root {
  --color-primary: #d97706;
  --spacing-md: 1rem;
}

/* Component styles */
.chatMessage {
  padding: var(--spacing-md);
}

.chatMessage--user {
  background: var(--color-primary);
}
```

### API Integration

1. **Error Handling**: Always handle API errors
2. **Loading States**: Show loading indicators
3. **Type Safety**: Define request/response types
4. **Authentication**: Include auth tokens in headers
5. **Retry Logic**: Implement retry for transient failures

```typescript
async function fetchNotes(): Promise<Note[]> {
  try {
    const response = await api.get<Note[]>('/notes');
    return response;
  } catch (error) {
    console.error('Failed to fetch notes:', error);
    throw error;
  }
}
```

---

## Development Workflow

### 1. Setup Development Environment

```bash
cd /home/user/brainda/app/web
npm install
npm run dev  # Start dev server on port 3000
```

### 2. Development Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/stage-X-component-name
   ```

2. **Implement Feature**
   - Write code
   - Add types
   - Handle errors
   - Add loading states

3. **Test Locally**
   - Visual testing
   - Interaction testing
   - Edge cases

4. **Type Check**
   ```bash
   npm run type-check
   ```

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: implement component name"
   ```

6. **Push and Create PR**
   ```bash
   git push origin feature/stage-X-component-name
   ```

### 3. Code Review Checklist

- [ ] TypeScript types defined
- [ ] Error handling implemented
- [ ] Loading states shown
- [ ] Responsive on mobile
- [ ] Accessible (ARIA labels, keyboard navigation)
- [ ] No console errors
- [ ] No "Brainda" references (should be "Brainda")

### 4. Testing Guidelines

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Type checking
npm run type-check
```

---

## Common Patterns

### 1. API Call Pattern

```typescript
function useResource<T>(endpoint: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<T>(endpoint)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [endpoint]);

  return { data, loading, error };
}
```

### 2. Form Handling Pattern

```typescript
function MyForm() {
  const [formData, setFormData] = useState({ title: '', body: '' });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post('/endpoint', formData);
      // Success handling
    } catch (error) {
      // Error handling
    } finally {
      setSubmitting(false);
    }
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

### 3. Modal Pattern

```typescript
function MyModal({ isOpen, onClose, children }: ModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
```

### 4. Protected Route Pattern

```typescript
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" />;

  return <>{children}</>;
}
```

---

## Environment Variables

Create `.env` file (copy from `.env.example`):

```env
# API Configuration
VITE_API_URL=http://localhost:8000
VITE_API_BASE_PATH=/api/v1

# Application
VITE_APP_NAME=Brainda
VITE_APP_VERSION=1.0.0

# Features
VITE_ENABLE_GOOGLE_CALENDAR=true
VITE_ENABLE_OPENMEMORY=true
```

Access in code:
```typescript
const API_URL = import.meta.env.VITE_API_URL;
```

---

## Build & Deployment

### Development Build
```bash
npm run dev
```

### Production Build
```bash
npm run build
# Output: dist/ folder
```

### Preview Production Build
```bash
npm run preview
```

### Docker Build

FastAPI will serve the built frontend from `dist/` folder. The build process is integrated into the main Docker build.

---

## Accessibility Requirements

1. **Keyboard Navigation**: All interactive elements accessible via keyboard
2. **Focus Indicators**: Visible focus rings (2px accent color)
3. **ARIA Labels**: All buttons, links, inputs have labels
4. **Semantic HTML**: Use proper heading hierarchy
5. **Color Contrast**: Minimum 4.5:1 for text
6. **Screen Reader**: Test with NVDA or VoiceOver
7. **Skip Links**: "Skip to main content"

---

## Performance Targets

- **Initial Load**: < 2 seconds
- **First Contentful Paint**: < 1.5 seconds
- **Time to Interactive**: < 3.5 seconds
- **Bundle Size**: < 200KB initial (gzipped)
- **Lighthouse Score**: > 90

---

## Browser Support

- Chrome/Edge: Last 2 versions
- Firefox: Last 2 versions
- Safari: Last 2 versions
- iOS Safari: Last 2 versions
- Android Chrome: Last 2 versions

---

## Stage Dependencies

```
Stage 1 (Foundation)
  └─> Stage 2 (Layout)
  └─> Stage 3 (API Layer)
        └─> Stage 4 (Chat) ⭐ PRIORITY
        └─> Stage 5 (Notes)
        └─> Stage 6 (Reminders)
        └─> Stage 7 (Documents)
        └─> Stage 8 (Calendar)
        └─> Stage 9 (Search)
        └─> Stage 10 (Auth)
        └─> Stage 11 (Settings)
              └─> Stage 12 (Polish)
              └─> Stage 13 (Mobile)
                    └─> Stage 14 (Testing)
                          └─> Stage 15 (Production)
```

**Parallelization Possible**:
- After Stage 1: Stages 2 and 3 can be parallel
- After Stages 1, 2, 3: Stages 4-11 can be parallel
- Stages 12 and 13 can be parallel
- Stages 14 and 15 must be sequential

---

## Getting Help

### Resources
- React Docs: https://react.dev
- TypeScript Docs: https://www.typescriptlang.org/docs
- Vite Docs: https://vitejs.dev
- React Router: https://reactrouter.com

### Common Issues

**Issue**: Build fails with TypeScript errors
**Solution**: Run `npm run type-check` and fix type errors

**Issue**: API calls fail with CORS
**Solution**: Check Vite proxy configuration in `vite.config.ts`

**Issue**: Components not updating
**Solution**: Check that state updates are immutable

---

## Notes for Developers

1. **Start with Stage 1** - Don't skip the foundation
2. **Test incrementally** - Don't wait until the end
3. **Keep components small** - Single responsibility
4. **Handle edge cases** - Empty states, errors, loading
5. **Think responsive** - Mobile-first design
6. **Commit often** - Small, focused commits
7. **Ask questions** - Better to clarify than guess
8. **Reference existing code** - Check existing components for patterns

---

**Version**: 1.0.0
**Last Updated**: 2025-01-14
**Maintained By**: Brainda Team
