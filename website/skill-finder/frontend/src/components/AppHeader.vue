<script setup lang="ts">
import { Moon, Search, Sun } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()
const route = useRoute()
const router = useRouter()

const isDark = computed(() => preferences.theme === 'dark')
const searchText = ref(typeof route.query.q === 'string' ? route.query.q : '')
const scrolled = ref(false)

let searchTimer: ReturnType<typeof setTimeout> | null = null

function toggleTheme() {
  preferences.setTheme(isDark.value ? 'light' : 'dark')
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const query = { ...route.query }
    if (searchText.value) {
      query.q = searchText.value
    } else {
      delete query.q
    }
    if (route.name !== 'home') {
      void router.push({ name: 'home', query })
    } else {
      void router.replace({ query })
    }
  }, 300)
}

function onScroll() {
  scrolled.value = window.scrollY > 24
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <header class="site-nav" :class="{ 'is-scrolled': scrolled }">
    <div class="site-nav-inner">
      <RouterLink to="/" class="brand" aria-label="Skill Finder 首页">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">Skill Finder</span>
      </RouterLink>

      <nav class="primary-nav" aria-label="主导航">
        <RouterLink to="/" class="nav-link">榜单</RouterLink>
        <RouterLink to="/last30days" class="nav-link">近 30 天最热</RouterLink>
        <RouterLink to="/daily-reports" class="nav-link">日报与视频</RouterLink>
      </nav>

      <div class="search-box">
        <Search :size="15" class="search-icon" aria-hidden="true" />
        <input
          v-model="searchText"
          type="search"
          class="search-input"
          placeholder="搜索仓库"
          aria-label="搜索仓库"
          data-testid="global-search"
          @input="onSearchInput"
        />
      </div>

      <button
        class="theme-toggle"
        type="button"
        :aria-label="isDark ? '切换到亮色主题' : '切换到暗色主题'"
        :title="isDark ? '切换到亮色主题' : '切换到暗色主题'"
        data-testid="theme-toggle"
        @click="toggleTheme"
      >
        <Sun v-if="isDark" :size="16" aria-hidden="true" />
        <Moon v-else :size="16" aria-hidden="true" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.site-nav {
  position: fixed;
  top: 14px;
  left: 50%;
  z-index: 60;
  width: min(1200px, calc(100% - 24px));
  transform: translateX(-50%);
}

.site-nav-inner {
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 60px;
  padding: 0 12px 0 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-button);
  background: var(--surface-glass);
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
  transition: background 320ms ease, border-color 320ms ease, box-shadow 320ms ease;
}

.site-nav.is-scrolled .site-nav-inner {
  border-color: var(--color-border-strong);
  background: var(--color-header);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.34);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  font-size: 15px;
  font-weight: 900;
  letter-spacing: -0.01em;
}

.brand-mark {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--color-accent);
  box-shadow: 0 0 16px var(--color-glow);
}

.primary-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0 16px;
  border-radius: var(--radius-button);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
  transition: color 200ms ease, background 200ms ease;
}

.nav-link:hover {
  color: var(--color-text-primary);
  background: var(--surface-glass-strong);
}

.nav-link.router-link-active {
  color: var(--color-text-primary);
  background: var(--surface-glass-strong);
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 0;
  max-width: 380px;
  margin-left: auto;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  min-height: 40px;
  padding: 0 16px 0 38px;
  border: 1px solid transparent;
  border-radius: var(--radius-button);
  background: var(--surface-glass-strong);
  color: var(--color-text-primary);
  font-size: 13px;
  transition: border-color 220ms ease, background 220ms ease;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.search-input:focus {
  outline: none;
  border-color: var(--color-accent);
  background: var(--surface-glass);
}

.theme-toggle {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-primary);
  transition: border-color 200ms ease, background 200ms ease, transform 200ms ease;
}

.theme-toggle:hover {
  border-color: var(--color-accent);
  transform: rotate(12deg);
}

@media (max-width: 860px) {
  .site-nav {
    top: 10px;
  }

  .site-nav-inner {
    flex-wrap: wrap;
    padding: 10px 12px;
    gap: 10px;
    border-radius: 26px;
  }

  .brand {
    order: 1;
  }

  .theme-toggle {
    order: 2;
    margin-left: auto;
  }

  .primary-nav {
    order: 3;
    width: 100%;
  }

  .nav-link {
    flex: 1;
    justify-content: center;
  }

  .search-box {
    order: 4;
    flex-basis: 100%;
    max-width: none;
    margin-left: 0;
  }
}
</style>
