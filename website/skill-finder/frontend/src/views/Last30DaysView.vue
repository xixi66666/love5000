<template>
  <main class="last30days-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">MULTI-SOURCE RESEARCH</p>
        <h1>近 30 天最热</h1>
        <p class="page-description">
          聚合 GitHub、Reddit、X、YouTube、Hacker News 等来源，按社区互动量呈现 Agent / Skill
          方向最近一个月最受关注的 Top 20。
        </p>
      </div>
      <div class="engine-state" :class="`state-${engineStatus}`" role="status">
        <Activity :size="16" aria-hidden="true" />
        <span>{{ engineStatusLabel }}</span>
      </div>
    </header>

    <div class="toolbar">
      <div class="direction-tabs" role="tablist" aria-label="方向">
        <button
          v-for="tab in DIRECTION_TABS"
          :key="tab.key"
          type="button"
          role="tab"
          class="direction-tab"
          :class="{ active: direction === tab.key }"
          :aria-selected="direction === tab.key"
          :data-testid="`direction-${tab.key}`"
          @click="onDirectionChange(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="toolbar-meta">
        <span v-if="fetchedAt" class="fetched-at">
          <Clock :size="14" aria-hidden="true" />
          最近更新：{{ formatDateTime(fetchedAt) }}
        </span>
        <button
          type="button"
          class="refresh-button"
          data-testid="refresh-ranking"
          :disabled="refreshing"
          @click="onRefresh"
        >
          <LoaderCircle v-if="refreshing" :size="16" class="spinner" aria-hidden="true" />
          <RefreshCw v-else :size="16" aria-hidden="true" />
          {{ refreshing ? '正在刷新…' : '刷新榜单' }}
        </button>
      </div>
    </div>

    <p v-if="engineMessage" class="setup-message">{{ engineMessage }}</p>

    <div v-if="refreshing" class="notice" role="status">
      <LoaderCircle :size="18" class="spinner" aria-hidden="true" />
      <span>正在运行 last30days 多源研究，完整结果可能需要几分钟，请耐心等待。</span>
    </div>

    <div v-if="refreshError" class="notice notice-error" role="alert">
      <CircleAlert :size="18" aria-hidden="true" />
      <span>{{ refreshError }}</span>
    </div>

    <StatePanel v-if="initialLoading" variant="skeleton" title="加载中" />

    <StatePanel
      v-else-if="loadError"
      variant="error"
      title="加载失败"
      message="无法获取榜单数据，请检查网络后重试。"
      @action="loadRanking"
    />

    <StatePanel
      v-else-if="items.length === 0"
      variant="empty"
      title="还没有榜单数据"
      :message="message || '点击“刷新榜单”生成该方向的近 30 天 Top 20。'"
      action-label="立即刷新"
      @action="onRefresh"
    />

    <template v-else>
      <div v-if="message" class="notice" role="status">
        <CircleAlert :size="18" aria-hidden="true" />
        <span>{{ message }}</span>
      </div>

      <ol class="ranking-list">
        <li v-for="(item, index) in items" :key="item.candidate_id" class="ranking-item">
          <article class="ranking-card">
            <span class="rank" aria-hidden="true">{{ index + 1 }}</span>
            <div class="ranking-main">
              <div class="ranking-title-row">
                <a
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ranking-title"
                >
                  {{ item.title }}
                  <ExternalLink :size="15" aria-hidden="true" />
                </a>
                <span class="source-chip">{{ sourceLabel(item.source) }}</span>
              </div>
              <p v-if="item.summary" class="ranking-summary">{{ item.summary }}</p>
              <div class="ranking-meta">
                <span v-if="item.published_at">{{ formatDate(item.published_at) }}</span>
                <span v-if="item.relevance_score != null">
                  相关度 {{ Math.round(item.relevance_score * 100) }}%
                </span>
              </div>
            </div>
            <div class="ranking-engagement">
              <MessageCircle :size="15" aria-hidden="true" />
              <span>{{ formatNumber(engagementTotal(item.engagement)) }} 互动</span>
            </div>
          </article>
        </li>
      </ol>
    </template>
  </main>
</template>

<script setup lang="ts">
import {
  Activity,
  CircleAlert,
  Clock,
  ExternalLink,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import {
  fetchLast30daysRankings,
  fetchLast30daysStatus,
  refreshLast30daysRankings,
} from '@/api/last30days'
import type {
  Last30DaysDirection,
  Last30DaysItem,
  Last30DaysRankingResponse,
  Last30DaysStatus,
} from '@/api/last30days'
import StatePanel from '@/components/StatePanel.vue'

const SOURCE_LABELS: Record<string, string> = {
  github: 'GitHub',
  grounding: 'Web',
  hackernews: 'Hacker News',
  polymarket: 'Polymarket',
  reddit: 'Reddit',
  tiktok: 'TikTok',
  x: 'X',
  youtube: 'YouTube',
}

const DIRECTION_TABS: { key: Last30DaysDirection; label: string }[] = [
  { key: 'agent', label: 'Agent' },
  { key: 'skill', label: 'Skill' },
]

const direction = ref<Last30DaysDirection>('agent')
const engineStatus = ref<Last30DaysStatus>('working')
const engineMessage = ref('')
const items = ref<Last30DaysItem[]>([])
const status = ref<Last30DaysStatus>('no-results')
const message = ref('')
const fetchedAt = ref('')
const initialLoading = ref(true)
const loadError = ref(false)
const refreshing = ref(false)
const refreshError = ref('')

const engineStatusLabel = computed(() => {
  if (engineStatus.value === 'unconfigured') return '需要配置'
  if (engineStatus.value === 'error') return '诊断失败'
  if (engineStatus.value === 'skipped') return '模块已停用'
  return '多源引擎就绪'
})

onMounted(async () => {
  try {
    const response = await fetchLast30daysStatus()
    engineStatus.value = response.status
    engineMessage.value = response.message ?? ''
  } catch {
    engineStatus.value = 'error'
    engineMessage.value = '暂时无法读取 last30days 引擎状态。'
  }
  await loadRanking()
})

function applyRanking(data: Last30DaysRankingResponse): void {
  status.value = data.status
  message.value = data.message ?? ''
  items.value = data.items
  fetchedAt.value = data.fetched_at
}

async function loadRanking(): Promise<void> {
  initialLoading.value = true
  loadError.value = false
  try {
    const data = await fetchLast30daysRankings(direction.value)
    applyRanking(data)
  } catch {
    loadError.value = true
  } finally {
    initialLoading.value = false
  }
}

function onDirectionChange(next: Last30DaysDirection): void {
  if (direction.value === next || refreshing.value) return
  direction.value = next
  void loadRanking()
}

async function onRefresh(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  refreshError.value = ''
  try {
    const data = await refreshLast30daysRankings(direction.value)
    if (data.status === 'error' || data.status === 'unconfigured' || data.status === 'skipped') {
      refreshError.value = data.message || '刷新失败，请稍后重试。'
    } else {
      applyRanking(data)
    }
  } catch (cause: unknown) {
    refreshError.value = cause instanceof Error ? cause.message : '刷新请求失败，请稍后重试。'
  } finally {
    refreshing.value = false
  }
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source.toLowerCase()] ?? source
}

function engagementTotal(engagement: Record<string, unknown>): number {
  return Object.values(engagement).reduce<number>((total, value) => {
    return typeof value === 'number' && Number.isFinite(value) ? total + value : total
  }, 0)
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN', { notation: 'compact' }).format(value)
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date)
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
</script>

<style scoped>
.last30days-view {
  width: min(1040px, calc(100% - 32px));
  margin: 0 auto;
  padding: 40px 0 64px;
  color: var(--color-text-primary);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-6);
}

.page-header h1 {
  margin: var(--spacing-1) 0 var(--spacing-2);
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.2;
}

.eyebrow {
  margin: 0;
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.page-description {
  max-width: 680px;
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.engine-state {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-success);
  font-size: 13px;
  font-weight: 600;
}

.engine-state.state-error,
.engine-state.state-unconfigured {
  color: var(--color-danger);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  margin-top: 32px;
}

.direction-tabs {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  overflow: hidden;
  width: fit-content;
}

.direction-tab {
  padding: 6px 14px;
  border: 0;
  background-color: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.direction-tab:hover {
  background-color: var(--color-canvas);
}

.direction-tab.active {
  background-color: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
}

.toolbar-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.fetched-at {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.refresh-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  min-height: 36px;
  padding: 0 var(--spacing-4);
  border: 1px solid var(--color-accent-emphasis);
  border-radius: var(--radius-button);
  background: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.refresh-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.setup-message {
  margin: var(--spacing-3) 0 0;
  color: var(--color-danger);
  font-size: 13px;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  margin-top: var(--spacing-4);
  padding: var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  font-size: 13px;
}

.notice-error {
  color: var(--color-danger);
}

.spinner {
  animation: spin 1s linear infinite;
  flex: 0 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  margin: var(--spacing-4) 0 0;
  padding: 0;
  list-style: none;
}

.ranking-card {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background-color: var(--color-bg);
}

.ranking-card:hover {
  border-color: var(--color-accent);
}

.rank {
  flex: 0 0 auto;
  min-width: 32px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 700;
  text-align: center;
}

.ranking-item:nth-child(-n + 3) .rank {
  color: var(--color-accent);
}

.ranking-main {
  flex: 1;
  min-width: 0;
}

.ranking-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.ranking-title {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  color: var(--color-text-primary);
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
}

.ranking-title:hover {
  color: var(--color-accent);
}

.source-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px var(--spacing-2);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 600;
}

.ranking-summary {
  margin: var(--spacing-1) 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.65;
  word-break: break-word;
}

.ranking-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-3);
  margin-top: var(--spacing-2);
  color: var(--color-text-secondary);
  font-size: 12px;
}

.ranking-engagement {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--spacing-1);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
}

.state-panel {
  margin-top: var(--spacing-4);
}

@media (max-width: 720px) {
  .last30days-view {
    width: min(100% - 24px, 1040px);
    padding-top: 28px;
  }

  .page-header,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .engine-state {
    justify-content: center;
  }

  .toolbar-meta {
    justify-content: space-between;
  }

  .ranking-card {
    flex-wrap: wrap;
  }
}
</style>
