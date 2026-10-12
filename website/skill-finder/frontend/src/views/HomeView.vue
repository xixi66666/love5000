<script setup lang="ts">
import { ArrowLeft, ArrowRight, LoaderCircle, RefreshCw } from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FilterSidebar from '@/components/FilterSidebar.vue'
import RepositoryListItem from '@/components/RepositoryListItem.vue'
import SparklineChart from '@/components/SparklineChart.vue'
import StatePanel from '@/components/StatePanel.vue'
import { triggerCollectionRefresh } from '@/api/collections'
import { fromAxiosError } from '@/api/client'
import { fetchLanguages, fetchRepositories, fetchStats } from '@/api/repositories'
import type { Category, LanguageStat, RepositoryListResponse, RepositoryQuery, SortKey } from '@/types/api'
import {
  handleCoverError,
  repoAvatarUrl,
  repoFallbackCoverUrl,
  repoOgCoverUrl,
} from '@/utils/covers'

type GsapInstance = (typeof import('gsap'))['gsap']
type ScrollTriggerInstance = (typeof import('gsap/ScrollTrigger'))['ScrollTrigger']

const route = useRoute()
const router = useRouter()
const rootEl = ref<HTMLElement | null>(null)

const items = ref<RepositoryListResponse['items']>([])
const total = ref(0)
const loading = ref(false)
const initialLoading = ref(true)
const error = ref(false)
const lastCollectionAt = ref<string | null>(null)
const stats = ref<{ total_repositories: number; positive_growth_today: number }>({
  total_repositories: 0,
  positive_growth_today: 0,
})
const languages = ref<LanguageStat[]>([])
const page = ref(1)
const filtersVisible = ref(false)

const filters = reactive({
  sort: 'daily_stars' as SortKey,
  category: '' as Category | '',
  language: '',
  minStars: null as number | null,
  q: '',
})

const pageSize = 20

const SORT_TABS: { key: SortKey; label: string }[] = [
  { key: 'daily_stars', label: '今日增长' },
  { key: 'weekly_stars', label: '7 日增长' },
  { key: 'monthly_stars', label: '30 日增长' },
  { key: 'total_stars', label: '总 Star' },
]

const CATEGORY_SLICES: { value: Category | ''; label: string; caption: string }[] = [
  { value: '', label: '全部', caption: '所有 AI 相关项目' },
  { value: 'AGENT', label: 'Agent', caption: '自主智能体与编排框架' },
  { value: 'SKILL', label: 'Skill', caption: '可复用的技能与工具包' },
  { value: 'MCP', label: 'MCP', caption: 'Model Context Protocol 生态' },
  { value: 'PLUGIN', label: '插件', caption: '编辑器与平台扩展' },
]

const hasActiveFilters = computed(
  () => filters.category !== '' || filters.language !== '' || filters.minStars != null,
)

const heroCards = computed(() => items.value.slice(0, 3))
const movers = computed(() => items.value.slice(0, 10))
const signals = computed(() => items.value.filter((repo) => repo.description).slice(0, 5))
const signalIndex = ref(0)
const currentSignal = computed(() => signals.value[signalIndex.value] ?? null)

const inlineMediaUrl = computed(() => {
  const first = heroCards.value[0]
  return first ? repoAvatarUrl(first.owner, 400) : repoFallbackCoverUrl('ai', 'signal', 400, 400)
})

function heroCoverUrl(owner: string, name: string): string {
  return repoOgCoverUrl(owner, name)
}

function onHeroCoverError(event: Event, owner: string, name: string) {
  handleCoverError(event, repoFallbackCoverUrl(owner, name))
}

function categoryMedia(value: Category | ''): string {
  return `https://picsum.photos/seed/trend-${(value || 'all').toLowerCase()}/900/1200`
}

function formatSigned(value: number | null): string {
  if (value == null) return '--'
  return value > 0 ? `+${value.toLocaleString('en-US')}` : value.toLocaleString('en-US')
}

function formatShortTime(value: string | null): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function cardSpan(index: number): string {
  if (index === 0) return 'span-6'
  if (index === 1 || index === 2) return 'span-3'
  const regularIndex = index - 3
  const regularCount = Math.max(0, items.value.length - 3)
  const remainder = regularCount % 3
  const tailStart = regularCount - remainder
  if (remainder === 1 && regularIndex === regularCount - 1) return 'span-12'
  if (remainder === 2 && regularIndex >= tailStart) return 'span-6'
  return 'span-4'
}

function nextSignal() {
  if (signals.value.length < 2) return
  signalIndex.value = (signalIndex.value + 1) % signals.value.length
}

function prevSignal() {
  if (signals.value.length < 2) return
  signalIndex.value = (signalIndex.value - 1 + signals.value.length) % signals.value.length
}

function scrollToTrending() {
  document.getElementById('trending')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function queryFromRoute(): Partial<RepositoryQuery> {
  const params = route.query
  return {
    sort: (params.sort as SortKey) || 'daily_stars',
    category: ((params.category as string) || '') as Category | '',
    language: (params.language as string) || '',
    min_stars: params.min_stars ? Number(params.min_stars) : null,
    q: (params.q as string) || '',
  }
}

function writeFiltersToUrl() {
  const query: Record<string, string> = {}
  if (filters.sort !== 'daily_stars') query.sort = filters.sort
  if (filters.category) query.category = filters.category
  if (filters.language) query.language = filters.language
  if (filters.minStars != null) query.min_stars = String(filters.minStars)
  if (filters.q) query.q = filters.q
  router.replace({ query })
}

async function loadRepositories() {
  loading.value = true
  error.value = false
  try {
    const params: RepositoryQuery = {
      page: page.value,
      page_size: pageSize,
      sort: filters.sort,
      category: filters.category || undefined,
      language: filters.language || undefined,
      min_stars: filters.minStars ?? undefined,
      q: filters.q || undefined,
    }
    const data = await fetchRepositories(params)
    items.value = data.items
    total.value = data.total
    lastCollectionAt.value = data.last_successful_collection_at
    signalIndex.value = 0
  } catch {
    error.value = true
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

function onSortChange(sort: SortKey) {
  if (filters.sort === sort) return
  filters.sort = sort
  page.value = 1
  writeFiltersToUrl()
  void loadRepositories()
}

function updateFilters(partial: Partial<typeof filters>) {
  Object.assign(filters, partial)
  page.value = 1
  writeFiltersToUrl()
  void loadRepositories()
}

function resetFilters() {
  updateFilters({ category: '', language: '', minStars: null, q: '' })
}

function goToPage(next: number) {
  page.value = next
  writeFiltersToUrl()
  void loadRepositories()
}

const totalPages = () => Math.max(1, Math.ceil(total.value / pageSize))

function applyRouteFilters() {
  const fromRoute = queryFromRoute()
  const { min_stars: minStars, ...rest } = fromRoute
  Object.assign(filters, rest, { minStars: minStars ?? null })
}

watch(
  () => route.query,
  () => {
    applyRouteFilters()
    void loadRepositories()
  },
)

onMounted(async () => {
  applyRouteFilters()
  void loadRepositories()
  await loadHeaderData()
  document.addEventListener('keydown', onKeydown)
  void initMotion()
})

async function loadHeaderData() {
  const [langs, statsData] = await Promise.all([fetchLanguages(), fetchStats()])
  languages.value = langs
  stats.value = statsData
  lastCollectionAt.value = statsData.last_successful_collection_at
}

const POLL_INTERVAL_MS = 5000
const POLL_TIMEOUT_MS = 15 * 60 * 1000

const refreshing = ref(false)
const refreshNotice = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let pollElapsedMs = 0
let pollSawRunning = false
let pollBaseline: string | null = null

async function onRefreshData() {
  if (refreshing.value) return
  refreshNotice.value = ''
  try {
    pollBaseline = lastCollectionAt.value
    await triggerCollectionRefresh()
  } catch (cause: unknown) {
    refreshNotice.value = cause instanceof Error ? fromAxiosError(cause).userMessage : '触发采集失败，请稍后重试。'
    return
  }
  refreshing.value = true
  pollSawRunning = false
  pollElapsedMs = 0
  refreshNotice.value = '采集中，通常需要几分钟，完成后自动刷新榜单。'
  pollTimer = setInterval(() => {
    void pollCollectionStatus()
  }, POLL_INTERVAL_MS)
}

async function pollCollectionStatus() {
  pollElapsedMs += POLL_INTERVAL_MS
  try {
    const statsData = await fetchStats()
    if (statsData.last_run_status === 'RUNNING') pollSawRunning = true
    const succeededAt = statsData.last_successful_collection_at
    if (succeededAt && succeededAt !== pollBaseline) {
      finishRefresh('')
      return
    }
    if (pollSawRunning && statsData.last_run_status === 'FAILED') {
      finishRefresh('采集执行失败，请稍后重试。')
      return
    }
  } catch {
    // 轮询中的瞬时网络错误不中断等待
  }
  if (pollElapsedMs >= POLL_TIMEOUT_MS) {
    finishRefresh('采集超时，请稍后手动刷新页面查看结果。')
  }
}

function finishRefresh(notice: string) {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  refreshing.value = false
  refreshNotice.value = notice
  if (!notice) {
    void loadRepositories()
    void loadHeaderData()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && filtersVisible.value) {
    filtersVisible.value = false
    const trigger = document.querySelector<HTMLButtonElement>('[data-testid="open-filters"]')
    trigger?.focus()
  }
}

let gsapRef: GsapInstance | null = null
let scrollTriggerRef: ScrollTriggerInstance | null = null
const motionCleanups: (() => void)[] = []

function motionAllowed(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

async function initMotion() {
  const root = rootEl.value
  if (!motionAllowed() || !root) return
  try {
    const gsapModule = await import('gsap')
    const scrollTriggerModule = await import('gsap/ScrollTrigger')
    const gsap = gsapModule.gsap
    const { ScrollTrigger } = scrollTriggerModule
    gsap.registerPlugin(ScrollTrigger)
    gsapRef = gsap
    scrollTriggerRef = ScrollTrigger

    const ctx = gsap.context(() => {
      gsap
        .timeline({ defaults: { ease: 'power3.out' } })
        .fromTo('[data-hero-eyebrow]', { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.7 })
        .fromTo(
          '[data-hero-line]',
          { y: 52, autoAlpha: 0 },
          { y: 0, autoAlpha: 1, duration: 1, stagger: 0.14 },
          '-=0.35',
        )
        .fromTo('[data-hero-lede]', { y: 24, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.8 }, '-=0.55')
        .fromTo(
          '[data-hero-action]',
          { y: 18, autoAlpha: 0 },
          { y: 0, autoAlpha: 1, duration: 0.6, stagger: 0.1 },
          '-=0.45',
        )
        .fromTo(
          '[data-hero-float]',
          { y: 70, autoAlpha: 0, rotate: 8 },
          { y: 0, autoAlpha: 1, rotate: 0, duration: 1.1, stagger: 0.15 },
          '-=0.9',
        )
    }, root)
    motionCleanups.push(() => ctx.revert())

    const heroSection = root.querySelector<HTMLElement>('.hero')
    const floats = gsap.utils.toArray<HTMLElement>('[data-hero-float]')
    if (heroSection && floats.length) {
      heroSection.addEventListener('mousemove', (event) => {
        const rect = heroSection.getBoundingClientRect()
        const dx = (event.clientX - rect.left) / rect.width - 0.5
        const dy = (event.clientY - rect.top) / rect.height - 0.5
        floats.forEach((card, index) => {
          gsap.to(card, {
            x: dx * (20 + index * 12),
            y: dy * (16 + index * 9),
            duration: 1,
            ease: 'power2.out',
            overwrite: 'auto',
          })
        })
      })
    }

    setupDynamicMotion()
  } catch {
    gsapRef = null
    scrollTriggerRef = null
  }
}

function setupDynamicMotion() {
  const gsap = gsapRef
  const ScrollTrigger = scrollTriggerRef
  const root = rootEl.value
  if (!gsap || !ScrollTrigger || !root) return

  gsap.utils.toArray<HTMLElement>(root.querySelectorAll('[data-motion-card]')).forEach((card) => {
    if (card.dataset.motionReady === '1') return
    card.dataset.motionReady = '1'
    const reveal = gsap.fromTo(
      card,
      { scale: 0.94, autoAlpha: 0 },
      {
        scale: 1,
        autoAlpha: 1,
        duration: 0.9,
        ease: 'power3.out',
        scrollTrigger: { trigger: card, start: 'top 92%', toggleActions: 'play none none reverse' },
      },
    )
    motionCleanups.push(() => {
      reveal.scrollTrigger?.kill()
      reveal.kill()
    })
    const image = card.querySelector('.repo-media-img')
    if (image) {
      const fade = gsap.to(image, {
        opacity: 0.32,
        ease: 'none',
        scrollTrigger: { trigger: card, start: 'bottom 45%', end: 'bottom 8%', scrub: true },
      })
      motionCleanups.push(() => {
        fade.scrollTrigger?.kill()
        fade.kill()
      })
    }
  })

  const pinEl = root.querySelector<HTMLElement>('.movers-pin')
  const listEl = root.querySelector<HTMLElement>('.movers-list')
  if (
    pinEl &&
    listEl &&
    pinEl.dataset.motionReady !== '1' &&
    window.matchMedia('(min-width: 1024px)').matches
  ) {
    pinEl.dataset.motionReady = '1'
    const pinTrigger = ScrollTrigger.create({
      trigger: listEl,
      start: 'top 180px',
      end: 'bottom 75%',
      pin: pinEl,
      pinSpacing: false,
      anticipatePin: 1,
    })
    motionCleanups.push(() => pinTrigger.kill())
  }
}

watch(items, async () => {
  await nextTick()
  setupDynamicMotion()
  scrollTriggerRef?.refresh()
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  while (motionCleanups.length) {
    const cleanup = motionCleanups.pop()
    cleanup?.()
  }
  gsapRef = null
  scrollTriggerRef = null
})
</script>

<template>
  <div ref="rootEl" class="home">
    <div v-if="filtersVisible" class="drawer-backdrop" data-testid="drawer-backdrop" @click="filtersVisible = false"></div>
    <aside class="filter-drawer" :class="{ open: filtersVisible }" aria-hidden="false">
      <FilterSidebar
        :model-value="{ category: filters.category, language: filters.language, minStars: filters.minStars }"
        :languages="languages"
        @update:model-value="
          (value) =>
            updateFilters({ category: value.category, language: value.language, minStars: value.minStars })
        "
        @close="filtersVisible = false"
      />
    </aside>

    <section class="hero" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="hero-eyebrow" data-hero-eyebrow>GITHUB TRENDING · 每日采集 · 真实增量</p>
        <h1 id="hero-title" class="hero-title">
          <span class="hero-line" data-hero-line>把每一次 AI 脉冲</span>
          <span class="hero-line" data-hero-line>
            变成<span class="hero-inline-media" aria-hidden="true" :style="{ backgroundImage: `url(${inlineMediaUrl})` }"></span>可读的趋势
          </span>
        </h1>
        <p class="hero-lede" data-hero-lede>
          每天采集 GitHub Trending 日 / 周 / 月榜，过滤 Agent、Skill、MCP 与插件项目，
          用真实的 Star 增量告诉你什么正在发生。
        </p>
        <div class="hero-actions">
          <button
            type="button"
            class="cta-primary"
            data-hero-action
            data-testid="refresh-data"
            :disabled="refreshing"
            @click="onRefreshData"
          >
            <LoaderCircle v-if="refreshing" :size="17" class="spinner" aria-hidden="true" />
            <RefreshCw v-else :size="17" aria-hidden="true" />
            {{ refreshing ? '采集中…' : '刷新数据' }}
          </button>
          <button type="button" class="cta-ghost" data-hero-action @click="scrollToTrending">
            浏览今日榜单
          </button>
        </div>
        <p v-if="refreshNotice" class="hero-notice" role="status" data-testid="refresh-notice">
          {{ refreshNotice }}
        </p>
      </div>

      <div class="hero-visual" aria-hidden="true">
        <template v-if="heroCards.length">
          <article
            v-for="(repo, index) in heroCards"
            :key="repo.id"
            class="hero-float-card"
            :class="`float-${index}`"
            data-hero-float
          >
            <img
              :src="heroCoverUrl(repo.owner, repo.name)"
              alt=""
              loading="lazy"
              decoding="async"
              @error="onHeroCoverError($event, repo.owner, repo.name)"
            />
            <div class="float-body">
              <span class="float-name">{{ repo.name }}</span>
              <span class="float-growth">{{ formatSigned(repo.daily_stars) }} 今日</span>
            </div>
          </article>
        </template>
        <template v-else>
          <article v-for="n in 3" :key="n" class="hero-float-card" :class="`float-${n - 1}`" data-hero-float>
            <div class="float-skeleton"></div>
          </article>
        </template>
      </div>
    </section>

    <section class="stats-strip" aria-label="数据概览">
      <div class="section-inner stats-grid">
        <div class="stat-cell">
          <span class="stat-value">{{ stats.total_repositories }}</span>
          <span class="stat-label">追踪仓库</span>
        </div>
        <div class="stat-cell">
          <span class="stat-value">{{ stats.positive_growth_today }}</span>
          <span class="stat-label">今日正增长</span>
        </div>
        <div class="stat-cell">
          <span class="stat-value">{{ languages.length }}</span>
          <span class="stat-label">覆盖语言</span>
        </div>
        <div class="stat-cell">
          <span class="stat-value is-time">{{ formatShortTime(lastCollectionAt) }}</span>
          <span class="stat-label">最近采集</span>
        </div>
      </div>
    </section>

    <section class="section category-section" aria-label="按分类探索">
      <div class="section-inner">
        <header class="section-head">
          <h2 class="section-title">按分类进入</h2>
          <p class="section-caption">把浩瀚的 AI 生态切成四条清晰的入口</p>
        </header>
        <div class="accordion" role="group" aria-label="分类筛选">
          <button
            v-for="slice in CATEGORY_SLICES"
            :key="slice.value || 'all'"
            type="button"
            class="accordion-slice"
            :class="{ 'is-active': filters.category === slice.value }"
            :aria-pressed="filters.category === slice.value"
            :style="{ backgroundImage: `url(${categoryMedia(slice.value)})` }"
            @click="updateFilters({ category: slice.value })"
          >
            <span class="slice-shade" aria-hidden="true"></span>
            <span class="slice-content">
              <span class="slice-label">{{ slice.label }}</span>
              <span class="slice-caption">{{ slice.caption }}</span>
            </span>
          </button>
        </div>
      </div>
    </section>

    <section id="trending" class="section trending-section" aria-labelledby="trending-title">
      <div class="section-inner">
        <header class="section-head">
          <h2 id="trending-title" class="section-title">今日榜单</h2>
          <p class="section-caption">
            共 {{ total }} 个仓库 · 最近采集 {{ formatShortTime(lastCollectionAt) }}
          </p>
        </header>

        <div class="trending-toolbar">
          <div class="sort-tabs" role="tablist" aria-label="排序方式">
            <button
              v-for="tab in SORT_TABS"
              :key="tab.key"
              type="button"
              role="tab"
              class="sort-tab"
              :class="{ active: filters.sort === tab.key }"
              :aria-selected="filters.sort === tab.key"
              :data-testid="`sort-${tab.key}`"
              @click="onSortChange(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>
          <div class="toolbar-filters">
            <select
              class="toolbar-select"
              :value="filters.language"
              aria-label="按语言筛选"
              data-testid="language-select"
              @change="updateFilters({ language: ($event.target as HTMLSelectElement).value })"
            >
              <option value="">全部语言</option>
              <option v-for="lang in languages" :key="lang.language" :value="lang.language">
                {{ lang.language }} ({{ lang.count }})
              </option>
            </select>
            <select
              class="toolbar-select"
              :value="String(filters.minStars ?? '')"
              aria-label="按最低 Star 筛选"
              data-testid="min-stars-select"
              @change="
                updateFilters({
                  minStars:
                    ($event.target as HTMLSelectElement).value === ''
                      ? null
                      : Number(($event.target as HTMLSelectElement).value),
                })
              "
            >
              <option value="">不限 Star</option>
              <option value="1000">≥ 1,000</option>
              <option value="5000">≥ 5,000</option>
              <option value="10000">≥ 10,000</option>
            </select>
            <button
              v-if="hasActiveFilters"
              type="button"
              class="toolbar-reset"
              data-testid="clear-filters"
              @click="resetFilters"
            >
              清除筛选
            </button>
            <button
              type="button"
              class="mobile-filter-button"
              data-testid="open-filters"
              @click="filtersVisible = true"
            >
              筛选
            </button>
          </div>
        </div>

        <StatePanel v-if="initialLoading" variant="skeleton" title="加载中" />

        <StatePanel
          v-else-if="error"
          variant="error"
          title="加载失败"
          message="无法获取仓库数据，请检查网络后重试。"
          @action="loadRepositories"
        />

        <StatePanel
          v-else-if="items.length === 0"
          variant="empty"
          title="没有匹配的仓库"
          message="试试调整筛选条件或清空搜索。"
          @action="resetFilters"
        />

        <template v-else>
          <div class="bento" :class="{ 'is-loading': loading }" role="list">
            <RepositoryListItem
              v-for="(repo, index) in items"
              :key="repo.id"
              :repo="repo"
              :rank="(page - 1) * pageSize + index + 1"
              :class="cardSpan(index)"
              data-motion-card
            />
          </div>
          <nav v-if="totalPages() > 1" class="pagination" aria-label="分页">
            <button
              type="button"
              class="page-button"
              :disabled="page <= 1"
              aria-label="上一页"
              @click="goToPage(page - 1)"
            >
              上一页
            </button>
            <span class="page-info">第 {{ page }} / {{ totalPages() }} 页</span>
            <button
              type="button"
              class="page-button"
              :disabled="page >= totalPages()"
              aria-label="下一页"
              @click="goToPage(page + 1)"
            >
              下一页
            </button>
          </nav>
        </template>
      </div>
    </section>

    <section v-if="movers.length" class="section movers-section" aria-labelledby="movers-title">
      <div class="section-inner movers-layout">
        <div class="movers-pin">
          <h2 id="movers-title" class="section-title">
            增长最快
            <em>此刻正在发生</em>
          </h2>
          <p class="section-caption">
            按当前排序取前十，滚动查看今天的脉冲信号。每一项都可以点进仓库详情，看到 30 天趋势曲线。
          </p>
        </div>
        <ol class="movers-list">
          <li v-for="(repo, index) in movers" :key="repo.id" class="mover-row">
            <span class="mover-rank">{{ String(index + 1).padStart(2, '0') }}</span>
            <RouterLink
              class="mover-name"
              :to="`/repositories/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}`"
            >
              {{ repo.owner }}/{{ repo.name }}
            </RouterLink>
            <SparklineChart :points="repo.trend" />
            <span class="mover-value">{{ formatSigned(repo.daily_stars) }}</span>
          </li>
        </ol>
      </div>
    </section>

    <section v-if="currentSignal" class="section signals-section" aria-label="趋势信号">
      <div class="section-inner signals-layout">
        <div class="signals-visual" aria-hidden="true">
          <div
            v-for="(signal, index) in signals.slice(0, 3)"
            :key="signal.id"
            class="signal-portrait"
            :class="{ 'is-current': index === signalIndex % 3 }"
            :style="{ backgroundImage: `url(${repoAvatarUrl(signal.owner, 600)})` }"
          ></div>
        </div>
        <div class="signals-copy">
          <p class="signals-eyebrow">SIGNAL FROM THE TRENDING</p>
          <blockquote class="signal-quote">{{ currentSignal.description }}</blockquote>
          <p class="signal-author">{{ currentSignal.owner }}/{{ currentSignal.name }}</p>
          <div class="signal-controls">
            <button type="button" aria-label="上一条信号" :disabled="signals.length < 2" @click="prevSignal">
              <ArrowLeft :size="17" aria-hidden="true" />
            </button>
            <button type="button" aria-label="下一条信号" :disabled="signals.length < 2" @click="nextSignal">
              <ArrowRight :size="17" aria-hidden="true" />
            </button>
            <span class="signal-count">{{ signalIndex + 1 }} / {{ signals.length }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  position: relative;
  padding-top: 92px;
}

.section-inner {
  width: min(1200px, calc(100% - 48px));
  margin: 0 auto;
}

.section {
  position: relative;
  padding: clamp(96px, 11vw, 176px) 0;
}

.section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 40px;
}

.section-title {
  font-family: var(--font-display);
  font-size: clamp(1.9rem, 3.6vw, 3.1rem);
  font-weight: 900;
  line-height: 1.06;
  letter-spacing: -0.02em;
}

.section-title em {
  display: block;
  margin-top: 6px;
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  font-size: 0.62em;
  color: var(--color-accent);
}

.section-caption {
  max-width: 420px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.hero {
  position: relative;
  width: min(1200px, calc(100% - 48px));
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
  align-items: center;
  gap: 48px;
  min-height: calc(100vh - 92px);
  padding: 40px 0 80px;
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 720px;
}

.hero-eyebrow {
  margin-bottom: 22px;
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.24em;
}

.hero-title {
  font-family: var(--font-display);
  font-size: clamp(2.4rem, 4vw, 4rem);
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: -0.035em;
}

.hero-line {
  display: block;
}

.hero-inline-media {
  display: inline-block;
  width: clamp(64px, 6.2vw, 100px);
  height: clamp(34px, 3.3vw, 54px);
  margin: 0 10px;
  border-radius: 999px;
  background-size: cover;
  background-position: center;
  filter: grayscale(0.2) contrast(1.1) brightness(0.92);
  vertical-align: middle;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
}

.hero-lede {
  max-width: 560px;
  margin-top: 26px;
  color: var(--color-text-secondary);
  font-size: clamp(0.95rem, 1.2vw, 1.1rem);
  line-height: 1.75;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 36px;
}

.cta-primary,
.cta-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 56px;
  padding: 0 30px;
  border-radius: var(--radius-button);
  font-size: 15px;
  font-weight: 700;
  transition: transform 240ms ease, background 240ms ease, border-color 240ms ease;
}

.cta-primary {
  border: 0;
  background: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
}

.cta-primary:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 22px 50px var(--color-glow);
}

.cta-primary:disabled {
  opacity: 0.7;
  cursor: wait;
}

.cta-ghost {
  border: 1px solid var(--color-border-strong);
  background: var(--surface-glass);
  color: var(--color-text-primary);
}

.cta-ghost:hover {
  border-color: var(--color-accent);
  transform: translateY(-3px);
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.hero-notice {
  margin-top: 20px;
  padding: 12px 18px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--surface-glass);
  color: var(--color-text-secondary);
  font-size: 13px;
}

.hero-visual {
  position: relative;
  z-index: 1;
  height: 480px;
}

.hero-float-card {
  position: absolute;
  width: min(300px, 68%);
  border: 1px solid var(--color-border-strong);
  border-radius: 24px;
  background: var(--color-canvas);
  overflow: hidden;
  box-shadow: 0 44px 90px rgba(0, 0, 0, 0.5);
  animation: float-in 900ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

.float-0 {
  top: 6%;
  right: 4%;
  width: min(330px, 74%);
  z-index: 3;
}

.float-1 {
  top: 44%;
  left: 0;
  z-index: 2;
  transform: rotate(-4deg);
  animation-delay: 120ms;
}

.float-2 {
  top: 68%;
  right: 14%;
  z-index: 1;
  transform: rotate(3deg);
  animation-delay: 240ms;
}

.hero-float-card img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  filter: grayscale(0.3) contrast(1.06) brightness(0.9);
}

[data-theme='dark'] .hero-float-card img {
  filter: grayscale(0.3) contrast(1.02) brightness(0.74);
}

.float-skeleton {
  aspect-ratio: 16 / 9;
  background: var(--color-skeleton);
  animation: pulse 1.4s ease-in-out infinite;
}

.float-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
}

.float-name {
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.float-growth {
  flex: 0 0 auto;
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

@keyframes float-in {
  from {
    opacity: 0;
    transform: translateY(40px) rotate(6deg);
  }

  to {
    opacity: 1;
    transform: translateY(0) rotate(0);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}

.stats-strip {
  position: relative;
  padding: 8px 0 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.stat-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 34px 28px;
  border-right: 1px solid var(--color-border);
}

.stat-cell:last-child {
  border-right: 0;
}

.stat-value {
  font-family: var(--font-display);
  font-size: clamp(2rem, 3.4vw, 3rem);
  font-weight: 900;
  letter-spacing: -0.03em;
}

.stat-value.is-time {
  font-size: clamp(1.2rem, 2vw, 1.7rem);
  padding: 10px 0;
}

.stat-label {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.accordion {
  display: flex;
  gap: 10px;
  height: 420px;
}

.accordion-slice {
  position: relative;
  flex: 1;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 24px;
  background-size: cover;
  background-position: center;
  overflow: hidden;
  transition: flex 600ms cubic-bezier(0.22, 1, 0.36, 1), border-color 300ms ease;
}

.accordion-slice:hover,
.accordion-slice.is-active {
  flex: 3.4;
  border-color: var(--color-border-strong);
}

.slice-shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(5, 8, 11, 0.3) 0%, rgba(5, 8, 11, 0.82) 100%);
  transition: background 400ms ease;
}

.accordion-slice:hover .slice-shade,
.accordion-slice.is-active .slice-shade {
  background: linear-gradient(180deg, rgba(5, 8, 11, 0.16) 0%, rgba(5, 8, 11, 0.72) 100%);
}

.accordion-slice.is-active .slice-shade {
  background: linear-gradient(180deg, rgba(5, 8, 11, 0.1) 0%, rgba(11, 18, 6, 0.82) 100%);
}

.slice-content {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 26px 22px;
  text-align: left;
}

.slice-label {
  font-family: var(--font-display);
  font-size: clamp(1.4rem, 2.2vw, 2rem);
  font-weight: 900;
  color: #ffffff;
  letter-spacing: -0.02em;
}

.accordion-slice.is-active .slice-label {
  color: var(--color-accent);
}

.slice-caption {
  max-width: 240px;
  color: rgba(255, 255, 255, 0.66);
  font-size: 12px;
  line-height: 1.5;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 400ms ease 120ms, transform 400ms ease 120ms;
}

.accordion-slice:hover .slice-caption,
.accordion-slice.is-active .slice-caption {
  opacity: 1;
  transform: translateY(0);
}

.trending-section {
  scroll-margin-top: 96px;
}

.trending-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 34px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: var(--surface-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.sort-tabs {
  display: inline-flex;
  gap: 4px;
}

.sort-tab {
  min-height: 40px;
  padding: 0 18px;
  border: 0;
  border-radius: var(--radius-button);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
  transition: background 220ms ease, color 220ms ease;
}

.sort-tab:hover {
  color: var(--color-text-primary);
  background: var(--surface-glass-strong);
}

.sort-tab.active {
  background: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
}

.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.toolbar-select {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: var(--color-canvas);
  color: var(--color-text-primary);
  font-size: 12px;
}

.toolbar-select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.toolbar-reset {
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: transparent;
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 600;
}

.toolbar-reset:hover {
  border-color: var(--color-accent);
}

.mobile-filter-button {
  display: none;
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: transparent;
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 600;
}

.bento {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-flow: dense;
  gap: 16px;
  transition: opacity 300ms ease;
}

.bento.is-loading {
  opacity: 0.55;
}

.span-3 {
  grid-column: span 3;
}

.span-4 {
  grid-column: span 4;
}

.span-6 {
  grid-column: span 6;
}

.span-12 {
  grid-column: span 12;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 56px 0 0;
}

.page-button {
  min-height: 44px;
  padding: 0 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: var(--surface-glass);
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 600;
  transition: border-color 200ms ease, transform 200ms ease;
}

.page-button:hover:not(:disabled) {
  border-color: var(--color-accent);
  transform: translateY(-2px);
}

.page-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.movers-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr);
  gap: clamp(40px, 6vw, 96px);
  align-items: start;
}

.movers-pin .section-caption {
  margin-top: 20px;
}

.movers-list {
  display: flex;
  flex-direction: column;
  list-style: none;
  border-top: 1px solid var(--color-border);
}

.mover-row {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 6px;
  border-bottom: 1px solid var(--color-border);
  transition: background 240ms ease, padding-left 240ms ease;
}

.mover-row:hover {
  background: var(--surface-glass);
  padding-left: 14px;
}

.mover-rank {
  flex: 0 0 auto;
  width: 34px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
}

.mover-row:nth-child(-n + 3) .mover-rank {
  color: var(--color-accent);
}

.mover-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
}

.mover-name:hover {
  color: var(--color-accent);
}

.mover-value {
  flex: 0 0 auto;
  min-width: 64px;
  text-align: right;
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
}

.signals-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 1.15fr);
  gap: clamp(40px, 6vw, 96px);
  align-items: center;
}

.signals-visual {
  position: relative;
  height: 420px;
}

.signal-portrait {
  position: absolute;
  width: 62%;
  aspect-ratio: 3 / 4;
  border-radius: 26px;
  background-size: cover;
  background-position: center;
  filter: grayscale(0.55) contrast(1.1) brightness(0.85);
  border: 1px solid var(--color-border);
  transition: transform 500ms cubic-bezier(0.22, 1, 0.36, 1), opacity 500ms ease, filter 500ms ease;
}

.signal-portrait:nth-child(1) {
  top: 0;
  left: 0;
  z-index: 3;
}

.signal-portrait:nth-child(2) {
  top: 18%;
  left: 24%;
  z-index: 2;
  opacity: 0.72;
}

.signal-portrait:nth-child(3) {
  top: 36%;
  left: 48%;
  z-index: 1;
  opacity: 0.45;
}

.signal-portrait.is-current {
  transform: translateY(-10px);
  filter: grayscale(0.15) contrast(1.06) brightness(0.95);
}

.signals-copy {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.signals-eyebrow {
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.22em;
}

.signal-quote {
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 2.4vw, 2rem);
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: -0.01em;
}

.signal-quote::before {
  content: '“';
  color: var(--color-accent);
}

.signal-quote::after {
  content: '”';
  color: var(--color-accent);
}

.signal-author {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
}

.signal-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.signal-controls button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--surface-glass);
  color: var(--color-text-primary);
  transition: border-color 200ms ease, transform 200ms ease;
}

.signal-controls button:hover:not(:disabled) {
  border-color: var(--color-accent);
  transform: translateY(-2px);
}

.signal-controls button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.signal-count {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}

.filter-drawer {
  display: none;
}

.drawer-backdrop {
  display: none;
}

@media (max-width: 1180px) {
  .bento .span-6 {
    grid-column: span 12;
  }

  .bento .span-4 {
    grid-column: span 6;
  }

  .bento .span-3 {
    grid-column: span 6;
  }
}

@media (max-width: 1024px) {
  .hero {
    grid-template-columns: 1fr;
    min-height: 0;
    padding: 24px 0 60px;
  }

  .hero-visual {
    height: 380px;
  }

  .accordion {
    height: auto;
    flex-direction: column;
  }

  .accordion-slice {
    min-height: 120px;
  }

  .accordion-slice:hover,
  .accordion-slice.is-active {
    flex: 1;
  }

  .movers-layout,
  .signals-layout {
    grid-template-columns: 1fr;
  }

  .signals-visual {
    height: 320px;
  }
}

@media (max-width: 860px) {
  .home {
    padding-top: 148px;
  }

  .trending-toolbar {
    border-radius: 24px;
  }

  .toolbar-filters .toolbar-select {
    display: none;
  }

  .mobile-filter-button {
    display: inline-flex;
    align-items: center;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-cell {
    border-bottom: 1px solid var(--color-border);
  }

  .stat-cell:nth-child(2n) {
    border-right: 0;
  }

  .stat-cell:nth-child(n + 3) {
    border-bottom: 0;
  }
}

@media (max-width: 640px) {
  .section-inner,
  .hero {
    width: calc(100% - 32px);
  }

  .bento {
    gap: 12px;
  }

  .bento .span-6,
  .bento .span-4,
  .bento .span-3,
  .bento .span-12 {
    grid-column: span 12;
  }

  .hero-visual {
    height: 320px;
  }

  .filter-drawer {
    display: block;
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: 70;
    width: 300px;
    max-width: 86vw;
    padding: 24px 20px;
    background: var(--color-canvas);
    border-right: 1px solid var(--color-border);
    box-shadow: 0 0 80px rgba(0, 0, 0, 0.5);
    transform: translateX(-102%);
    transition: transform 280ms cubic-bezier(0.22, 1, 0.36, 1);
    overflow-y: auto;
  }

  .filter-drawer.open {
    transform: translateX(0);
  }

  .drawer-backdrop {
    position: fixed;
    inset: 0;
    z-index: 69;
    display: block;
    background: rgba(3, 5, 8, 0.6);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
  }
}
</style>
