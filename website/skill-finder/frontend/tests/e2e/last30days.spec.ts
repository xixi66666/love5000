import { expect, test } from '@playwright/test'

import { mockApi } from './mock-api'

const RANKING_ITEM = {
  candidate_id: 'reddit-1',
  title: 'What developers are saying',
  source: 'reddit',
  url: 'https://www.reddit.com/r/example/1',
  published_at: '2026-08-20T00:00:00Z',
  summary: 'A grounded community summary.',
  engagement: { score: 210, comments: 42 },
  relevance_score: 0.95,
  cluster: 0,
}

function rankingPayload(direction: string, items: unknown[] = [RANKING_ITEM]) {
  return {
    direction,
    status: items.length ? 'working' : 'no-results',
    items,
    clusters: [],
    sources: ['reddit', 'hackernews', 'github'],
    source_status: { reddit: 'ok' },
    fetched_at: '2026-08-21T00:00:00Z',
    message: null,
  }
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
  await page.route('**/api/v1/last30days/status', async (route) => {
    await route.fulfill({
      json: {
        status: 'working',
        sources: ['reddit', 'hackernews', 'polymarket', 'github', 'grounding'],
      },
    })
  })
  await page.route('**/api/v1/last30days/rankings?*', async (route) => {
    const url = new URL(route.request().url())
    const direction = url.searchParams.get('direction') ?? 'agent'
    const items = direction === 'agent' ? [RANKING_ITEM] : []
    await route.fulfill({ json: rankingPayload(direction, items) })
  })
  await page.route('**/api/v1/last30days/rankings/refresh', async (route) => {
    const body = route.request().postDataJSON() as { direction?: string }
    await route.fulfill({ json: rankingPayload(body.direction ?? 'agent') })
  })
})

test('opens the top-20 ranking from the primary navigation', async ({ page }) => {
  await page.goto('/')

  const researchLink = page.getByRole('link', { name: '近 30 天最热' })
  await expect(researchLink).toBeVisible()
  await researchLink.click()

  await expect(page).toHaveURL(/\/last30days$/)
  await expect(page.getByRole('heading', { name: '近 30 天最热' })).toBeVisible()
  await expect(page.getByText('What developers are saying')).toBeVisible()
})

test('switches direction tabs and refreshes the ranking', async ({ page }) => {
  await page.goto('/last30days')

  await page.getByTestId('direction-skill').click()
  await expect(page.getByText('还没有榜单数据')).toBeVisible()

  await page.getByTestId('refresh-ranking').click()
  await expect(page.getByText('What developers are saying')).toBeVisible()
})
