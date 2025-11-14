# Stage 1: Foundation & Build System Setup

**Duration**: 2-3 days
**Priority**: CRITICAL (must be completed first)
**Dependencies**: None

---

## Goal

Set up modern build tooling, project structure, and development environment for long-term maintainability.

---

## Prerequisites

- Node.js 18+ installed
- npm 9+ installed
- Access to `/home/user/brainda/app/web` directory
- FastAPI backend running

---

## Tasks

### Task 1.1: Initialize Vite Project

**Install Core Dependencies**

```bash
cd /home/user/brainda/app/web

# Core build tools
npm install -D vite @vitejs/plugin-react typescript

# React dependencies
npm install react@18 react-dom@18 react-router-dom@6

# TypeScript types
npm install -D @types/react @types/react-dom @types/node
```

**Expected Output**: `node_modules/` folder created with all dependencies

---

### Task 1.2: Create Vite Configuration

**File**: `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@services': path.resolve(__dirname, './src/services'),
      '@types': path.resolve(__dirname, './src/types'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },

  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
});
```

---

### Task 1.3: Configure TypeScript

**File**: `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,

    /* Path aliases */
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@pages/*": ["./src/pages/*"],
      "@hooks/*": ["./src/hooks/*"],
      "@services/*": ["./src/services/*"],
      "@types/*": ["./src/types/*"],
      "@utils/*": ["./src/utils/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**File**: `tsconfig.node.json`

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

---

### Task 1.4: Update package.json

**File**: `package.json`

Update the scripts section:

```json
{
  "name": "brainda-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "type-check": "tsc --noEmit",
    "lint": "eslint src --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
  }
}
```

---

### Task 1.5: Create Project Directory Structure

**Create directories**:

```bash
cd /home/user/brainda/app/web

# Create src directory structure
mkdir -p src/{components,pages,hooks,services,contexts,types,utils,styles}
mkdir -p src/components/{auth,chat,notes,reminders,documents,calendar,search,settings,shared,layout}

# Create public directory for static assets
mkdir -p public
```

**Expected structure**:
```
app/web/
├── src/
│   ├── components/
│   │   ├── auth/
│   │   ├── chat/
│   │   ├── notes/
│   │   ├── reminders/
│   │   ├── documents/
│   │   ├── calendar/
│   │   ├── search/
│   │   ├── settings/
│   │   ├── shared/
│   │   └── layout/
│   ├── pages/
│   ├── hooks/
│   ├── services/
│   ├── contexts/
│   ├── types/
│   ├── utils/
│   └── styles/
├── public/
├── vite.config.ts
├── tsconfig.json
└── package.json
```

---

### Task 1.6: Create Entry HTML

**File**: `index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="Brainda - Personal Knowledge Management System" />
    <link rel="icon" type="image/x-icon" href="/favicon.ico" />
    <title>Brainda</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

---

### Task 1.7: Create App Entry Point

**File**: `src/main.tsx`

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**File**: `src/App.tsx` (temporary placeholder)

```typescript
import { BrowserRouter } from 'react-router-dom';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ padding: '2rem', fontFamily: 'system-ui' }}>
        <h1>Brainda</h1>
        <p>Build system is working! 🎉</p>
        <p>Ready for Stage 2: Layout & Navigation</p>
      </div>
    </BrowserRouter>
  );
}
```

---

### Task 1.8: Create Global Styles

**File**: `src/styles/global.css`

```css
/* CSS Reset */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* CSS Variables (Design Tokens) */
:root {
  /* Colors - Dark Mode */
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

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.6);

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
               Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;

  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem;

  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;

  /* Spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;

  /* Layout */
  --header-height: 56px;
  --sidebar-width: 280px;
  --sidebar-collapsed: 64px;
  --max-chat-width: 768px;

  /* Border Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-2xl: 1.5rem;
  --radius-full: 9999px;
}

/* Base Styles */
html, body {
  height: 100%;
}

body {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--text-primary);
  background: var(--bg-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#root {
  min-height: 100vh;
}

/* Accessibility */
:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

/* Scrollbar Styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}
```

---

### Task 1.9: Rename All "VIB" References

**Search and replace** in existing files:
- `app/web/components/*.tsx`: Change "VIB" → "Brainda"
- `app/web/public/index.html`: Update title and references

**Files to update**:
1. `components/VibInterface.tsx` → Update logo text
2. `public/index.html` → Update title (if not replaced)

**Command to find all references**:
```bash
cd /home/user/brainda/app/web
grep -r "VIB" --include="*.tsx" --include="*.ts" --include="*.html"
```

---

### Task 1.10: Update FastAPI to Serve Built Frontend

**File**: `/home/user/brainda/app/api/main.py`

Update the static file serving section:

```python
# Replace existing static file mounting code
WEB_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "dist")

if os.path.exists(WEB_DIST_DIR):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIST_DIR, "assets")), name="assets")

# Catch-all route for SPA (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve React SPA for all non-API routes"""
    # Don't intercept API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # Serve index.html for all other routes (SPA routing)
    index_path = os.path.join(WEB_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    # Fallback if build doesn't exist
    return {
        "message": "Brainda API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "Frontend not built. Run 'cd app/web && npm run build'"
    }
```

---

### Task 1.11: Create Environment Variables Template

**File**: `.env.example`

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

# Development
VITE_DEV_MODE=true
```

**File**: `.env` (create from example)

```bash
cp .env.example .env
```

Add to `.gitignore`:
```
.env
.env.local
```

---

## Testing & Verification

### Test 1: Build System Works

```bash
cd /home/user/brainda/app/web
npm run dev
```

**Expected**:
- Dev server starts on http://localhost:3000
- Browser shows "Brainda - Build system is working! 🎉"
- No console errors

### Test 2: TypeScript Type Checking

```bash
npm run type-check
```

**Expected**: No type errors

### Test 3: Production Build

```bash
npm run build
```

**Expected**:
- Build completes successfully
- `dist/` folder created
- Contains `index.html`, `assets/` folder

### Test 4: API Proxy Works

With dev server running:
```bash
curl http://localhost:3000/api/v1/health
```

**Expected**: Returns health check JSON from FastAPI

---

## Deliverables

- [x] Vite configured and working
- [x] TypeScript setup with strict mode
- [x] Project structure created
- [x] Global styles with design tokens
- [x] Entry point (`main.tsx`, `App.tsx`)
- [x] Development server running
- [x] Production build working
- [x] FastAPI serving built frontend
- [x] All "VIB" renamed to "Brainda"
- [x] Environment variables configured

---

## Common Issues & Solutions

**Issue**: `npm install` fails
**Solution**: Clear npm cache `npm cache clean --force` and retry

**Issue**: Vite dev server won't start
**Solution**: Check if port 3000 is already in use. Change port in `vite.config.ts`

**Issue**: TypeScript errors about path aliases
**Solution**: Verify `tsconfig.json` and `vite.config.ts` have matching path configurations

**Issue**: API proxy not working
**Solution**: Ensure FastAPI is running on port 8000

---

## Next Stage

Once this stage is complete, proceed to:
- **Stage 2**: Core Layout & Navigation

**Can Start in Parallel**:
- Stage 3: API Integration Layer (after this stage)
