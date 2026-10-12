<script setup lang="ts">
import { computed } from 'vue'

import type { TrendPoint } from '@/types/api'

const props = defineProps<{
  points: TrendPoint[]
}>()

const WIDTH = 96
const HEIGHT = 28
const PAD = 2

const hasData = computed(() => props.points.length > 0)

const path = computed(() => {
  if (!hasData.value) return ''
  const values = props.points.map((p) => p.stars_count)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const stepX = (WIDTH - PAD * 2) / (values.length - 1 || 1)
  return props.points
    .map((p, i) => {
      const x = PAD + i * stepX
      const y = HEIGHT - PAD - ((p.stars_count - min) / span) * (HEIGHT - PAD * 2)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const description = computed(() => {
  if (!hasData.value) return ''
  const first = props.points[0]
  const last = props.points[props.points.length - 1]
  return `${props.points.length} 个快照点，从 ${first.stars_count} 到 ${last.stars_count}`
})
</script>

<template>
  <svg
    class="sparkline"
    :width="WIDTH"
    :height="HEIGHT"
    viewBox="0 0 96 28"
    role="img"
    aria-label="30 天 Star 迷你趋势线"
  >
    <title>30 天 Star 趋势</title>
    <desc>{{ description }}</desc>
    <template v-if="hasData">
      <path :d="path" class="sparkline-line" />
      <circle
        :cx="PAD + (points.length - 1) * ((WIDTH - PAD * 2) / (points.length - 1 || 1))"
        :cy="parseFloat(path.split(' ').at(-1)?.slice(1) ?? '14')"
        r="2"
        class="sparkline-dot"
      />
    </template>
  </svg>
</template>

<style scoped>
.sparkline {
  display: block;
}

.sparkline-line {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.sparkline-dot {
  fill: var(--color-accent);
}
</style>
