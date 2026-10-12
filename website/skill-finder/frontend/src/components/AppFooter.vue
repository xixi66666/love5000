<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
</script>

<template>
  <footer class="site-footer">
    <div class="footer-inner">
      <section class="footer-cta">
        <p class="footer-eyebrow">KEEP THE SIGNAL</p>
        <h2 class="footer-title">
          让下一次浪潮
          <em>先抵达你</em>
        </h2>
        <div class="footer-actions">
          <RouterLink class="footer-action-primary" :to="{ name: 'home', hash: '#trending' }">
            浏览今日榜单
            <ArrowUpRight :size="18" aria-hidden="true" />
          </RouterLink>
          <RouterLink class="footer-action-ghost" to="/last30days">近 30 天最热</RouterLink>
        </div>
      </section>
      <div class="footer-meta">
        <div class="footer-brand">
          <span class="brand-mark" aria-hidden="true"></span>
          <span>Skill Finder</span>
        </div>
        <nav class="footer-links" aria-label="页脚导航">
          <RouterLink to="/">榜单</RouterLink>
          <RouterLink to="/last30days">近 30 天最热</RouterLink>
          <a href="https://github.com/trending" target="_blank" rel="noopener noreferrer">
            数据来源 GitHub Trending
          </a>
        </nav>
        <p class="footer-note">每日采集 · 真实 Star 增量 · love5000 微服务</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.site-footer {
  position: relative;
  z-index: 1;
  padding: 96px 24px 40px;
}

.footer-inner {
  width: min(1200px, 100%);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 96px;
}

.footer-cta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 24px;
  padding: clamp(32px, 6vw, 72px);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--radius-card) + 10px);
  background: linear-gradient(140deg, var(--surface-glass-strong), transparent 58%),
    var(--color-canvas);
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.28);
}

.footer-eyebrow {
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.22em;
}

.footer-title {
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 5vw, 4.2rem);
  font-weight: 900;
  line-height: 1.04;
  letter-spacing: -0.03em;
}

.footer-title em {
  display: block;
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  color: var(--color-accent);
}

.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.footer-action-primary,
.footer-action-ghost {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
  padding: 0 26px;
  border-radius: var(--radius-button);
  font-size: 15px;
  font-weight: 700;
  transition: transform 240ms ease, background 240ms ease, border-color 240ms ease;
}

.footer-action-primary {
  background: var(--color-accent-emphasis);
  color: var(--color-accent-ink);
}

.footer-action-primary:hover {
  transform: translateY(-2px);
}

.footer-action-ghost {
  border: 1px solid var(--color-border-strong);
  background: var(--surface-glass);
  color: var(--color-text-primary);
}

.footer-action-ghost:hover {
  border-color: var(--color-accent);
  transform: translateY(-2px);
}

.footer-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding-top: 28px;
  border-top: 1px solid var(--color-border);
}

.footer-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
}

.brand-mark {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-accent);
  box-shadow: 0 0 18px var(--color-glow);
}

.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 22px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.footer-links a:hover {
  color: var(--color-accent);
}

.footer-note {
  color: var(--color-text-muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .site-footer {
    padding: 72px 16px 32px;
  }

  .footer-inner {
    gap: 64px;
  }

  .footer-meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
