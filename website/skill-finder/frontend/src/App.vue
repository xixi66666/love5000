<script setup lang="ts">
import { onMounted } from 'vue'

import AppFooter from '@/components/AppFooter.vue'
import AppHeader from '@/components/AppHeader.vue'
import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()

onMounted(() => {
  document.documentElement.setAttribute('data-theme', preferences.theme)
})
</script>

<template>
  <div class="app-shell">
    <div class="app-ambient" aria-hidden="true">
      <div class="ambient-glow ambient-glow-a"></div>
      <div class="ambient-glow ambient-glow-b"></div>
      <div class="ambient-grid"></div>
    </div>
    <AppHeader />
    <main class="app-main">
      <RouterView />
    </main>
    <AppFooter />
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: clip;
  background-color: var(--color-bg);
}

.app-ambient {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.ambient-glow {
  position: absolute;
  width: 54vw;
  height: 54vw;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.5;
}

.ambient-glow-a {
  top: -22vw;
  left: -14vw;
  background: radial-gradient(circle, var(--color-glow), transparent 68%);
}

.ambient-glow-b {
  right: -20vw;
  top: 26vh;
  background: radial-gradient(circle, rgba(120, 160, 220, 0.2), transparent 70%);
}

.ambient-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(var(--color-border) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-border) 1px, transparent 1px);
  background-size: 96px 96px;
  opacity: 0.16;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 20%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 20%, transparent 78%);
}

[data-theme='light'] .ambient-glow-b {
  background: radial-gradient(circle, rgba(150, 170, 110, 0.28), transparent 70%);
}

.app-main {
  position: relative;
  z-index: 1;
  flex: 1;
  width: 100%;
}
</style>
