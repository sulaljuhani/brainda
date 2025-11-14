# Testing Guide - Brainda Web UI

Complete testing guide for the Brainda web application.

---

## Table of Contents

- [Overview](#overview)
- [Setup](#setup)
- [Running Tests](#running-tests)
- [Unit Tests](#unit-tests)
- [E2E Tests](#e2e-tests)
- [Accessibility Tests](#accessibility-tests)
- [Writing Tests](#writing-tests)
- [Best Practices](#best-practices)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Brainda web UI uses a comprehensive testing approach:

- **Unit Tests**: Vitest + React Testing Library
- **E2E Tests**: Playwright
- **Accessibility**: axe-core integration
- **Coverage Target**: 80%+

---

## Setup

### Install Dependencies

```bash
cd app/web
npm install
```

### Install Playwright Browsers

```bash
npm run playwright:install
```

This installs Chromium, Firefox, and WebKit browsers for E2E testing.

---

## Running Tests

### Unit Tests

```bash
# Run all unit tests
npm test

# Run in watch mode
npm test -- --watch

# Run with UI
npm run test:ui

# Run with coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui

# Run specific test file
npm run test:e2e -- e2e/auth.spec.ts

# Run in specific browser
npm run test:e2e -- --project=chromium
npm run test:e2e -- --project=firefox
npm run test:e2e -- --project=webkit
```

### Accessibility Tests

```bash
# Run accessibility tests (included in E2E suite)
npm run test:e2e -- e2e/accessibility.spec.ts

# Run all tests with verbose accessibility reporting
npm run test:a11y
```

### All Tests

```bash
# Run unit tests and E2E tests
npm test && npm run test:e2e
```

---

## Unit Tests

### Location

- Test files: `src/**/*.test.{ts,tsx}`
- Test utilities: `src/test/utils.tsx`
- Setup: `src/test/setup.ts`

### Structure

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/utils';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});
```

### What We Test

- **Components**: Rendering, props, user interactions, edge cases
- **Hooks**: State changes, side effects, return values
- **Utils**: Pure functions, data transformations

### Coverage

Coverage is tracked automatically with Vitest. Reports are generated in:
- `coverage/` directory (HTML report)
- Console output

**Thresholds**:
- Lines: 80%
- Functions: 80%
- Branches: 80%
- Statements: 80%

---

## E2E Tests

### Location

- Test files: `e2e/**/*.spec.ts`
- Configuration: `playwright.config.ts`

### Structure

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should do something', async ({ page }) => {
    await page.click('button');
    await expect(page.getByText('Success')).toBeVisible();
  });
});
```

### Test Suites

1. **auth.spec.ts**: Authentication flows (login, register, logout)
2. **chat.spec.ts**: Chat interface and messaging
3. **notes.spec.ts**: Note creation, editing, deletion
4. **accessibility.spec.ts**: Accessibility compliance

### Browsers Tested

- **Desktop**: Chrome, Firefox, Safari (WebKit)
- **Mobile**: Chrome (Pixel 5), Safari (iPhone 12)

### Authentication in Tests

Most tests require authentication. Use this pattern:

```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('sessionToken', 'mock-token-12345');
  });
  await page.goto('/page-to-test');
});
```

---

## Accessibility Tests

### Tools

- **axe-core**: Automated accessibility testing
- **axe-playwright**: Playwright integration

### Running Accessibility Tests

```typescript
import { injectAxe, checkA11y } from 'axe-playwright';

test('page should be accessible', async ({ page }) => {
  await page.goto('/');
  await injectAxe(page);
  await checkA11y(page);
});
```

### What We Test

- **WCAG 2.1 Level AA** compliance
- Color contrast ratios
- Keyboard navigation
- Screen reader support
- ARIA attributes
- Semantic HTML
- Focus management

### Common Issues

1. **Missing alt text**: All images need `alt` attributes
2. **Poor color contrast**: Text should meet 4.5:1 ratio
3. **Missing labels**: All form inputs need labels
4. **Invalid ARIA**: Check ARIA roles and attributes
5. **Keyboard traps**: All interactive elements accessible via keyboard

---

## Writing Tests

### Unit Test Example

```typescript
// Button.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/utils';
import userEvent from '@testing-library/user-event';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click me');
  });

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(<Button onClick={onClick}>Click</Button>);
    await user.click(screen.getByRole('button'));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### E2E Test Example

```typescript
// feature.spec.ts
import { test, expect } from '@playwright/test';

test.describe('My Feature', () => {
  test('completes user flow', async ({ page }) => {
    // Navigate
    await page.goto('/feature');

    // Interact
    await page.getByLabel('Username').fill('testuser');
    await page.getByRole('button', { name: 'Submit' }).click();

    // Assert
    await expect(page.getByText('Success')).toBeVisible();
  });
});
```

### Hook Test Example

```typescript
// useCounter.test.ts
import { renderHook, act } from '@testing-library/react';
import { useCounter } from './useCounter';

describe('useCounter', () => {
  it('increments count', () => {
    const { result } = renderHook(() => useCounter());

    expect(result.current.count).toBe(0);

    act(() => {
      result.current.increment();
    });

    expect(result.current.count).toBe(1);
  });
});
```

---

## Best Practices

### General

1. **Write tests as you code**: Don't wait until the end
2. **Test behavior, not implementation**: Focus on user interactions
3. **Keep tests isolated**: Each test should be independent
4. **Use descriptive test names**: Clearly describe what's being tested
5. **Avoid test duplication**: Don't test the same thing multiple times

### Unit Tests

1. **Use Testing Library queries**: Prefer `getByRole`, `getByLabelText`
2. **Test user interactions**: Click, type, submit forms
3. **Mock external dependencies**: API calls, localStorage, etc.
4. **Test edge cases**: Empty states, errors, loading states
5. **Keep tests simple**: One assertion per test when possible

### E2E Tests

1. **Test critical paths**: Focus on main user journeys
2. **Use data-testid sparingly**: Prefer semantic queries
3. **Wait for elements**: Use `waitFor`, `toBeVisible()`
4. **Handle async operations**: Always await promises
5. **Test on multiple browsers**: At least Chrome and Firefox

### Accessibility

1. **Test with keyboard only**: Tab, Enter, Escape, Arrow keys
2. **Check color contrast**: Use browser dev tools
3. **Test with screen reader**: NVDA (Windows) or VoiceOver (Mac)
4. **Validate HTML**: Use W3C validator
5. **Run axe audits**: On every page

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Run unit tests
        run: npm test -- --coverage

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Run E2E tests
        run: npm run test:e2e

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hook

Add to `.husky/pre-commit`:

```bash
#!/bin/sh
npm test -- --run
```

---

## Troubleshooting

### Common Issues

#### Tests timeout

**Problem**: Tests hang or timeout

**Solutions**:
- Increase timeout in test
- Check for infinite loops
- Ensure API mocks are working
- Use `waitFor` for async operations

#### Mock not working

**Problem**: Mocked function not being called

**Solutions**:
- Verify mock is set up before render
- Check import path matches
- Clear mocks between tests: `vi.clearAllMocks()`

#### Playwright browser issues

**Problem**: Browsers fail to launch

**Solutions**:
```bash
# Reinstall browsers
npx playwright install --with-deps

# Check system dependencies
npx playwright install-deps
```

#### Flaky tests

**Problem**: Tests pass/fail inconsistently

**Solutions**:
- Add proper waits: `await expect(element).toBeVisible()`
- Avoid hard-coded delays: `waitForTimeout(1000)`
- Check for race conditions
- Ensure proper cleanup in `afterEach`

#### Accessibility violations

**Problem**: axe-core reports violations

**Solutions**:
- Read violation message carefully
- Use browser dev tools to inspect element
- Check WCAG guidelines
- Fix HTML/ARIA issues

### Getting Help

1. Check test output for error messages
2. Use `screen.debug()` to see rendered HTML
3. Add `await page.screenshot()` in E2E tests
4. Enable verbose logging: `DEBUG=pw:api npm run test:e2e`
5. Consult documentation:
   - [Vitest](https://vitest.dev)
   - [Testing Library](https://testing-library.com)
   - [Playwright](https://playwright.dev)
   - [axe-core](https://github.com/dequelabs/axe-core)

---

## Coverage Reports

### Viewing Coverage

After running `npm run test:coverage`:

```bash
# Open HTML report
open coverage/index.html
```

### Coverage Metrics

- **Lines**: Percentage of code lines executed
- **Functions**: Percentage of functions called
- **Branches**: Percentage of conditional branches tested
- **Statements**: Percentage of statements executed

### Improving Coverage

1. Identify uncovered lines in report
2. Add tests for missing scenarios
3. Test error handling paths
4. Test edge cases and boundary conditions
5. Don't aim for 100% - focus on critical paths

---

## Resources

- [Vitest Documentation](https://vitest.dev)
- [React Testing Library](https://testing-library.com/react)
- [Playwright Documentation](https://playwright.dev)
- [axe-core GitHub](https://github.com/dequelabs/axe-core)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

---

**Version**: 1.0.0
**Last Updated**: 2025-01-14
**Stage**: 14 - Testing & QA
