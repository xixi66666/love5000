import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { SortKey } from '@/types/api'

export interface FilterState {
  sort: SortKey
  category: string
  language: string
  minStars: number | null
  q: string
}

const STORAGE_KEY = 'skill-finder:preferences'
const THEME_KEY = 'skill-finder:theme'

function loadPreferences(): FilterState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultFilters()
    const parsed = JSON.parse(raw) as Partial<FilterState>
    return { ...defaultFilters(), ...parsed }
  } catch {
    return defaultFilters()
  }
}

function defaultFilters(): FilterState {
  return {
    sort: 'daily_stars',
    category: '',
    language: '',
    minStars: null,
    q: '',
  }
}

function loadTheme(): string {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const usePreferencesStore = defineStore('preferences', () => {
  const filters = ref<FilterState>(loadPreferences())
  const theme = ref<string>(loadTheme())

  const activeFilters = computed(() => ({
    ...filters.value,
  }))

  function setFilters(partial: Partial<FilterState>) {
    filters.value = { ...filters.value, ...partial }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters.value))
    } catch {
      /* storage unavailable */
    }
  }

  function resetFilters() {
    setFilters(defaultFilters())
  }

  function setTheme(next: string) {
    theme.value = next
    document.documentElement.setAttribute('data-theme', next)
    try {
      localStorage.setItem(THEME_KEY, next)
    } catch {
      /* storage unavailable */
    }
  }

  return { filters, theme, activeFilters, setFilters, resetFilters, setTheme }
})
