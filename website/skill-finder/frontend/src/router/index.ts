import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'
import RepositoryDetailView from '@/views/RepositoryDetailView.vue'
import Last30DaysView from '@/views/Last30DaysView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/repositories/:owner/:name', name: 'repository-detail', component: RepositoryDetailView },
    { path: '/last30days', name: 'last30days', component: Last30DaysView },
  ],
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' }
    }
    return { top: 0 }
  },
})

export default router
