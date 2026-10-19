import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dailyApi, type ConsoleSnapshot, type DailyReport } from '@/api/dailyReports'
import DailyReportsView from '@/views/DailyReportsView.vue'

const names = ['采集榜单', '筛选项目', '编排脚本', '准备素材', '生成配音', '对齐字幕', '渲染成片', '人工审核', '抖音发布', '消息送达']
const keys = ['collection', 'selection', 'script', 'assets', 'voice', 'captions', 'render', 'review', 'publish', 'notify']
function consoleData(status = 'idle', current = 'collection'): ConsoleSnapshot {
  return {
    date: '2026-10-19', today: '2026-10-19', timezone: 'Asia/Shanghai', status, recorded: true,
    workflow: { current, updated_at: '2026-10-19T15:00:00+08:00', events: [], stages: keys.map((id, i) => ({
      id, label: names[i], description: names[i], status: id === current ? 'running' : 'pending', detail: '', done: 0, total: 0,
    })) },
    runtime: [], assets: [], artifacts: [], samples: [], render_progress: null,
    template: { composition: 'SkillFinderDaily', width: 1080, height: 1920, fps: 30,
      directory: 'website/skill-finder/video-renderer', editor_url: '/daily-reports?panel=template', api: '/api/v1/daily-reports/template',
      files: [{ path: 'src/video.tsx', description: '主模板' }] },
  }
}
let data: ConsoleSnapshot
let reports: DailyReport[]
let wrappers: ReturnType<typeof mount>[]
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('isSecureContext', true)
  data = consoleData()
  reports = []
  wrappers = []
  vi.spyOn(dailyApi, 'get').mockImplementation(async url => ({ data: structuredClone(url.endsWith('/console') ? data : { items: reports }) }))
  vi.spyOn(dailyApi, 'post').mockResolvedValue({ data: { status: 'accepted', date: data.date } })
})
afterEach(() => {
  wrappers.forEach(wrapper => wrapper.unmount())
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers()
})
async function open() { const wrapper = mount(DailyReportsView); wrappers.push(wrapper); await flushPromises(); return wrapper }

describe('制作操作台', () => {
  it('can start today while inspecting an immutable older report', async () => {
    data = consoleData('pending_review', 'review')
    data.date = '2026-10-18'
    reports = [{ date: data.date, status: 'pending_review', items: [] }]
    const wrapper = await open()
    expect(wrapper.get('[data-testid="run-workflow"]').attributes('disabled')).toBeUndefined()
  })
  it('shows every real stage and follows new execution state while polling', async () => {
    data = consoleData('generating', 'voice')
    const wrapper = await open()
    expect(wrapper.findAll('.stage-button')).toHaveLength(10)
    expect(wrapper.get('#stage-title').text()).toBe('生成配音')
    data = consoleData('generating', 'render')
    data.render_progress = { phase: 'rendering', rendered_frames: 42, total_frames: 100, updated_at: data.workflow.updated_at }
    await vi.advanceTimersByTimeAsync(5000); await flushPromises()
    expect(wrapper.get('#stage-title').text()).toBe('渲染成片')
    expect(wrapper.get('progress').attributes('value')).toBe('42')
    expect(wrapper.text()).toContain('42 / 100 帧')
  })

  it('keeps a manually inspected stage selected when background progress changes', async () => {
    data = consoleData('generating', 'voice')
    const wrapper = await open()
    await wrapper.get('[data-testid="stage-script"]').trigger('click')
    data = consoleData('generating', 'render')
    await vi.advanceTimersByTimeAsync(5000); await flushPromises()
    expect(wrapper.get('#stage-title').text()).toBe('编排脚本')
    expect(wrapper.get('.run-summary').text()).toContain('渲染成片')
  })

  it('does not submit a task before a management key is provided', async () => {
    const wrapper = await open()
    await wrapper.get('[data-testid="run-workflow"]').trigger('click')
    expect(dailyApi.post).not.toHaveBeenCalled()
    expect(wrapper.get('[role="alert"]').text()).toContain('管理密钥')
    await wrapper.get('#review-key').setValue('only-a-test-key')
    await wrapper.get('[data-testid="run-workflow"]').trigger('click'); await flushPromises()
    expect(dailyApi.post).toHaveBeenCalledWith('/daily-reports/generate', {}, { headers: { 'X-Admin-Key': 'only-a-test-key' } })
    expect(window.localStorage.getItem('adminKey')).toBeNull()
  })

  it('never approves a sample in place of the current report', async () => {
    data = consoleData('pending_review', 'review')
    data.artifacts = [{ name: 'video.mp4', label: '视频', ready: true }]
    data.samples = [{ id: '20261019-144156', width: 1080, height: 1920, fps: 30, duration_seconds: 27 }]
    reports = [{ date: data.date, status: 'pending_review', items: [], script: '当前原稿', caption: '当前文案', review_digest: 'a'.repeat(64) }]
    const wrapper = await open()
    await wrapper.get('#review-key').setValue('only-a-test-key')
    const sampleButton = wrapper.findAll('.preview-toolbar button').find(button => button.text() === '接入样片')!
    await sampleButton.trigger('click')
    expect(wrapper.get('[data-testid="approve-video"]').attributes('disabled')).toBeDefined()
    await wrapper.findAll('.preview-toolbar button')[0].trigger('click')
    await wrapper.get('[data-testid="approve-video"]').trigger('click'); await flushPromises()
    expect(dailyApi.post).toHaveBeenCalledWith(`/daily-reports/${data.date}/review`,
      { decision: 'approve', expected_digest: 'a'.repeat(64) }, { headers: { 'X-Admin-Key': 'only-a-test-key' } })
  })

  it('offers the embedded template editor instead of requiring an external terminal', async () => {
    const wrapper = await open()
    await wrapper.get('.template-nav').trigger('click')
    expect(wrapper.text()).toContain('连接模板编辑器')
    expect(wrapper.text()).toContain('src/video.tsx')
    expect(wrapper.text()).not.toContain('pnpm studio')
    expect(dailyApi.post).not.toHaveBeenCalled()
  })
})
