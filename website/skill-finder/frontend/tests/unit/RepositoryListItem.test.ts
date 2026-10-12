import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RepositoryListItem from '@/components/RepositoryListItem.vue'

import type { RepositoryListItem as Repo } from '@/types/api'

function makeRepo(overrides: Partial<Repo> = {}): Repo {
  return {
    id: 1,
    owner: 'octocat',
    name: 'agent-hub',
    description: 'An agent framework',
    html_url: 'https://github.com/octocat/agent-hub',
    language: 'Python',
    topics: ['ai-agent', 'agentic', 'llm', 'tools', 'extra'],
    categories: ['AGENT', 'MCP'],
    stars_count: 1500,
    daily_stars: 20,
    weekly_stars: 100,
    monthly_stars: 400,
    last_synced_at: '2026-08-10T00:00:00Z',
    trend: [],
    ...overrides,
  }
}

function mountItem(repo: Repo) {
  return mount(RepositoryListItem, {
    props: { repo },
    global: {
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('RepositoryListItem', () => {
  it('renders name, description and topics (max 4)', () => {
    const wrapper = mountItem(makeRepo())
    expect(wrapper.text()).toContain('agent-hub')
    expect(wrapper.text()).toContain('An agent framework')
    const topicChips = wrapper.findAll('[data-testid="topic"]')
    expect(topicChips.length).toBe(4)
  })

  it('shows growth values and keeps minus sign for negatives', () => {
    const wrapper = mountItem(
      makeRepo({ daily_stars: -5, weekly_stars: -20, monthly_stars: -40 }),
    )
    expect(wrapper.text()).toContain('-5')
    expect(wrapper.text()).toContain('-20')
    expect(wrapper.text()).toContain('-40')
    expect(wrapper.text()).toContain('30 日')
  })

  it('shows dash for null growth', () => {
    const wrapper = mountItem(
      makeRepo({ daily_stars: null, weekly_stars: null, monthly_stars: null }),
    )
    expect(wrapper.text()).toContain('--')
  })

  it('external link has proper attributes', () => {
    const wrapper = mountItem(makeRepo())
    const link = wrapper.find('[data-testid="external-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('aria-label')).toBeTruthy()
  })

  it('renders semantic article element', () => {
    const wrapper = mountItem(makeRepo())
    expect(wrapper.element.tagName.toLowerCase()).toBe('article')
  })
})
