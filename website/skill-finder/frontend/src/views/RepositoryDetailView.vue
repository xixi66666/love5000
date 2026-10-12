<script setup lang="ts">
import { ArrowLeft, ExternalLink } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fromAxiosError } from '@/api/client'
import { fetchRepositoryDetail } from '@/api/repositories'
import StatePanel from '@/components/StatePanel.vue'
import type { RepositoryDetail } from '@/types/api'

const route = useRoute()
const router = useRouter()

const detail = ref<RepositoryDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref(false)

let controller: AbortController | null = null

function formatStars(value: number): string {
  return value.toLocaleString('en-US')
}

function formatSigned(value: number | null): string {
  if (value == null) return '--'
  return value > 0 ? `+${value.toLocaleString('en-US')}` : value.toLocaleString('en-US')
}

async function loadDetail() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  notFound.value = false
  error.value = false
  const owner = String(route.params.owner)
  const name = String(route.params.name)
  try {
    detail.value = await fetchRepositoryDetail(owner, name, controller.signal)
  } catch (err) {
    const apiError = fromAxiosError(err)
    if (apiError.cancelled) return
    if (apiError.status === 404) {
      notFound.value = true
    } else {
      error.value = true
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)
onUnmounted(() => controller?.abort())
</script>

<template>
  <div class="detail-page">
    <button type="button" class="back-button" data-testid="back" @click="router.back()">
      <ArrowLeft :size="16" aria-hidden="true" />
      返回排行榜
    </button>

    <StatePanel v-if="loading" variant="skeleton" title="加载中" />

    <section v-else-if="notFound" class="detail-not-found" data-testid="not-found">
      <h1>仓库不存在</h1>
      <p>该仓库不存在或已不可用。</p>
      <RouterLink to="/">返回排行榜</RouterLink>
    </section>

    <StatePanel
      v-else-if="error"
      variant="error"
      title="加载失败"
      message="无法获取仓库详情，请重试。"
      @action="loadDetail"
    />

    <template v-else-if="detail">
      <header class="detail-header">
        <h1 class="detail-name">{{ detail.owner }}/{{ detail.name }}</h1>
        <p class="detail-description">{{ detail.description }}</p>
        <div class="detail-meta">
          <span class="detail-language">
            <span class="language-dot"></span>{{ detail.language }}
          </span>
          <span class="detail-stat"><strong>{{ formatStars(detail.stars_count) }}</strong> stars</span>
          <span class="detail-stat"><strong>{{ formatStars(detail.forks_count) }}</strong> forks</span>
          <span class="detail-stat"><strong>{{ formatStars(detail.open_issues_count) }}</strong> issues</span>
          <span class="growth-value" data-testid="growth">
            今日 {{ formatSigned(detail.daily_stars) }} · 7 日
            {{ formatSigned(detail.weekly_stars) }} · 30 日
            {{ formatSigned(detail.monthly_stars) }}
          </span>
        </div>
        <a
          :href="detail.html_url"
          class="github-link"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="在 GitHub 上打开该仓库"
        >
          <ExternalLink :size="16" aria-hidden="true" />
          访问 GitHub
        </a>
      </header>

      <section v-if="detail.introduction" class="detail-section" data-testid="introduction">
        <h2 class="section-title">项目介绍</h2>
        <div class="introduction-card">
          <div class="intro-block">
            <h3 class="intro-subtitle">简介</h3>
            <p class="intro-text">{{ detail.introduction.introduction }}</p>
          </div>
          <div v-if="detail.introduction.highlights.length > 0" class="intro-block">
            <h3 class="intro-subtitle">核心功能</h3>
            <ul class="intro-list" data-testid="highlights">
              <li v-for="item in detail.introduction.highlights" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div v-if="detail.introduction.requirements.length > 0" class="intro-block">
            <h3 class="intro-subtitle">环境要求</h3>
            <ul class="intro-list" data-testid="requirements">
              <li v-for="item in detail.introduction.requirements" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div v-if="detail.introduction.usage" class="intro-block">
            <h3 class="intro-subtitle">如何使用</h3>
            <p class="intro-text intro-usage" data-testid="usage">{{ detail.introduction.usage }}</p>
          </div>
          <div v-if="detail.introduction.audience" class="intro-block">
            <h3 class="intro-subtitle">适合人群</h3>
            <p class="intro-text">{{ detail.introduction.audience }}</p>
          </div>
          <div v-if="detail.introduction.domains.length > 0" class="intro-block">
            <h3 class="intro-subtitle">应用领域</h3>
            <div class="domains-list">
              <span v-for="domain in detail.introduction.domains" :key="domain" class="domain-chip">
                {{ domain }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="detail-section" data-testid="introduction-missing">
        <h2 class="section-title">项目介绍</h2>
        <div class="introduction-card intro-placeholder">
          <p class="intro-text">介绍生成中：采集任务会自动为项目生成中文介绍，稍后刷新页面试试。</p>
        </div>
      </section>

      <section class="detail-section">
        <h2 class="section-title">分类依据</h2>
        <div class="rules-list">
          <code v-for="rule in detail.matched_rules" :key="rule" class="rule-chip">{{ rule }}</code>
          <span v-if="detail.matched_rules.length === 0" class="muted">无命中规则</span>
        </div>
      </section>

      <section class="detail-section">
        <h2 class="section-title">Topics</h2>
        <div class="topics-list">
          <span v-for="topic in detail.topics" :key="topic" class="topic-chip" data-testid="topic">
            {{ topic }}
          </span>
          <span v-if="detail.topics.length === 0" class="muted">无 Topics</span>
        </div>
      </section>

      <section class="detail-section">
        <h2 class="section-title">详细信息</h2>
        <dl class="detail-list">
          <div class="detail-row">
            <dt>主页</dt>
            <dd>
              <a v-if="detail.homepage" :href="detail.homepage" target="_blank" rel="noopener noreferrer">
                {{ detail.homepage }}
              </a>
              <span v-else class="muted">无</span>
            </dd>
          </div>
          <div class="detail-row">
            <dt>创建时间</dt>
            <dd>{{ detail.github_created_at }}</dd>
          </div>
          <div class="detail-row">
            <dt>最后同步</dt>
            <dd>{{ detail.last_synced_at }}</dd>
          </div>
          <div class="detail-row">
            <dt>7 日增长</dt>
            <dd>{{ formatSigned(detail.weekly_stars) }}</dd>
          </div>
          <div class="detail-row">
            <dt>30 日增长</dt>
            <dd>{{ formatSigned(detail.monthly_stars) }}</dd>
          </div>
        </dl>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
  max-width: 880px;
  margin: 0 auto;
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: 6px 12px;
  width: fit-content;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background-color: transparent;
  color: var(--color-text-primary);
  font-size: 13px;
}

.back-button:hover {
  background-color: var(--color-canvas);
}

.detail-not-found {
  padding: var(--spacing-6);
  text-align: center;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--color-border);
}

.detail-name {
  font-size: 24px;
  font-weight: 600;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.detail-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  word-break: break-word;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-4);
  font-size: 13px;
  color: var(--color-text-secondary);
}

.detail-language {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
}

.language-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--lang-python);
}

.detail-stat strong {
  color: var(--color-text-primary);
}

.growth-value {
  color: var(--color-success);
  font-family: var(--font-mono);
}

.github-link {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  width: fit-content;
  padding: 6px 12px;
  border-radius: var(--radius-button);
  background-color: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
}

.github-link:hover {
  text-decoration: none;
  opacity: 0.9;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
}

.chart-card {
  padding: var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background-color: var(--color-bg);
  overflow-x: auto;
}

.introduction-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background-color: var(--color-bg);
}

.intro-block {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.intro-subtitle {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.intro-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-primary);
  word-break: break-word;
  overflow-wrap: anywhere;
}

.intro-usage {
  white-space: pre-wrap;
}

.intro-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-primary);
}

.intro-placeholder {
  border-style: dashed;
  color: var(--color-text-secondary);
}

.domains-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.domain-chip {
  padding: 2px 10px;
  border-radius: 100px;
  background-color: var(--color-canvas);
  color: var(--color-accent);
  font-size: 12px;
}

.rules-list,
.topics-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.rule-chip {
  padding: 2px 8px;
  border-radius: 4px;
  background-color: var(--color-canvas);
  font-size: 12px;
}

.topic-chip {
  padding: 2px 10px;
  border-radius: 100px;
  background-color: var(--color-canvas);
  color: var(--color-accent);
  font-size: 12px;
}

.muted {
  color: var(--color-text-secondary);
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.detail-row {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--color-border);
}

.detail-row dt {
  width: 100px;
  flex-shrink: 0;
  color: var(--color-text-secondary);
}

.detail-row dd {
  margin: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
}
</style>
