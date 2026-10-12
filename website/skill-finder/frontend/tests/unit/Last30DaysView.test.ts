import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Last30DaysView from '@/views/Last30DaysView.vue'

vi.mock('@/api/last30days', () => ({
  fetchLast30daysStatus: vi.fn(),
  fetchLast30daysRankings: vi.fn(),
  refreshLast30daysRankings: vi.fn(),
}))

import {
  fetchLast30daysRankings,
  fetchLast30daysStatus,
  refreshLast30daysRankings,
} from '@/api/last30days'
import type { Last30DaysRankingResponse } from '@/api/last30days'

const mockedStatus = vi.mocked(fetchLast30daysStatus)
const mockedFetch = vi.mocked(fetchLast30daysRankings)
const mockedRefresh = vi.mocked(refreshLast30daysRankings)

function rankingResponse(overrides: Partial<Last30DaysRankingResponse> = {}): Last30DaysRankingResponse {
  return {
    direction: 'agent',
    status: 'working',
    items: [
      {
        candidate_id: 'reddit-1',
        title: 'What developers are saying',
        source: 'reddit',
        url: 'https://www.reddit.com/r/example/1',
        published_at: '2026-08-20T00:00:00Z',
        summary: 'A grounded community summary.',
        engagement: { score: 210, comments: 42 },
        relevance_score: 0.95,
        cluster: 0,
      },
      {
        candidate_id: 'github-1',
        title: 'mvanhorn/last30days-skill',
        source: 'github',
        url: 'https://github.com/mvanhorn/last30days-skill',
        published_at: '2026-08-19T00:00:00Z',
        summary: 'AI agent skill that researches any topic.',
        engagement: { stars: 5020 },
        relevance_score: 0.88,
        cluster: 1,
      },
    ],
    clusters: [],
    sources: ['reddit', 'github'],
    source_status: { reddit: 'ok', github: 'ok' },
    fetched_at: '2026-08-21T00:00:00Z',
    message: null,
    ...overrides,
  }
}

describe('Last30DaysView', () => {
  beforeEach(() => {
    mockedStatus.mockReset()
    mockedFetch.mockReset()
    mockedRefresh.mockReset()
    mockedStatus.mockResolvedValue({
      status: 'working',
      sources: ['reddit', 'hackernews', 'github'],
    })
    mockedFetch.mockResolvedValue(rankingResponse())
  })

  it('loads the cached agent ranking on mount and renders ranked cards', async () => {
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('近 30 天最热')
    expect(mockedFetch).toHaveBeenCalledWith('agent')
    expect(wrapper.text()).toContain('What developers are saying')
    expect(wrapper.text()).toContain('mvanhorn/last30days-skill')
    expect(wrapper.text()).toContain('Reddit')
    expect(wrapper.text()).toContain('GitHub')
    expect(wrapper.text()).toContain('252 互动')
    expect(wrapper.text()).toContain('最近更新')
  })

  it('loads the skill ranking when switching tabs', async () => {
    mockedFetch.mockResolvedValueOnce(rankingResponse())
    mockedFetch.mockResolvedValueOnce(
      rankingResponse({ direction: 'skill', items: [] }),
    )
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    await wrapper.get('[data-testid="direction-skill"]').trigger('click')
    await flushPromises()

    expect(mockedFetch).toHaveBeenNthCalledWith(2, 'skill')
    expect(wrapper.text()).toContain('还没有榜单数据')
  })

  it('shows an empty state with a refresh action when nothing is cached', async () => {
    mockedFetch.mockResolvedValueOnce(
      rankingResponse({
        status: 'no-results',
        items: [],
        message: '该方向还没有榜单数据，点击刷新按钮生成。',
      }),
    )
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    expect(wrapper.text()).toContain('还没有榜单数据')
    expect(wrapper.text()).toContain('该方向还没有榜单数据，点击刷新按钮生成。')
    expect(wrapper.text()).toContain('立即刷新')
  })

  it('refreshes the ranking and renders the new data', async () => {
    mockedFetch.mockResolvedValueOnce(rankingResponse({ items: [] }))
    mockedRefresh.mockResolvedValueOnce(rankingResponse())
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    await wrapper.get('[data-testid="refresh-ranking"]').trigger('click')
    await flushPromises()

    expect(mockedRefresh).toHaveBeenCalledWith('agent')
    expect(wrapper.text()).toContain('What developers are saying')
    expect(wrapper.text()).not.toContain('正在刷新…')
  })

  it('shows an error notice when the refresh fails', async () => {
    mockedRefresh.mockRejectedValueOnce(new Error('网络连接失败，请检查网络'))
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    await wrapper.get('[data-testid="refresh-ranking"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('网络连接失败，请检查网络')
  })

  it('surfaces engine setup failures in the header badge', async () => {
    mockedStatus.mockResolvedValueOnce({
      status: 'unconfigured',
      sources: [],
      message: '未找到用户级 last30days skill。',
    })
    const wrapper = mount(Last30DaysView)
    await flushPromises()

    expect(wrapper.text()).toContain('需要配置')
    expect(wrapper.text()).toContain('未找到用户级 last30days skill。')
  })
})
