# Test Utilities

This directory contains testing utilities and configuration for the Brainda web application.

## Files

- **setup.ts**: Global test setup, mocks, and configurations
- **utils.tsx**: Custom render functions and testing helpers

## Usage

### Custom Render

Use the custom `render` function from `utils.tsx` to automatically wrap components with necessary providers:

```typescript
import { render, screen } from '@/test/utils';
import { MyComponent } from './MyComponent';

test('renders component', () => {
  render(<MyComponent />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});
```

This automatically provides:
- BrowserRouter (for routing)
- AuthProvider (for authentication)
- ToastProvider (for notifications)

### Mock Data

```typescript
import { mockUser, mockApiResponse, mockApiError } from '@/test/utils';

// Mock successful API response
mockFetch({ data: 'test' });

// Mock API error
mockApiError('Network error');
```

### Resetting Mocks

```typescript
import { resetMocks } from '@/test/utils';

afterEach(() => {
  resetMocks();
});
```

## Best Practices

1. Always use the custom `render` from `@/test/utils`
2. Clean up mocks in `afterEach` hooks
3. Use `mockApiResponse` for API mocking
4. Import test utilities from `@testing-library/react` via `@/test/utils`

## Available Mocks

- `localStorage`
- `sessionStorage`
- `window.matchMedia`
- `IntersectionObserver`
- `ResizeObserver`
- `fetch`
