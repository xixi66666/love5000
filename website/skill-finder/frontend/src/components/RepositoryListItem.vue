<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'
import { computed } from 'vue'

import SparklineChart from '@/components/SparklineChart.vue'
import type { RepositoryListItem as Repo } from '@/types/api'
import { handleCoverError, repoFallbackCoverUrl, repoOgCoverUrl } from '@/utils/covers'

const props = defineProps<{
  repo: Repo
  rank?: number
}>()

const CATEGORY_COLORS: Record<string, string> = {
  AGENT: 'var(--color-accent)',
  SKILL: 'var(--color-success)',
  MCP: 'var(--color-danger)',
  PLUGIN: 'var(--color-plugin)',
}

const LANGUAGE_COLORS: Record<string, string> = {
  Python: 'var(--lang-python)',
  TypeScript: 'var(--lang-typescript)',
  JavaScript: 'var(--lang-javascript)',
  Go: 'var(--lang-go)',
  Rust: 'var(--lang-rust)',
}

const coverUrl = computed(() => repoOgCoverUrl(props.repo.owner, props.repo.name))
const coverFallback = computed(() => repoFallbackCoverUrl(props.repo.owner, props.repo.name))

function onCoverError(event: Event) {
  handleCoverError(event, coverFallback.value)
}

const rankLabel = computed(() =>
  props.rank == null ? '' : String(props.rank).padStart(2, '0'),
)

function languageColor(language: string | null): string {
  if (!language) return 'var(--lang-default)'
  return LANGUAGE_COLORS[language] ?? 'var(--lang-default)'
}

function formatStars(value: number): string {
  return value.toLocaleString('en-US')
}

function formatGrowth(value: number | null): string {
  return value == null ? '--' : formatSigned(value)
}

function formatSigned(value: number): string {
  return value > 0 ? `+${value.toLocaleString('en-US')}` : value.toLocaleString('en-US')
}

function growthClass(value: number | null): string {
  if (value == null) return 'is-flat'
  return value > 0 ? 'is-up' : value < 0 ? 'is-down' : 'is-flat'
}

function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? 'var(--color-text-secondary)'
}
</script>

<template>
  <article class="repo-card" data-testid="repo-item">
    <div class="repo-media">
      <img
        class="repo-media-img"
        :src="coverUrl"
        alt=""
        loading="lazy"
        decoding="async"
        @error="onCoverError"
      />
      <div class="repo-media-shade" aria-hidden="true"></div>
      <div class="repo-media-top">
        <span v-if="rankLabel" class="repo-rank">{{ rankLabel }}</span>
        <span
          v-for="cat in repo.categories"
          :key="cat"
          class="repo-category"
          :style="{ color: categoryColor(cat) }"
        >
          {{ cat }}
        </span>
      </div>
    </div>

    <div class="repo-body">
      <div class="repo-title-row">
        <RouterLink
          :to="`/repositories/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}`"
          class="repo-name"
          :data-testid="`repo-link-${repo.name}`"
        >
          {{ repo.owner }}/{{ repo.name }}
        </RouterLink>
      </div>
      <p class="repo-description">{{ repo.description }}</p>
      <div class="repo-meta">
        <span
          v-for="topic in repo.topics.slice(0, 4)"
          :key="topic"
          class="repo-topic"
          data-testid="topic"
        >
          {{ topic }}
        </span>
        <span class="repo-language" data-testid="language">
          <span class="language-dot" :style="{ backgroundColor: languageColor(repo.language) }"></span>
          {{ repo.language }}
        </span>
        <span class="repo-stars">{{ formatStars(repo.stars_count) }} stars</span>
      </div>
    </div>

    <div class="repo-growth">
      <div class="growth-metric">
        <span class="growth-label">今日</span>
        <span class="growth-value" :class="growthClass(repo.daily_stars)">{{ formatGrowth(repo.daily_stars) }}</span>
      </div>
      <div class="growth-metric">
        <span class="growth-label">7 日</span>
        <span class="growth-value" :class="growthClass(repo.weekly_stars)">{{ formatGrowth(repo.weekly_stars) }}</span>
      </div>
      <div class="growth-metric">
        <span class="growth-label">30 日</span>
        <span class="growth-value" :class="growthClass(repo.monthly_stars)">{{ formatGrowth(repo.monthly_stars) }}</span>
      </div>
      <SparklineChart :points="repo.trend" />
      <a
        :href="repo.html_url"
        class="repo-external"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="`在 GitHub 上打开 ${repo.owner}/${repo.name}`"
        data-testid="external-link"
      >
        <ExternalLink :size="15" aria-hidden="true" />
      </a>
    </div>
  </article>
</template>

<style scoped>
.repo-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-canvas);
  overflow: hidden;
  transition: border-color 400ms ease, transform 500ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 500ms ease;
}

.repo-card:hover {
  border-color: var(--color-border-strong);
  transform: translateY(-5px);
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.35);
}

.repo-media {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: linear-gradient(150deg, var(--surface-glass-strong), var(--color-canvas-subtle));
}

.repo-media-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: grayscale(0.3) contrast(1.05) brightness(0.88) saturate(0.95);
  transform: scale(1.01);
  transition: transform 900ms cubic-bezier(0.22, 1, 0.36, 1), filter 700ms ease;
}

.repo-card:hover .repo-media-img {
  transform: scale(1.06);
  filter: grayscale(0.05) contrast(1.04) brightness(0.96) saturate(1.05);
}

[data-theme='dark'] .repo-media-img {
  filter: grayscale(0.32) contrast(1.02) brightness(0.72) saturate(0.9);
}

[data-theme='dark'] .repo-card:hover .repo-media-img {
  filter: grayscale(0.08) contrast(1.02) brightness(0.86) saturate(1);
}

[data-theme='dark'] .repo-media-shade {
  background: linear-gradient(180deg, rgba(5, 8, 11, 0.5) 0%, rgba(5, 8, 11, 0.12) 42%, rgba(5, 8, 11, 0.7) 100%);
}

.repo-media-shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(5, 8, 11, 0.42) 0%, transparent 42%, rgba(5, 8, 11, 0.62) 100%);
}

[data-theme='light'] .repo-media-shade {
  background: linear-gradient(180deg, rgba(20, 22, 18, 0.3) 0%, transparent 46%, rgba(20, 22, 18, 0.42) 100%);
}

.repo-media-top {
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.repo-rank {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.85);
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

.repo-category {
  padding: 3px 10px;
  border: 1px solid currentColor;
  border-radius: 999px;
  background: rgba(7, 9, 12, 0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.repo-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 18px 12px;
}

.repo-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.repo-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 200ms ease;
}

.repo-name:hover {
  color: var(--color-accent);
}

.repo-description {
  min-height: 40px;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.55;
  word-break: break-word;
}

.repo-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.repo-topic {
  padding: 2px 9px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-secondary);
  font-size: 10px;
  font-weight: 600;
  transition: border-color 200ms ease, color 200ms ease;
}

.repo-card:hover .repo-topic {
  border-color: var(--color-border-strong);
}

.repo-language {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.language-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.repo-stars {
  color: var(--color-text-muted);
  font-size: 11px;
}

.repo-growth {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: auto;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--color-border);
}

.growth-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 46px;
}

.growth-label {
  color: var(--color-text-muted);
  font-size: 10px;
  letter-spacing: 0.04em;
}

.growth-value {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
}

.growth-value.is-up {
  color: var(--color-accent);
}

.growth-value.is-down {
  color: var(--color-danger);
}

.growth-value.is-flat {
  color: var(--color-text-muted);
}

.repo-external {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-left: auto;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  color: var(--color-text-secondary);
  transition: border-color 200ms ease, color 200ms ease, transform 200ms ease;
}

.repo-external:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
  transform: translateY(-2px);
}

@media (max-width: 640px) {
  .repo-growth {
    flex-wrap: wrap;
    gap: 12px;
  }
}
</style>
