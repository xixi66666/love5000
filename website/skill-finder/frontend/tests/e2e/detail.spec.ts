import { expect, test } from '@playwright/test'

import { mockApi } from './mock-api'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('shows repository detail with introduction', async ({ page }) => {
  await page.goto('/repositories/octocat/agent-hub')
  await expect(page.getByRole('heading', { name: 'octocat/agent-hub' })).toBeVisible()
  await expect(page.getByTestId('introduction')).toBeVisible()
  await expect(page.getByText('Composable agent framework')).toBeVisible()
  await expect(page.getByTestId('highlights')).toContainText('多工具调用')
  await expect(page.getByTestId('usage')).toContainText('npm install')
})

test('shows not found for unknown repo', async ({ page }) => {
  await page.goto('/repositories/unknown/missing')
  await expect(page.getByTestId('not-found')).toBeVisible()
})

test('shows empty trend state when no snapshots', async ({ page }) => {
  await page.goto('/repositories/octocat/agent-hub')
  await expect(page.getByText('Composable agent framework')).toBeVisible()
})
