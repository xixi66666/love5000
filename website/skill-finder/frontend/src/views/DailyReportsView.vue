<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'

interface Project {
  rank: number
  full_name: string
  url: string
  summary: string
  daily_stars: number
}
interface Report {
  date: string
  title?: string
  status: string
  publisher_status?: string
  qq_status?: string
  script?: string
  caption?: string
  review_digest?: string
  items: Project[]
  item_count?: number
  completeness?: string
  error?: string
}
const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1' })
const reports = ref<Report[]>([])
const selectedDate = ref(new URLSearchParams(location.search).get('date') || '')
const adminKey = ref('')
const busy = ref(false)
const loading = ref(true)
const message = ref('')
const error = ref('')
const qqConfigured = ref(false)
const loginOpen = ref(false)
const loginStatus = ref('')
const loginImage = ref('')
const report = computed(() => reports.value.find((item) => item.date === selectedDate.value))
let interval: ReturnType<typeof setInterval> | undefined
let loginInterval: ReturnType<typeof setInterval> | undefined
const labels: Record<string, string> = {
  generating: '正在生成', pending_review: '等待你审核', approved: '已批准', rejected: '已退回',
  publishing: '正在提交抖音', published: '已发布', publish_unknown: '请到抖音确认发布结果', failed: '生成失败',
}
function file(name: string) {
  return `${api.defaults.baseURL}/daily-reports/${selectedDate.value}/files/${name}`
}
function readableError(reason: unknown) {
  if (axios.isAxiosError(reason)) {
    if (reason.response?.status === 401) return '审核密钥不正确，请重新输入。'
    if (reason.response?.status === 403) return '管理操作仅通过安全连接开放，请使用 HTTPS 或 SSH 隧道。'
    if (reason.response?.status === 409) return '任务正在执行或内容已变化，请刷新后再审核。'
  }
  return '请求没有完成，请检查网络并重试。'
}
async function pollLogin() {
  try {
    const headers = { 'X-Admin-Key': adminKey.value }
    const { data } = await api.get('/daily-reports/publisher/login', { headers })
    const messages: Record<string, string> = {
      starting: '正在打开抖音登录页…', scan_required: '请用手机抖音扫描下方登录页中的二维码。',
      ready: '抖音登录已保存。仍需逐份批准视频，才会发布。',
      timed_out: '二维码已超时，请重新打开登录页面。',
      browser_or_network_unavailable: '登录页面未能打开，请检查服务器浏览器和网络。',
      not_started: '正在排队打开登录页面…',
    }
    loginStatus.value = messages[data.status] || data.status
    if (['ready', 'timed_out', 'browser_or_network_unavailable'].includes(data.status)) {
      if (loginInterval) clearInterval(loginInterval)
      return
    }
    if (data.status === 'scan_required') {
      const screen = await api.get('/daily-reports/publisher/login/screen', { headers, responseType: 'blob' })
      if (loginImage.value) URL.revokeObjectURL(loginImage.value)
      loginImage.value = URL.createObjectURL(screen.data)
    }
  } catch (reason) { error.value = readableError(reason) }
}
async function openLogin() {
  if (!window.isSecureContext) { error.value = '请使用 HTTPS 打开登录配置。'; return }
  if (!adminKey.value) { error.value = '请先输入审核密钥。'; return }
  busy.value = true
  try {
    await api.post('/daily-reports/publisher/login', {}, { headers: { 'X-Admin-Key': adminKey.value } })
    loginOpen.value = true
    loginStatus.value = '正在打开抖音登录页面…'
    if (loginInterval) clearInterval(loginInterval)
    loginInterval = setInterval(() => { void pollLogin() }, 3000)
  } catch (reason) { error.value = readableError(reason) }
  finally { busy.value = false }
}
async function refresh() {
  try {
    const { data } = await api.get('/daily-reports')
    reports.value = data.items
    qqConfigured.value = data.qq_configured
    if (!selectedDate.value) selectedDate.value = reports.value[0]?.date || ''
  } catch (reason) {
    error.value = readableError(reason)
  } finally {
    loading.value = false
  }
}
async function action(decision: 'approve' | 'reject' | 'generate' | 'publish') {
  if (!window.isSecureContext) {
    error.value = '请通过 HTTPS 或本机 SSH 隧道打开审核页，避免在明文连接中发送密钥。'
    return
  }
  if (!adminKey.value) { error.value = '请输入审核密钥。'; return }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const path = decision === 'generate' ? '/daily-reports/generate'
      : decision === 'publish' ? `/daily-reports/${selectedDate.value}/publish`
        : `/daily-reports/${selectedDate.value}/review`
    const body = ['approve', 'reject'].includes(decision)
      ? { decision, expected_digest: report.value?.review_digest } : {}
    await api.post(path, body, { headers: { 'X-Admin-Key': adminKey.value } })
    message.value = decision === 'approve'
      ? '已记录你对当前视频及文案的批准；抖音未登录时保留在待发布队列。'
      : decision === 'reject' ? '已退回，视频不会发布。' : '任务已提交，请稍后查看状态。'
    await refresh()
  } catch (reason) {
    error.value = readableError(reason)
  } finally {
    busy.value = false
  }
}
onMounted(() => { void refresh(); interval = setInterval(() => { void refresh() }, 15000) })
onUnmounted(() => {
  if (interval) clearInterval(interval)
  if (loginInterval) clearInterval(loginInterval)
  if (loginImage.value) URL.revokeObjectURL(loginImage.value)
})
</script>

<template>
  <div class="daily-page">
    <header class="daily-intro">
      <p class="edition">每天 08:00 · 北京时间</p>
      <h1>今天的开源灵感，<br />先看，再发布。</h1>
      <p class="intro-copy">AI 项目日榜、中文口播与竖屏视频。每一份成品，都由你决定是否发布。</p>
    </header>
    <p v-if="loading" role="status">正在读取日报…</p>
    <p v-if="error" class="feedback error" role="alert">{{ error }}</p>
    <p v-if="message" class="feedback" role="status">{{ message }}</p>
    <div class="daily-workspace">
      <aside class="editions" aria-label="日报日期">
        <h2>日报存档</h2>
        <button
          v-for="item in reports" :key="item.date" type="button"
          :aria-pressed="selectedDate === item.date" @click="selectedDate = item.date"
        >
          <span>{{ item.date }}</span><small>{{ labels[item.status] || item.status }}</small>
        </button>
        <p v-if="!loading && !reports.length" class="muted">还没有日报。可手动生成第一份，之后由服务器每天自动制作。</p>
        <p class="delivery">QQ：{{ qqConfigured ? '已配置接入口' : '暂未配置' }}</p>
      </aside>
      <section class="review" aria-labelledby="review-title">
        <template v-if="report">
          <div class="report-heading">
            <div><p class="edition">{{ report.date }}</p><h2 id="review-title">{{ report.title || '今日日报' }}</h2></div>
            <span class="status">{{ labels[report.status] || report.status }}</span>
          </div>
          <p v-if="report.completeness === 'insufficient_ai_projects'" class="feedback">
            今日符合范围的项目只有 {{ report.item_count }} 个，未补入旧数据。
          </p>
          <p v-if="report.status === 'generating'" class="feedback" role="status">正在采集、配音和合成视频，完成后本页会自动更新。</p>
          <p v-else-if="report.status === 'failed'" class="feedback error">生成未完成，请检查服务器任务日志后重新生成。</p>
          <div v-else class="preview-grid">
            <div class="video-column">
              <video :key="report.date" :src="file('video.mp4')" :poster="file('poster.png')" controls preload="metadata" playsinline aria-label="日报视频预览"></video>
              <div class="downloads">
                <a :href="file('video.mp4')" download>下载视频</a>
                <a :href="file('audio.m4a')">中文配音</a>
                <a :href="file('subtitles.srt')">字幕</a>
                <a :href="file('report.md')">文字日报</a>
              </div>
            </div>
            <div class="script-column">
              <h3>校对口播</h3><p class="muted">视频由第十名倒数至第一名；热度采用当天日榜新增 Star。</p>
              <div class="script-text">{{ report.script }}</div>
              <h3 class="caption-title">抖音发布文案</h3>
              <p class="caption-text">{{ report.caption }}</p>
            </div>
          </div>
          <section v-if="report.items.length" class="sources" aria-label="项目来源">
            <h3>回到项目本身</h3>
            <a v-for="item in report.items" :key="item.full_name" :href="item.url" target="_blank" rel="noopener noreferrer">
              <span class="rank">{{ String(item.rank).padStart(2, '0') }}</span>
              <span><strong>{{ item.full_name }}</strong><small>{{ item.summary }}</small></span>
              <span class="growth">+{{ item.daily_stars.toLocaleString() }} ★</span>
            </a>
          </section>
        </template>
        <h2 v-else id="review-title">准备你的第一份日报</h2>
        <section class="approval" aria-labelledby="approval-title">
          <h3 id="approval-title">发布审核</h3>
          <p>只有明确批准的当前版本才会进入发布任务。密钥仅在本页内存中使用。</p>
          <p v-if="report?.publisher_status === 'awaiting_login'" class="muted">抖音：等待创作者账号登录。批准不会跳过账号登录。</p>
          <p v-if="report?.publisher_status === 'login_or_ui_required'" class="feedback error">抖音登录可能已过期，或创作者后台页面已变化。请检查账号和上传页面后再重试。</p>
          <p v-if="report?.publisher_status === 'verify_manually'" class="feedback error">提交后的结果尚未确认。请先到抖音作品管理核查，系统不会自动重复发布。</p>
          <label for="review-key">审核密钥</label>
          <input id="review-key" v-model="adminKey" type="password" autocomplete="off" placeholder="输入服务器私有审核密钥" />
          <div class="review-actions">
            <button type="button" :disabled="busy" @click="openLogin">登录抖音（扫码）</button>
            <template v-if="report?.status === 'pending_review'">
              <button type="button" class="primary" :disabled="busy" @click="action('approve')">批准当前视频并提交发布任务</button>
              <button type="button" :disabled="busy" @click="action('reject')">退回，不发布</button>
            </template>
            <button v-if="report?.status === 'approved'" type="button" class="primary" :disabled="busy" @click="action('publish')">登录就绪后重试发布</button>
            <button v-if="!report || report.status === 'failed'" type="button" class="primary" :disabled="busy" @click="action('generate')">{{ busy ? '正在提交…' : '采集并生成今日视频' }}</button>
          </div>
          <div v-if="loginOpen" class="login-screen">
            <p role="status">{{ loginStatus }}</p>
            <img v-if="loginImage" :src="loginImage" alt="抖音创作者后台登录页面，请用手机抖音扫码" />
          </div>
        </section>
      </section>
    </div>
  </div>
</template>

<style scoped>
.daily-page { max-width: 1440px; margin: auto; padding: 156px 5vw 96px; }
.daily-intro { margin-bottom: 64px; }
.edition { color: var(--color-accent); margin-bottom: 12px; font-size: 14px; }
h1 { font-size: clamp(32px, 4.5vw, 64px); line-height: 1.2; font-weight: 600; letter-spacing: -.025em; }
.intro-copy { color: var(--color-text-secondary); font-size: 17px; margin-top: 22px; max-width: 65ch; }
.daily-workspace { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 42px; }
h2 { font-size: 22px; line-height: 1.4; } h3 { font-size: 18px; margin-bottom: 12px; }
.editions button { width: 100%; text-align: left; display: grid; gap: 5px; margin-top: 12px; border: 1px solid var(--color-border); }
button, .downloads a { border: 1px solid var(--color-border-strong); border-radius: 8px; background: var(--color-canvas); color: var(--color-text-primary); padding: 12px 16px; min-height: 44px; font-size: 14px; }
button:hover, .downloads a:hover { border-color: var(--color-accent); }
button[aria-pressed='true'] { border-color: var(--color-accent); color: var(--color-accent); }
button:disabled { opacity: .5; cursor: wait; }
small, .muted, .delivery { color: var(--color-text-secondary); }
.delivery { margin-top: 28px; font-size: 13px; }
.report-heading { display: flex; justify-content: space-between; gap: 18px; align-items: start; margin-bottom: 30px; flex-wrap: wrap; }
.status { color: var(--color-accent); border: 1px solid var(--color-border-strong); padding: 6px 12px; border-radius: 999px; white-space: nowrap; }
.preview-grid { display: grid; grid-template-columns: minmax(220px, 340px) minmax(0, 1fr); gap: 32px; }
video { width: 100%; aspect-ratio: 9/16; background: #07090c; border-radius: 12px; }
.downloads { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.downloads a { display: inline-flex; align-items: center; font-size: 13px; }
.script-text { white-space: pre-wrap; max-height: 610px; overflow-y: auto; line-height: 1.9; margin-top: 24px; padding-right: 16px; }
.caption-title { margin-top: 32px; }
.caption-text { white-space: pre-wrap; line-height: 1.8; overflow-wrap: anywhere; }
.sources { margin-top: 56px; }
.sources > a { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 16px; padding: 22px 0; border-bottom: 1px solid var(--color-border); }
.sources strong, .sources small { display: block; overflow-wrap: anywhere; }
.sources small { margin-top: 8px; line-height: 1.7; }
.rank, .growth { color: var(--color-accent); font-variant-numeric: tabular-nums; }
.growth { white-space: nowrap; }
.approval { margin-top: 56px; padding-top: 32px; border-top: 1px solid var(--color-border); }
.approval p { max-width: 65ch; margin-bottom: 18px; line-height: 1.7; }
label { display: block; margin-bottom: 8px; }
input { width: min(100%, 420px); padding: 13px; min-height: 46px; border: 1px solid var(--color-border-strong); border-radius: 8px; color: var(--color-text-primary); background: var(--color-canvas); }
input::placeholder { color: var(--color-text-secondary); }
.review-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
.login-screen { margin-top: 24px; }
.login-screen img { width: 100%; max-width: 1000px; border-radius: 12px; }
.primary { background: var(--color-accent); color: var(--color-accent-ink); border-color: var(--color-accent); }
.feedback { padding: 18px 0; color: var(--color-accent); line-height: 1.7; }
.error { color: var(--color-danger); }
@media (max-width: 1000px) { .daily-workspace { grid-template-columns: 1fr; } .editions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; } .editions button { width: auto; margin: 0; } .delivery { margin: 0; } }
@media (max-width: 860px) { .daily-page { padding-top: 220px; } }
@media (max-width: 680px) { .daily-intro { margin-bottom: 42px; } .preview-grid { grid-template-columns: 1fr; } video { max-height: 68vh; } .sources > a { grid-template-columns: 24px minmax(0, 1fr); } .growth { grid-column: 2; } .script-text { max-height: 350px; } }
</style>
