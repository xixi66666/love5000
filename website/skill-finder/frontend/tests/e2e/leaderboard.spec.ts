import { expect, test, type Page } from '@playwright/test'

import { assertNoHorizontalScroll, mockApi } from './mock-api'

async function ensureSidebar(page: Page): Promise<void> {
  const openButton = page.getByTestId('open-filters')
  if (await openButton.isVisible()) {
    await openButton.click()
  }
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
})

test('shows default daily growth ranking', async ({ page }) => {
  await expect(page.getByText('octocat/agent-hub')).toBeVisible()
  await expect(page.getByText('+20').first()).toBeVisible()
})

test('switches to 7-day ranking', async ({ page }) => {
  await page.getByTestId('sort-weekly_stars').click()
  await expect(page.getByTestId('sort-weekly_stars')).toHaveAttribute('aria-selected', 'true')
})

test('switches to 30-day ranking', async ({ page }) => {
  await page.getByTestId('sort-monthly_stars').click()
  await expect(page.getByTestId('sort-monthly_stars')).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('+400').first()).toBeVisible()
})

test('filters by plugin category', async ({ page }) => {
  await ensureSidebar(page)
  await page.getByTestId('category-plugin').click()
  await expect(page.getByText('ada/claude-plugin-kit')).toBeVisible()
  await expect(page.getByText('octocat/agent-hub')).toHaveCount(0)
})

test('filters by category and language', async ({ page }) => {
  await ensureSidebar(page)
  await page.getByTestId('category-mcp').click()
  await expect(page.getByText('mcp-server-kit')).toBeVisible()
  await expect(page.getByText('octocat/agent-hub')).toHaveCount(0)

  await page.getByTestId('category-all').click()
  await page.getByTestId('language-select').selectOption('Python')
  await expect(page.getByText('octocat/agent-hub')).toBeVisible()
  await expect(page.getByText('mcp-server-kit')).toHaveCount(0)
})

test('searches with debounce', async ({ page }) => {
  await page.getByTestId('global-search').fill('skill')
  await page.waitForTimeout(500)
  await expect(page.getByText('skill-collection')).toBeVisible()
  await expect(page.getByText('octocat/agent-hub')).toHaveCount(0)
})

test('opens detail and restores filters on back', async ({ page }) => {
  await ensureSidebar(page)
  await page.getByTestId('category-agent').click()
  const closeButton = page.getByTestId('close-filters')
  if (await closeButton.isVisible()) {
    await closeButton.click()
  }
  await expect(page.getByTestId('repo-link-agent-hub')).toBeVisible()
  await page.getByTestId('repo-link-agent-hub').click()
  await expect(page.getByRole('heading', { name: 'octocat/agent-hub' })).toBeVisible()
  await page.getByTestId('back').click()
  await expect(page.getByTestId('category-agent')).toHaveAttribute('aria-pressed', 'true')
})

test('toggles theme', async ({ page }) => {
  const html = page.locator('html')
  const before = await html.getAttribute('data-theme')
  await page.getByTestId('theme-toggle').click()
  const after = await html.getAttribute('data-theme')
  expect(after).not.toBe(before)
})

test('external links have noopener noreferrer', async ({ page }) => {
  const link = page.locator('a[target="_blank"]').first()
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
})

test('desktop layout has no horizontal scroll', async ({ page }) => {
  await assertNoHorizontalScroll(page)
})
