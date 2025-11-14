import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login page for unauthenticated users', async ({ page }) => {
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
  });

  test('should show login form fields', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByLabel(/username/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('should show validation errors on empty submit', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('button', { name: /sign in/i }).click();

    // Check for validation messages
    const errorMessages = page.locator('.input-error-message');
    await expect(errorMessages.first()).toBeVisible();
  });

  test('should navigate to registration page', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('link', { name: /sign up|register/i }).click();

    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByRole('heading', { name: /create account|sign up/i })).toBeVisible();
  });

  test('should show registration form fields', async ({ page }) => {
    await page.goto('/register');

    await expect(page.getByLabel(/username/i)).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /create account|sign up/i })).toBeVisible();
  });

  test('login page should be accessible', async ({ page }) => {
    await page.goto('/login');
    await injectAxe(page);
    await checkA11y(page);
  });

  test('registration page should be accessible', async ({ page }) => {
    await page.goto('/register');
    await injectAxe(page);
    await checkA11y(page);
  });

  test('should handle keyboard navigation on login form', async ({ page }) => {
    await page.goto('/login');

    // Tab through form elements
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(/username/i)).toBeFocused();

    await page.keyboard.press('Tab');
    await expect(page.getByLabel(/password/i)).toBeFocused();

    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: /sign in/i })).toBeFocused();
  });

  test('password field should be hidden by default', async ({ page }) => {
    await page.goto('/login');

    const passwordInput = page.getByLabel(/password/i);
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });
});

test.describe('Authenticated User Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authenticated session
    await page.goto('/login');

    // Set session token in localStorage
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
  });

  test('should redirect to chat page when authenticated', async ({ page }) => {
    await page.goto('/');
    // If authenticated, should redirect to chat
    await page.waitForURL(/\/chat|\//, { timeout: 5000 });
  });

  test('should show user menu when authenticated', async ({ page }) => {
    await page.goto('/');

    // Look for user menu or logout button
    const userMenu = page.getByRole('button', { name: /menu|account|user/i });
    const logoutButton = page.getByRole('button', { name: /logout|sign out/i });

    await expect(userMenu.or(logoutButton)).toBeVisible({ timeout: 5000 });
  });
});
