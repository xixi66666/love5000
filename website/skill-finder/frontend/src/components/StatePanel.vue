<script setup lang="ts">
import { AlertTriangle, Inbox, RotateCw } from 'lucide-vue-next'

defineProps<{
  variant: 'skeleton' | 'empty' | 'error'
  title: string
  message?: string
  actionLabel?: string
}>()

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <section
    v-if="variant === 'skeleton'"
    class="state-panel"
    data-testid="skeleton"
    aria-busy="true"
    aria-label="正在加载"
  >
    <div v-for="n in 6" :key="n" class="skeleton-card">
      <div class="skeleton-media"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line is-short"></div>
    </div>
  </section>

  <section
    v-else
    class="state-panel state-centered"
    :data-testid="`${variant}-state`"
  >
    <span class="state-icon-wrap" aria-hidden="true">
      <Inbox v-if="variant === 'empty'" :size="26" />
      <AlertTriangle v-else :size="26" />
    </span>
    <h2 class="state-title">{{ title }}</h2>
    <p v-if="message" class="state-message">{{ message }}</p>
    <button
      v-if="variant === 'empty' || variant === 'error'"
      type="button"
      class="state-action"
      :data-testid="variant === 'empty' ? 'reset-filters' : 'retry'"
      @click="emit('action')"
    >
      <RotateCw :size="14" aria-hidden="true" />
      {{ actionLabel ?? (variant === 'empty' ? '清空筛选条件' : '重试') }}
    </button>
  </section>
</template>

<style scoped>
.state-panel {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  grid-auto-flow: dense;
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-canvas);
}

.skeleton-media {
  aspect-ratio: 16 / 9;
  border-radius: calc(var(--radius-card) - 8px);
  background: var(--color-skeleton);
  animation: pulse 1.3s ease-in-out infinite;
}

.skeleton-line {
  height: 14px;
  border-radius: 999px;
  background: var(--color-skeleton);
  animation: pulse 1.3s ease-in-out infinite;
}

.skeleton-line.is-short {
  width: 56%;
}

.state-centered {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 320px;
  padding: 56px 24px;
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-card);
  text-align: center;
  color: var(--color-text-secondary);
}

.state-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin-bottom: 6px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--surface-glass);
  color: var(--color-accent);
}

.state-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
}

.state-message {
  max-width: 420px;
  font-size: 13px;
}

.state-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  min-height: 44px;
  padding: 0 22px;
  border: 0;
  border-radius: var(--radius-button);
  background: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
  font-size: 13px;
  font-weight: 700;
  transition: transform 200ms ease;
}

.state-action:hover {
  transform: translateY(-2px);
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
</style>
