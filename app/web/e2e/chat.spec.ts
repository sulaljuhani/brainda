import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock authentication
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/chat');
  });

  test('should display chat interface', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /chat|brainda/i })).toBeVisible();
  });

  test('should show chat input field', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    await expect(chatInput).toBeVisible();
    await expect(chatInput).toBeEnabled();
  });

  test('should show send button', async ({ page }) => {
    const sendButton = page.getByRole('button', { name: /send/i });
    await expect(sendButton).toBeVisible();
  });

  test('send button should be disabled with empty input', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    const sendButton = page.getByRole('button', { name: /send/i });

    await expect(chatInput).toHaveValue('');
    await expect(sendButton).toBeDisabled();
  });

  test('send button should be enabled with text input', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    const sendButton = page.getByRole('button', { name: /send/i });

    await chatInput.fill('Hello, Brainda!');
    await expect(sendButton).toBeEnabled();
  });

  test('should handle Enter key to send message', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);

    await chatInput.fill('Test message');
    await chatInput.press('Enter');

    // Input should be cleared after sending
    await expect(chatInput).toHaveValue('');
  });

  test('should display message history', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    const sendButton = page.getByRole('button', { name: /send/i });

    await chatInput.fill('First message');
    await sendButton.click();

    // Wait for message to appear
    await expect(page.getByText('First message')).toBeVisible({ timeout: 5000 });
  });

  test('should show typing indicator while waiting for response', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    const sendButton = page.getByRole('button', { name: /send/i });

    await chatInput.fill('Test message');
    await sendButton.click();

    // Look for typing indicator (dots, loading, etc.)
    const typingIndicator = page.locator('[data-testid="typing-indicator"], .typing-indicator');
    await expect(typingIndicator).toBeVisible({ timeout: 2000 });
  });

  test('chat page should be accessible', async ({ page }) => {
    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: true },
    });
  });

  test('should support keyboard navigation', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);

    await page.keyboard.press('Tab');
    await expect(chatInput).toBeFocused();
  });

  test('should clear input after sending message', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);
    const sendButton = page.getByRole('button', { name: /send/i });

    await chatInput.fill('Message to send');
    await sendButton.click();

    await expect(chatInput).toHaveValue('');
  });

  test('should scroll to bottom when new message arrives', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);

    // Send multiple messages to create scroll
    for (let i = 1; i <= 5; i++) {
      await chatInput.fill(`Message ${i}`);
      await chatInput.press('Enter');
      await page.waitForTimeout(500);
    }

    // Check if last message is visible (scrolled to bottom)
    const lastMessage = page.getByText('Message 5');
    await expect(lastMessage).toBeVisible();
  });
});

test.describe('Chat Features', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/chat');
  });

  test('should show sidebar toggle on mobile', async ({ page, viewport }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    const hamburgerMenu = page.getByRole('button', { name: /menu|toggle sidebar/i });
    await expect(hamburgerMenu).toBeVisible();
  });

  test('should handle multiline input with Shift+Enter', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/ask|message|type/i);

    await chatInput.fill('Line 1');
    await chatInput.press('Shift+Enter');
    await chatInput.type('Line 2');

    // Input should contain both lines
    const inputValue = await chatInput.inputValue();
    expect(inputValue).toContain('Line 1');
    expect(inputValue).toContain('Line 2');
  });
});
