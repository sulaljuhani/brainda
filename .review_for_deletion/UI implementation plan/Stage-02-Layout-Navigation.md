# Stage 2: Core Layout & Navigation

**Duration**: 2-3 days
**Priority**: HIGH
**Dependencies**: Stage 1 (Foundation) must be complete

---

## Goal

Build the main application shell with header, collapsible sidebar, routing, and responsive layout.

---

## Tasks

### Task 2.1: Create MainLayout Component

**File**: `src/layouts/MainLayout.tsx`

```typescript
import { ReactNode, useState } from 'react';
import { Header } from '@components/layout/Header';
import { Sidebar } from '@components/layout/Sidebar';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className={styles.layout}>
      <Header />
      <div className={styles.mainContainer}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <main className={styles.content}>
          {children}
        </main>
      </div>
    </div>
  );
}
```

**File**: `src/layouts/MainLayout.module.css`

```css
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.mainContainer {
  display: flex;
  flex: 1;
  overflow: hidden;
  margin-top: var(--header-height);
}

.content {
  flex: 1;
  overflow-y: auto;
  background: radial-gradient(
    circle at top left,
    rgba(234, 156, 62, 0.08),
    transparent 50%
  );
}
```

---

### Task 2.2: Build Header Component

**File**: `src/components/layout/Header.tsx`

```typescript
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './Header.module.css';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <div className={styles.logo} onClick={() => navigate('/')}>
          Brainda
        </div>

        <form className={styles.searchForm} onSubmit={handleSearch}>
          <div className={styles.searchBar}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search workspace..."
              className={styles.searchInput}
            />
          </div>
        </form>
      </div>

      <div className={styles.right}>
        <button className={styles.iconButton} aria-label="Notifications">
          🔔
          {/* Add badge if needed */}
        </button>

        <button className={styles.iconButton} aria-label="Settings">
          ⚙️
        </button>

        <div className={styles.avatar}>
          JD
        </div>
      </div>
    </header>
  );
}
```

**File**: `src/components/layout/Header.module.css`

```css
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: color-mix(in srgb, var(--bg-secondary) 85%, transparent);
  border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(20px);
  z-index: 100;
}

.left,
.right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.logo {
  font-family: var(--font-sans);
  font-weight: var(--font-semibold);
  font-size: var(--text-xl);
  letter-spacing: 0.12em;
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
}

.logo:hover {
  opacity: 0.8;
}

.searchForm {
  flex: 1;
  max-width: 400px;
}

.searchBar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: color-mix(in srgb, var(--bg-tertiary) 80%, transparent);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-3);
  transition: all 0.2s ease;
}

.searchBar:focus-within {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 1px var(--accent-primary);
  background: var(--bg-elevated);
}

.searchIcon {
  font-size: var(--text-sm);
  opacity: 0.6;
}

.searchInput {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
}

.searchInput::placeholder {
  color: var(--text-tertiary);
}

.iconButton {
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
  font-size: var(--text-base);
}

.iconButton:hover {
  color: var(--accent-primary);
  border-color: var(--accent-primary);
  transform: translateY(-1px);
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: linear-gradient(
    135deg,
    rgba(234, 156, 62, 0.4),
    rgba(217, 119, 6, 0.6)
  );
  color: var(--text-inverse);
  display: grid;
  place-items: center;
  font-weight: var(--font-semibold);
  letter-spacing: 0.04em;
  box-shadow: var(--shadow-md);
  cursor: pointer;
  user-select: none;
}
```

---

### Task 2.3: Build Collapsible Sidebar

**File**: `src/components/layout/Sidebar.tsx`

```typescript
import { useNavigate, useLocation } from 'react-router-dom';
import styles from './Sidebar.module.css';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: '💬', path: '/' },
  { id: 'notes', label: 'Notes', icon: '📝', path: '/notes' },
  { id: 'documents', label: 'Documents', icon: '📄', path: '/documents' },
  { id: 'reminders', label: 'Reminders', icon: '⏰', path: '/reminders' },
  { id: 'calendar', label: 'Calendar', icon: '📆', path: '/calendar' },
  { id: 'search', label: 'Search', icon: '🔎', path: '/search' },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
            onClick={() => navigate(item.path)}
            aria-label={item.label}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className={styles.divider} />

      {!collapsed && (
        <div className={styles.recentSection}>
          <div className={styles.sectionTitle}>Recent</div>
          <div className={styles.recentItem}>Project notes</div>
          <div className={styles.recentItem}>Meeting summary</div>
          <div className={styles.recentItem}>Ideas brainstorm</div>
        </div>
      )}

      <div className={styles.collapseSection}>
        <button className={styles.collapseButton} onClick={onToggle}>
          <span>{collapsed ? '➡️' : '⬅️'}</span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
```

**File**: `src/components/layout/Sidebar.module.css`

```css
.sidebar {
  width: var(--sidebar-width);
  background: color-mix(in srgb, var(--bg-primary) 85%, transparent);
  border-right: 1px solid var(--border-subtle);
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  transition: width 0.25s ease, padding 0.25s ease;
  overflow-x: hidden;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed);
  padding-left: var(--space-3);
  padding-right: var(--space-3);
  align-items: center;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.navItem {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: var(--text-sm);
  border: none;
  background: transparent;
  border-left: 2px solid transparent;
  width: 100%;
  text-align: left;
  font-family: var(--font-sans);
}

.navItem:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.navItem.active {
  color: var(--accent-primary);
  background: rgba(217, 119, 6, 0.14);
  border-left-color: var(--accent-primary);
}

.navIcon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: rgba(234, 156, 62, 0.12);
  display: grid;
  place-items: center;
  font-size: var(--text-sm);
  flex-shrink: 0;
}

.collapsed .navItem {
  justify-content: center;
  padding-left: var(--space-2);
  padding-right: var(--space-2);
}

.collapsed .navLabel {
  display: none;
}

.divider {
  height: 1px;
  background: var(--border-subtle);
}

.recentSection {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sectionTitle {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}

.recentItem {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: background 0.2s ease;
  font-size: var(--text-sm);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recentItem:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.collapseSection {
  margin-top: auto;
}

.collapseButton {
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
  font-family: var(--font-sans);
  font-size: var(--text-sm);
}

.collapseButton:hover {
  color: var(--accent-primary);
  border-color: var(--accent-primary);
  transform: translateY(-1px);
}

/* Mobile responsiveness */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: var(--header-height);
    bottom: 0;
    z-index: 90;
    transform: translateX(-100%);
  }

  .sidebar.collapsed {
    transform: translateX(0);
  }
}
```

---

### Task 2.4: Setup React Router

**File**: `src/App.tsx`

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';

// Page imports (we'll create placeholders for now)
import ChatPage from '@pages/ChatPage';
import NotesPage from '@pages/NotesPage';
import DocumentsPage from '@pages/DocumentsPage';
import RemindersPage from '@pages/RemindersPage';
import CalendarPage from '@pages/CalendarPage';
import SearchPage from '@pages/SearchPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Main routes with layout */}
        <Route path="/" element={<MainLayout><ChatPage /></MainLayout>} />
        <Route path="/chat" element={<Navigate to="/" replace />} />
        <Route path="/notes" element={<MainLayout><NotesPage /></MainLayout>} />
        <Route path="/documents" element={<MainLayout><DocumentsPage /></MainLayout>} />
        <Route path="/reminders" element={<MainLayout><RemindersPage /></MainLayout>} />
        <Route path="/calendar" element={<MainLayout><CalendarPage /></MainLayout>} />
        <Route path="/search" element={<MainLayout><SearchPage /></MainLayout>} />

        {/* 404 fallback */}
        <Route path="*" element={<div style={{ padding: '2rem' }}>Page not found</div>} />
      </Routes>
    </BrowserRouter>
  );
}
```

---

### Task 2.5: Create Placeholder Pages

**File**: `src/pages/ChatPage.tsx`

```typescript
export default function ChatPage() {
  return (
    <div style={{ padding: '2rem' }}>
      <h1>Chat Page</h1>
      <p>Main chat interface will be implemented in Stage 4</p>
    </div>
  );
}
```

**File**: `src/pages/NotesPage.tsx`

```typescript
export default function NotesPage() {
  return (
    <div style={{ padding: '2rem' }}>
      <h1>Notes Page</h1>
      <p>Notes management will be implemented in Stage 5</p>
    </div>
  );
}
```

Create similar placeholders for:
- `src/pages/DocumentsPage.tsx`
- `src/pages/RemindersPage.tsx`
- `src/pages/CalendarPage.tsx`
- `src/pages/SearchPage.tsx`

---

### Task 2.6: Add Sidebar Persistence

**File**: `src/hooks/useLocalStorage.ts`

```typescript
import { useState, useEffect } from 'react';

export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  };

  return [storedValue, setValue];
}
```

**Update**: `src/layouts/MainLayout.tsx`

```typescript
import { useLocalStorage } from '@hooks/useLocalStorage';

export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage('sidebar-collapsed', false);

  return (
    // ... rest of component
  );
}
```

---

## Testing & Verification

### Test 1: Navigation Works

- Click each sidebar item
- Verify URL changes
- Verify active state highlights correct item

### Test 2: Sidebar Collapse

- Click collapse button
- Verify sidebar width changes to 64px
- Verify only icons visible
- Click again, verify it expands
- Refresh page, verify state persists

### Test 3: Responsive Layout

- Resize browser window to < 1024px
- Verify sidebar hides
- Resize back, verify sidebar returns

### Test 4: Header Search

- Type in search bar
- Press Enter
- Verify navigation to `/search?q=...`

---

## Deliverables

- [x] MainLayout component
- [x] Header with logo, search, user menu
- [x] Collapsible sidebar (remembers state)
- [x] React Router setup
- [x] All page placeholders created
- [x] Active navigation highlighting
- [x] Mobile-responsive sidebar
- [x] LocalStorage persistence hook

---

## Next Stage

Proceed to:
- **Stage 3**: API Integration Layer

**Can Start After This Stage**:
- Stage 4: Chat Page (needs Stage 3)
- Stage 5: Notes (needs Stage 3)
- All other page stages (need Stage 3)
