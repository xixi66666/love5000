<script setup lang="ts">
import { computed } from 'vue'

import type { TrendPoint } from '@/types/api'

const props = defineProps<{
  points: TrendPoint[]
}>()

const WIDTH = 720
const HEIGHT = 240
const PAD = { top: 16, right: 16, bottom: 28, left: 44 }

const hasData = computed(() => props.points.length > 0)

const yMax = computed(() => Math.max(...props.points.map((p) => p.stars_count)))
const yMin = computed(() => Math.min(...props.points.map((p) => p.stars_count)))

const range = computed(() => {
  const span = yMax.value - yMin.value
  return { min: yMin.value - span * 0.08, max: yMax.value + span * 0.08, span: span * 1.16 || 1 }
})

function xFor(index: number): number {
  const n = props.points.length
  if (n <= 1) return PAD.left + (WIDTH - PAD.left - PAD.right) / 2
  return PAD.left + (index / (n - 1)) * (WIDTH - PAD.left - PAD.right)
}

function yFor(value: number): number {
  return HEIGHT - PAD.bottom - ((value - range.value.min) / range.value.span) * (HEIGHT - PAD.top - PAD.bottom)
}

const linePath = computed(() =>
  props.points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${xFor(i).toFixed(1)},${yFor(p.stars_count).toFixed(1)}`)
    .join(' '),
)

const gridLines = computed(() => {
  const steps = 4
  const lines: { y: number; label: string }[] = []
  for (let i = 0; i <= steps; i++) {
    const value = range.value.min + (range.value.span * i) / steps
    lines.push({ y: yFor(value), label: Math.round(value).toLocaleString('en-US') })
  }
  return lines
})

const summary = computed(() => {
  if (!hasData.value) return ''
  const first = props.points[0]
  const last = props.points[props.points.length - 1]
  return `${props.points.length} 个快照点，从 ${first.stars_count} 到 ${last.stars_count}`
})
</script>

<template>
  <svg
    v-if="hasData"
    class="trend-chart"
    data-testid="trend-chart"
    :width="WIDTH"
    :height="HEIGHT"
    :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
    role="img"
    aria-label="最近 30 天 Star 趋势图"
  >
    <title>最近 30 天 Star 趋势</title>
    <desc>{{ summary }}</desc>
    <g class="grid">
      <g v-for="line in gridLines" :key="line.y">
        <line :x1="PAD.left" :y1="line.y" :x2="WIDTH - PAD.right" :y2="line.y" class="grid-line" />
        <text :x="PAD.left - 6" :y="line.y + 4" class="grid-label" text-anchor="end">{{ line.label }}</text>
      </g>
    </g>
    <template v-if="points.length === 1">
      <circle
        :cx="xFor(0)"
        :cy="yFor(points[0].stars_count)"
        r="3"
        class="trend-dot"
      />
    </template>
    <template v-else>
      <path :d="linePath" class="trend-line" />
      <g
        v-for="(point, i) in points"
        :key="`${point.snapshot_date}-${i}`"
      >
        <circle
          :cx="xFor(i)"
          :cy="yFor(point.stars_count)"
          r="2.5"
          class="trend-point"
        >
          <title>{{ point.snapshot_date }}: {{ point.stars_count.toLocaleString('en-US') }} stars</title>
        </circle>
      </g>
    </template>
  </svg>
  <div v-else data-testid="no-trend" class="no-trend">暂无趋势数据</div>
</template>

<style scoped>
.trend-chart {
  display: block;
  width: 100%;
  height: auto;
}

.grid-line {
  stroke: var(--color-border);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.grid-label {
  fill: var(--color-text-muted);
  font-size: 11px;
}

.trend-line {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-point {
  fill: var(--color-bg);
  stroke: var(--color-accent);
  stroke-width: 1.5;
}

.trend-dot {
  fill: var(--color-accent);
}

.no-trend {
  padding: var(--spacing-6);
  text-align: center;
  color: var(--color-text-secondary);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-card);
}
</style>
