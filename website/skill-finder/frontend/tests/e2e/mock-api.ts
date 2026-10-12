import type { Page } from '@playwright/test'

export const MOCK_REPOS = [
  {
    id: 1,
    owner: 'octocat',
    name: 'agent-hub',
    description: 'Composable agent framework',
    html_url: 'https://github.com/octocat/agent-hub',
    language: 'Python',
    topics: ['ai-agent', 'agentic', 'llm', 'tools'],
    categories: ['AGENT'],
    stars_count: 1500,
    daily_stars: 20,
    weekly_stars: 100,
    monthly_stars: 400,
    last_synced_at: '2026-08-10T00:00:00Z',
    trend: [
      { snapshot_date: '2026-07-20', stars_count: 1300 },
      { snapshot_date: '2026-08-01', stars_count: 1420 },
      { snapshot_date: '2026-08-10', stars_count: 1500 },
    ],
  },
  {
    id: 2,
    owner: 'smith',
    name: 'mcp-server-kit',
    description: 'Build mcp server quickly',
    html_url: 'https://github.com/smith/mcp-server-kit',
    language: 'TypeScript',
    topics: ['mcp-server', 'model-context-protocol'],
    categories: ['MCP'],
    stars_count: 900,
    daily_stars: 15,
    weekly_stars: 60,
    monthly_stars: 250,
    last_synced_at: '2026-08-10T00:00:00Z',
    trend: [
      { snapshot_date: '2026-07-20', stars_count: 820 },
      { snapshot_date: '2026-08-10', stars_count: 900 },
    ],
  },
  {
    id: 3,
    owner: 'lee',
    name: 'skill-collection',
    description: 'A curated list of agent skills',
    html_url: 'https://github.com/lee/skill-collection',
    language: 'Python',
    topics: ['agent-skills', 'claude-skills'],
    categories: ['SKILL'],
    stars_count: 700,
    daily_stars: null,
    weekly_stars: null,
    monthly_stars: null,
    last_synced_at: '2026-08-10T00:00:00Z',
    trend: [],
  },
  {
    id: 4,
    owner: 'ada',
    name: 'claude-plugin-kit',
    description: 'Claude plugin starter kit',
    html_url: 'https://github.com/ada/claude-plugin-kit',
    language: 'TypeScript',
    topics: ['claude-plugin', 'plugins'],
    categories: ['PLUGIN'],
    stars_count: 500,
    daily_stars: 12,
    weekly_stars: 45,
    monthly_stars: 180,
    last_synced_at: '2026-08-10T00:00:00Z',
    trend: [],
  },
]

const MOCK_DETAIL = {
  id: 1,
  owner: 'octocat',
  name: 'agent-hub',
  description: 'Composable agent framework',
  introduction: {
    introduction: '一个可组合的 AI Agent 框架，支持多工具调用与记忆管理。',
    highlights: ['多工具调用', '记忆管理', '可组合'],
    requirements: ['Node.js 18+'],
    usage: '直接运行 npm install 后即可集成到现有项目。',
    audience: '适合需要构建 Agent 应用的开发者。',
    domains: ['AI Agent', '自动化', '工具调用'],
  },
  html_url: 'https://github.com/octocat/agent-hub',
  homepage: 'https://example.com',
  language: 'Python',
  topics: ['ai-agent', 'agentic', 'llm', 'tools'],
  categories: ['AGENT'],
  matched_rules: ['topic:ai-agent', 'name:agent framework'],
  stars_count: 1500,
  forks_count: 80,
  open_issues_count: 4,
  daily_stars: 20,
  weekly_stars: 100,
  monthly_stars: 400,
  last_synced_at: '2026-08-10T00:00:00Z',
  github_created_at: '2026-01-01T00:00:00Z',
  trend: [
    { snapshot_date: '2026-07-12', stars_count: 1100 },
    { snapshot_date: '2026-07-20', stars_count: 1300 },
    { snapshot_date: '2026-08-01', stars_count: 1420 },
    { snapshot_date: '2026-08-10', stars_count: 1500 },
  ],
}

export async function mockApi(page: Page): Promise<void> {
  await page.route('**/api/v1/repositories?*', async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams.get('q')
    const category = url.searchParams.get('category')
    const language = url.searchParams.get('language')
    let items = [...MOCK_REPOS]
    if (category) items = items.filter((repo) => repo.categories.includes(category as never))
    if (language) items = items.filter((repo) => repo.language === language)
    if (q) items = items.filter((repo) => repo.name.includes(q) || repo.owner.includes(q))
    await route.fulfill({
      json: {
        items,
        page: 1,
        page_size: 20,
        total: items.length,
        last_successful_collection_at: '2026-08-10T00:00:00Z',
      },
    })
  })

  await page.route('**/api/v1/repositories/**', async (route) => {
    const path = route.request().url().split('/api/v1/repositories/')[1]
    if (path === 'octocat/agent-hub') {
      await route.fulfill({ json: MOCK_DETAIL })
    } else {
      await route.fulfill({
        status: 404,
        json: { code: 'REPOSITORY_NOT_FOUND', message: 'Repository not found', request_id: 'mock' },
      })
    }
  })

  await page.route('**/api/v1/languages', async (route) => {
    await route.fulfill({
      json: [
        { language: 'Python', count: 2 },
        { language: 'TypeScript', count: 2 },
      ],
    })
  })

  await page.route('**/api/v1/stats', async (route) => {
    await route.fulfill({
      json: {
        total_repositories: 4,
        positive_growth_today: 3,
        last_successful_collection_at: '2026-08-10T00:00:00Z',
        last_run_status: 'SUCCESS',
      },
    })
  })
}

export async function assertNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  if (overflow > 0) {
    throw new Error(`Horizontal overflow detected: ${overflow}px`)
  }
}

