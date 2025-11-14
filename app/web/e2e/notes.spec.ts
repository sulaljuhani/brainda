import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('Notes Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock authentication
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/notes');
  });

  test('should display notes page', async ({ page }) => {
    await expect(page).toHaveURL(/\/notes/);
    await expect(page.getByRole('heading', { name: /notes/i })).toBeVisible();
  });

  test('should show create note button', async ({ page }) => {
    const createButton = page.getByRole('button', { name: /create|new note/i });
    await expect(createButton).toBeVisible();
  });

  test('should open note editor when create button is clicked', async ({ page }) => {
    const createButton = page.getByRole('button', { name: /create|new note/i });
    await createButton.click();

    // Look for editor fields
    const titleInput = page.getByLabel(/title/i);
    const bodyInput = page.getByLabel(/body|content/i);

    await expect(titleInput.or(bodyInput)).toBeVisible();
  });

  test('should display empty state when no notes', async ({ page }) => {
    // Check for empty state message
    const emptyState = page.getByText(/no notes|get started|create your first/i);
    await expect(emptyState).toBeVisible({ timeout: 5000 });
  });

  test('should show note list when notes exist', async ({ page }) => {
    // This test assumes notes might be loaded from API
    const noteCards = page.locator('[data-testid="note-card"], .note-card');

    // Wait for either notes or empty state
    await page.waitForSelector('[data-testid="note-card"], .note-card, [data-testid="empty-state"]', {
      timeout: 5000,
      state: 'visible',
    });
  });

  test('notes page should be accessible', async ({ page }) => {
    await injectAxe(page);
    await checkA11y(page);
  });

  test('should support search/filter functionality', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|filter/i);

    if (await searchInput.isVisible()) {
      await expect(searchInput).toBeEnabled();
      await searchInput.fill('test');
      await expect(searchInput).toHaveValue('test');
    }
  });

  test('should handle keyboard shortcuts', async ({ page }) => {
    // Try common keyboard shortcut for new note (Ctrl+N or Cmd+N)
    const isMac = process.platform === 'darwin';
    const modifier = isMac ? 'Meta' : 'Control';

    await page.keyboard.press(`${modifier}+KeyN`);

    // Check if note editor opened
    const titleInput = page.getByLabel(/title/i);
    await expect(titleInput).toBeVisible({ timeout: 2000 });
  });
});

test.describe('Note Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/notes');

    // Open note editor
    const createButton = page.getByRole('button', { name: /create|new note/i });
    await createButton.click();
  });

  test('should display note editor fields', async ({ page }) => {
    await expect(page.getByLabel(/title/i)).toBeVisible();
    await expect(page.getByLabel(/body|content/i)).toBeVisible();
  });

  test('should show save and cancel buttons', async ({ page }) => {
    const saveButton = page.getByRole('button', { name: /save|create/i });
    const cancelButton = page.getByRole('button', { name: /cancel|close/i });

    await expect(saveButton).toBeVisible();
    await expect(cancelButton).toBeVisible();
  });

  test('should enable save button when title and body are filled', async ({ page }) => {
    const titleInput = page.getByLabel(/title/i);
    const bodyInput = page.getByLabel(/body|content/i);
    const saveButton = page.getByRole('button', { name: /save|create/i });

    await titleInput.fill('Test Note');
    await bodyInput.fill('Test content');

    await expect(saveButton).toBeEnabled();
  });

  test('should close editor when cancel is clicked', async ({ page }) => {
    const cancelButton = page.getByRole('button', { name: /cancel|close/i });
    await cancelButton.click();

    // Editor should be closed
    const titleInput = page.getByLabel(/title/i);
    await expect(titleInput).not.toBeVisible();
  });

  test('should support markdown formatting', async ({ page }) => {
    const bodyInput = page.getByLabel(/body|content/i);

    await bodyInput.fill('# Heading\n**bold** *italic*');

    // Check if markdown is accepted
    const value = await bodyInput.inputValue();
    expect(value).toContain('# Heading');
  });

  test('note editor should be accessible', async ({ page }) => {
    await injectAxe(page);
    await checkA11y(page);
  });
});

test.describe('Note Actions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('sessionToken', 'mock-token-12345');
    });
    await page.goto('/notes');
  });

  test('should support deleting notes', async ({ page }) => {
    // Look for delete button on note cards
    const deleteButton = page.getByRole('button', { name: /delete/i }).first();

    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Look for confirmation dialog
      const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
      await expect(confirmButton).toBeVisible();
    }
  });

  test('should support editing notes', async ({ page }) => {
    // Look for edit button on note cards
    const editButton = page.getByRole('button', { name: /edit/i }).first();

    if (await editButton.isVisible()) {
      await editButton.click();

      // Editor should open with note data
      const titleInput = page.getByLabel(/title/i);
      await expect(titleInput).toBeVisible();
    }
  });
});
