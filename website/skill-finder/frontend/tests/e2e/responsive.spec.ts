import { expect, test } from '@playwright/test'

import { assertNoHorizontalScroll, mockApi } from './mock-api'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('mobile home page has no horizontal scroll', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('octocat/agent-hub')).toBeVisible()
  await assertNoHorizontalScroll(page)
})

test('mobile detail page has no horizontal scroll', async ({ page }) => {
  await page.goto('/repositories/octocat/agent-hub')
  await expect(page.getByRole('heading', { name: 'octocat/agent-hub' })).toBeVisible()
  await assertNoHorizontalScroll(page)
})

test('mobile buttons do not truncate text', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('octocat/agent-hub')).toBeVisible()
  const overflowed = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'))
    return buttons.filter((b) => b.scrollWidth > b.clientWidth).length
  })
  expect(overflowed).toBe(0)
})

test('mobile introduction content does not overflow', async ({ page }) => {
  await page.goto('/repositories/octocat/agent-hub')
  await expect(page.getByTestId('introduction')).toBeVisible()
  const card = page.getByTestId('introduction')
  const box = await card.boundingBox()
  expect(box).not.toBeNull()
  await assertNoHorizontalScroll(page)
})

test('keyboard can open filters and navigate', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('octocat/agent-hub')).toBeVisible()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Enter')
})
