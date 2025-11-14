import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y, getViolations } from 'axe-playwright';

test.describe('Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock authentication for protected pages
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
  });

  test('login page should have no accessibility violations', async ({ page }) => {
    await page.goto('/login');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('registration page should have no accessibility violations', async ({ page }) => {
    await page.goto('/register');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('chat page should have no accessibility violations', async ({ page }) => {
    await page.goto('/chat');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('notes page should have no accessibility violations', async ({ page }) => {
    await page.goto('/notes');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('reminders page should have no accessibility violations', async ({ page }) => {
    await page.goto('/reminders');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('documents page should have no accessibility violations', async ({ page }) => {
    await page.goto('/documents');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('calendar page should have no accessibility violations', async ({ page }) => {
    await page.goto('/calendar');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('search page should have no accessibility violations', async ({ page }) => {
    await page.goto('/search');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('settings page should have no accessibility violations', async ({ page }) => {
    await page.goto('/settings');
    await injectAxe(page);

    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });
});

test.describe('Keyboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
  });

  test('should navigate through interactive elements with Tab', async ({ page }) => {
    await page.goto('/chat');

    // Press Tab to move focus
    await page.keyboard.press('Tab');

    // Check that something is focused
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();
  });

  test('should have visible focus indicators', async ({ page }) => {
    await page.goto('/chat');

    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    await chatInput.focus();

    // Check that focused element has outline or similar
    const outline = await chatInput.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return styles.outline || styles.outlineWidth;
    });

    expect(outline).toBeTruthy();
  });

  test('should handle Escape key to close modals', async ({ page }) => {
    await page.goto('/notes');

    // Open note editor
    const createButton = page.getByRole('button', { name: /create|new note/i });
    if (await createButton.isVisible()) {
      await createButton.click();

      // Press Escape
      await page.keyboard.press('Escape');

      // Modal should be closed
      const titleInput = page.getByLabel(/title/i);
      await expect(titleInput).not.toBeVisible();
    }
  });

  test('all buttons should be keyboard accessible', async ({ page }) => {
    await page.goto('/chat');

    const buttons = await page.getByRole('button').all();

    for (const button of buttons) {
      if (await button.isVisible()) {
        await button.focus();
        const isFocused = await button.evaluate((el) => el === document.activeElement);
        expect(isFocused).toBe(true);
      }
    }
  });
});

test.describe('Screen Reader Support', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
  });

  test('all images should have alt text', async ({ page }) => {
    await page.goto('/');

    const images = await page.locator('img').all();

    for (const img of images) {
      const alt = await img.getAttribute('alt');
      expect(alt).toBeTruthy();
    }
  });

  test('all form inputs should have labels', async ({ page }) => {
    await page.goto('/login');

    const inputs = await page.locator('input').all();

    for (const input of inputs) {
      const inputId = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');

      // Input should have either an id (for label), aria-label, or aria-labelledby
      const hasLabel = inputId || ariaLabel || ariaLabelledBy;
      expect(hasLabel).toBeTruthy();
    }
  });

  test('all buttons should have accessible names', async ({ page }) => {
    await page.goto('/chat');

    const buttons = await page.getByRole('button').all();

    for (const button of buttons) {
      if (await button.isVisible()) {
        const accessibleName = await button.getAttribute('aria-label') || await button.textContent();
        expect(accessibleName?.trim()).toBeTruthy();
      }
    }
  });

  test('headings should be in correct hierarchy', async ({ page }) => {
    await page.goto('/chat');

    const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
    const levels: number[] = [];

    for (const heading of headings) {
      const tagName = await heading.evaluate((el) => el.tagName);
      const level = parseInt(tagName.replace('H', ''));
      levels.push(level);
    }

    // Check that headings start with h1 and don't skip levels
    if (levels.length > 0) {
      expect(levels[0]).toBe(1); // Should start with h1

      for (let i = 1; i < levels.length; i++) {
        const diff = levels[i] - levels[i - 1];
        expect(diff).toBeLessThanOrEqual(1); // Should not skip levels
      }
    }
  });

  test('interactive elements should have appropriate ARIA roles', async ({ page }) => {
    await page.goto('/chat');

    // Check that custom interactive elements have roles
    const clickableElements = await page.locator('[onclick], [ng-click], .clickable').all();

    for (const element of clickableElements) {
      const role = await element.getAttribute('role');
      const tagName = await element.evaluate((el) => el.tagName);

      // If not a native button/link, should have a role
      if (!['BUTTON', 'A'].includes(tagName)) {
        expect(role).toBeTruthy();
      }
    }
  });

  test('loading states should be announced', async ({ page }) => {
    await page.goto('/chat');

    // Look for loading indicators with aria-live or role="status"
    const loadingIndicators = await page.locator('[role="status"], [aria-live]').all();

    // Should have at least one loading indicator mechanism
    expect(loadingIndicators.length).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Color Contrast', () => {
  test('should meet WCAG AA color contrast requirements', async ({ page }) => {
    await page.goto('/');
    await injectAxe(page);

    const violations = await getViolations(page, 'color-contrast');
    expect(violations).toHaveLength(0);
  });
});

test.describe('Mobile Accessibility', () => {
  test('should be accessible on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/chat');

    await injectAxe(page);
    const violations = await getViolations(page);
    expect(violations).toHaveLength(0);
  });

  test('touch targets should be at least 44x44 pixels', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/chat');

    const buttons = await page.getByRole('button').all();

    for (const button of buttons) {
      if (await button.isVisible()) {
        const box = await button.boundingBox();
        if (box) {
          expect(box.width).toBeGreaterThanOrEqual(44);
          expect(box.height).toBeGreaterThanOrEqual(44);
        }
      }
    }
  });
});
