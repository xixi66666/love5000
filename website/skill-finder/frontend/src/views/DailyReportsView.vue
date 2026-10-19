<!--
THESIS: 延伸日报审核页，以真实执行节点、产物和恢复操作组成制作台。
OWN-WORLD: 沿用双主题、绿色操作色，以时间线和分区工作面承载任务。
STORY: 选择日期 → 一键执行 → 查看步骤 → 补素材 → 校对成片 → 审核发布。
FIRST VIEWPORT: 日期与运行按钮在顶栏，左侧全流程，右侧当前步骤。
FORM: 在已有页面内扩展操作布局；顺序编号对应生产步骤，QQ 通知独立执行。
-->
<script setup lang="ts">
import axios from 'axios'
import TemplateEditor from '@/components/TemplateEditor.vue'
import {
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronRight,
  Circle,
  Code2,
  Play,
  RefreshCw,
} from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  dailyApi,
  dailyFile,
  sampleFile,
  type ConsoleSnapshot,
  type DailyReport,
} from '@/api/dailyReports'

const reports = ref<DailyReport[]>([])
const snapshot = ref<ConsoleSnapshot | null>(null)
const selectedDate = ref(
  new URLSearchParams(window.location.search).get('date') || '',
)
const selectedStage = ref(new URLSearchParams(window.location.search).get('stage') || '')
const followCurrent = ref(!selectedStage.value)
const panel = ref<'workflow' | 'template'>(new URLSearchParams(window.location.search).get('panel') === 'template' ? 'template' : 'workflow')
const adminKey = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const pollError = ref('')
const message = ref('')
const assetProject = ref('')
const assetSource = ref('')
const assetFile = ref<File | null>(null)
const uploadPercent = ref<number | null>(null)
const useSample = ref(false)
const loginOpen = ref(false)
const loginStatus = ref('')
const loginImage = ref('')
const loginPolling = ref(false)
const flowSidebar = ref<HTMLElement | null>(null)
const flowList = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | undefined
let loginTimer: ReturnType<typeof setInterval> | undefined
let requestId = 0
let refreshing = false
let disposed = false
let loginRequest = false
const stateLabels: Record<string, string> = {
  idle: '尚未开始',
  queued: '等待启动',
  running: '执行中',
  generating: '制作中',
  completed: '已完成',
  pending: '等待前序',
  waiting: '待你审核',
  blocked: '需要处理',
  failed: '未完成',
  skipped: '已跳过',
  untracked: '无历史记录',
  interrupted: '执行已中断',
  uncertain: '待平台核查',
  pending_review: '待你审核',
  approved: '已批准',
  rejected: '已退回',
  publishing: '正在发布',
  published: '已发布',
  publish_unknown: '待平台核查',
  ready: '已就绪',
}
const report = computed(() =>
  reports.value.find((item) => item.date === selectedDate.value),
)
const stages = computed(() => snapshot.value?.workflow.stages || [])
const stage = computed(() =>
  stages.value.find((item) => item.id === selectedStage.value),
)
const activeStage = computed(() =>
  stages.value.find((item) => item.id === snapshot.value?.workflow.current),
)
const status = computed(() => snapshot.value?.status || 'idle')
const working = computed(
  () =>
    ['generating', 'queued', 'running', 'publishing'].includes(status.value) ||
    stages.value.some(
      (item) => item.id === 'publish' && item.status === 'running',
    ),
)
const canGenerate = computed(
  () =>
    !working.value &&
    (!reports.value.some(item => item.date === snapshot.value?.today && !['failed'].includes(item.status))
      || selectedDate.value === snapshot.value?.today && status.value === 'interrupted'),
)
const dates = computed(
  () =>
    [
      ...new Set(
        [
          snapshot.value?.today,
          snapshot.value?.date,
          ...reports.value.map((item) => item.date),
        ].filter(Boolean),
      ),
    ] as string[],
)
const videoReady = computed(() =>
  snapshot.value?.artifacts.some(
    (item) => item.name === 'video.mp4' && item.ready,
  ),
)
const sample = computed(() => snapshot.value?.samples[0])
const showSample = computed(
  () => !!sample.value && (useSample.value || !videoReady.value),
)
const videoUrl = computed(() =>
  showSample.value
    ? sampleFile(sample.value!.id, 'video.mp4')
    : dailyFile(selectedDate.value, 'video.mp4'),
)
const posterUrl = computed(() =>
  showSample.value
    ? sampleFile(sample.value!.id, 'poster.png')
    : dailyFile(selectedDate.value, 'poster.png'),
)
const videoMeta = computed(() =>
  showSample.value ? sample.value : report.value?.render,
)
const currentAsset = computed(() =>
  snapshot.value?.assets.find((item) => item.project === assetProject.value),
)
const events = computed(() =>
  [...(snapshot.value?.workflow.events || [])].reverse(),
)
function label(value: string) {
  return stateLabels[value] || value
}
function time(value?: string) {
  return value
    ? new Date(value).toLocaleTimeString('zh-CN', {
        timeZone: snapshot.value?.timezone || 'Asia/Shanghai',
        hour12: false,
      })
    : '—'
}
function readableError(reason: unknown) {
  if (axios.isAxiosError(reason)) {
    const code = reason.response?.status
    if (code === 401) return '管理密钥不正确，请重新输入。'
    if (code === 403)
      return '管理操作需要 HTTPS 或本机连接，请从安全地址打开操作台。'
    if (code === 409)
      return '已有任务在运行，或本期已进入审核。请刷新状态，避免重复提交。'
    if (code === 413) return '素材超过 100 MiB，请压缩后重新上传。'
    if (code === 422)
      return '素材或参数未通过校验。请使用可播放的 MP4 或 PNG/JPEG，并填写 HTTPS 来源。'
  }
  return '请求未完成，请检查网络后重试。'
}
function authorized() {
  if (!window.isSecureContext) {
    error.value = '请通过 HTTPS 或本机连接使用管理操作。'
    return false
  }
  if (!adminKey.value) {
    error.value = '请在上方「管理连接与环境」中输入管理密钥。'
    return false
  }
  return true
}
async function refresh(force = false) {
  if (refreshing && !force) return
  const id = ++requestId
  refreshing = true
  try {
    const [consoleResult, list] = await Promise.all([
      dailyApi.get<ConsoleSnapshot>('/daily-reports/console', {
        params: selectedDate.value ? { day: selectedDate.value } : {},
      }),
      dailyApi.get<{ items: DailyReport[] }>('/daily-reports'),
    ])
    if (disposed || id !== requestId) return
    snapshot.value = consoleResult.data
    reports.value = list.data.items
    selectedDate.value = consoleResult.data.date
    if (followCurrent.value || !consoleResult.data.workflow.stages.some(item => item.id === selectedStage.value))
      selectedStage.value = consoleResult.data.workflow.current || 'collection'
    if (!assetProject.value && consoleResult.data.assets.length)
      chooseAsset(
        consoleResult.data.assets.find((item) => item.status !== 'ready')
          ?.project || consoleResult.data.assets[0].project,
      )
    pollError.value = ''
  } catch (reason) {
    if (!disposed && id === requestId) pollError.value = readableError(reason)
  } finally {
    if (!disposed && id === requestId) {
      refreshing = false
      loading.value = false
    }
  }
}
function chooseDate() {
  followCurrent.value = true
  selectedStage.value = ''
  assetProject.value = ''
  assetFile.value = null
  panel.value = 'workflow'
  loading.value = true
  void refresh(true)
}
function pickStage(id: string, follow = false) {
  selectedStage.value = id
  followCurrent.value = follow
  panel.value = 'workflow'
}
function revealStage() {
  const sidebar = flowSidebar.value
  const list = flowList.value
  const button = list?.querySelector<HTMLElement>(`[data-testid="stage-${selectedStage.value}"]`)
  if (!sidebar || !list || !button) return
  const item = button.getBoundingClientRect()
  const rail = list.getBoundingClientRect()
  if (list.scrollWidth > list.clientWidth) {
    if (item.right > rail.right) list.scrollLeft += item.right - rail.right
    else if (item.left < rail.left) list.scrollLeft -= rail.left - item.left
  }
  const area = sidebar.getBoundingClientRect()
  if (sidebar.scrollHeight > sidebar.clientHeight) {
    if (item.bottom > area.bottom) sidebar.scrollTop += item.bottom - area.bottom
    else if (item.top < area.top) sidebar.scrollTop -= area.top - item.top
  }
}
watch(selectedStage, () => { void nextTick(revealStage) })
function chooseAsset(project: string) {
  assetProject.value = project
  assetSource.value =
    snapshot.value?.assets.find((item) => item.project === project)?.source ||
    `https://github.com/${project}`
  assetFile.value = null
}
function pickedFile(event: Event) {
  assetFile.value = (event.target as HTMLInputElement).files?.[0] || null
}
async function upload() {
  if (!authorized()) return
  if (!assetFile.value) {
    error.value = '请选择要上传的项目演示素材。'
    return
  }
  if (assetFile.value.size > 100 * 1024 * 1024) {
    error.value = '素材需小于或等于 100 MiB。'
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  uploadPercent.value = 0
  try {
    await dailyApi.put(
      `/daily-reports/${selectedDate.value}/assets/${assetProject.value.split('/').map(encodeURIComponent).join('/')}`,
      assetFile.value,
      {
        params: { filename: assetFile.value.name, source: assetSource.value },
        timeout: 120000,
        headers: {
          'X-Admin-Key': adminKey.value,
          'Content-Type': 'application/octet-stream',
        },
        onUploadProgress: (event) => {
          uploadPercent.value = event.total
            ? Math.round((event.loaded / event.total) * 100)
            : null
        },
      },
    )
    message.value = '素材已校验并保存。准备齐全后，点击「重新运行今日流程」。'
    assetFile.value = null
    await refresh(true)
  } catch (reason) {
    error.value = readableError(reason)
  } finally {
    busy.value = false
    uploadPercent.value = null
  }
}
async function action(
  decision: 'generate' | 'approve' | 'reject' | 'publish' | 'notify',
) {
  if (!authorized()) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const path =
      decision === 'generate'
        ? '/daily-reports/generate'
        : ['approve', 'reject'].includes(decision)
          ? `/daily-reports/${selectedDate.value}/review`
          : `/daily-reports/${selectedDate.value}/${decision}`
    const body = ['approve', 'reject'].includes(decision)
      ? { decision, expected_digest: report.value?.review_digest }
      : {}
    const { data } = await dailyApi.post(path, body, {
      headers: { 'X-Admin-Key': adminKey.value },
    })
    if (decision === 'generate') {
      selectedDate.value = data.date
      selectedStage.value = 'collection'
      message.value = '今日流程已提交，状态会自动更新。'
    } else if (decision === 'approve')
      message.value =
        '已批准当前视频及文案，并提交发布任务；未登录时会等待账号就绪。'
    else if (decision === 'reject') message.value = '当前版本已退回，不会发布。'
    else message.value = '任务已提交，请查看对应环节的执行记录。'
    await refresh(true)
  } catch (reason) {
    error.value = readableError(reason)
  } finally {
    busy.value = false
  }
}
async function pollLogin() {
  if (loginRequest || disposed) return
  loginRequest = true
  try {
    const headers = { 'X-Admin-Key': adminKey.value }
    const { data } = await dailyApi.get('/daily-reports/publisher/login', {
      headers,
    })
    if (disposed) return
    const messages: Record<string, string> = {
      starting: '正在打开抖音登录页…',
      scan_required: '请用手机抖音扫描下方二维码。',
      ready: '登录态已保存。发布仍需当前版本的人工批准。',
      timed_out: '二维码已超时，请重新获取。',
      browser_or_network_unavailable:
        '登录页未能打开，请检查浏览器环境和网络后重试。',
      not_started: '正在启动登录页面…',
    }
    loginStatus.value = messages[data.status] || '等待登录状态更新。'
    if (data.status === 'scan_required') {
      const screen = await dailyApi.get(
        '/daily-reports/publisher/login/screen',
        { headers, responseType: 'blob' },
      )
      if (disposed) return
      if (loginImage.value) URL.revokeObjectURL(loginImage.value)
      loginImage.value = URL.createObjectURL(screen.data)
    }
    if (
      ['ready', 'timed_out', 'browser_or_network_unavailable'].includes(
        data.status,
      )
    ) {
      if (loginTimer) clearInterval(loginTimer)
      loginPolling.value = false
      if (loginImage.value) {
        URL.revokeObjectURL(loginImage.value)
        loginImage.value = ''
      }
      await refresh(true)
    }
  } catch (reason) {
    error.value = readableError(reason)
    if (loginTimer) clearInterval(loginTimer)
    loginPolling.value = false
  } finally {
    loginRequest = false
  }
}
async function openLogin() {
  if (!authorized()) return
  busy.value = true
  error.value = ''
  try {
    await dailyApi.post(
      '/daily-reports/publisher/login',
      {},
      { headers: { 'X-Admin-Key': adminKey.value } },
    )
    loginOpen.value = true
    loginPolling.value = true
    loginStatus.value = '正在获取登录页面…'
    if (loginImage.value) {
      URL.revokeObjectURL(loginImage.value)
      loginImage.value = ''
    }
    if (loginTimer) clearInterval(loginTimer)
    loginTimer = setInterval(() => {
      void pollLogin()
    }, 3000)
    await pollLogin()
  } catch (reason) {
    error.value = readableError(reason)
    loginPolling.value = false
  } finally {
    busy.value = false
  }
}
onMounted(() => {
  void refresh().then(() => nextTick(revealStage))
  pollTimer = setInterval(() => {
    if (!document.hidden) void refresh()
  }, 5000)
})
onUnmounted(() => {
  disposed = true
  ++requestId
  if (pollTimer) clearInterval(pollTimer)
  if (loginTimer) clearInterval(loginTimer)
  if (loginImage.value) URL.revokeObjectURL(loginImage.value)
  adminKey.value = ''
})
</script>

<template>
  <div class="console-page">
    <header class="console-heading">
      <div>
        <p class="context-label">Skill Finder / 内容制作</p>
        <h1>制作操作台</h1>
        <p class="heading-copy">从发现项目到发布成片，每一步都有迹可循。</p>
      </div>
      <div class="heading-controls">
        <label class="date-control">制作日期<select
          v-model="selectedDate"
          aria-label="制作日期"
          @change="chooseDate"
        >
          <option v-if="!dates.length" value="">今天</option>
          <option v-for="day in dates" :key="day" :value="day">
            {{ day }}{{ day === snapshot?.today ? ' · 今天' : '' }}
          </option>
        </select></label>
        <button
          class="primary run-button"
          type="button"
          :disabled="busy || !canGenerate || loading"
          data-testid="run-workflow"
          @click="action('generate')"
        >
          <Play :size="16" aria-hidden="true" />{{
            working
              ? '流程正在执行'
              : status === 'failed' || status === 'interrupted'
                ? '重新运行今日流程'
                : '一键运行今日流程'
          }}
        </button>
      </div>
    </header>
    <details class="connection">
      <summary>
        <span>管理连接与环境</span><span class="secondary">{{ adminKey ? '密钥仅保存在本页内存' : '输入密钥后可执行管理操作'
        }}<ChevronRight :size="15" aria-hidden="true" /></span>
      </summary>
      <div class="connection-body">
        <div>
          <label for="review-key">管理密钥</label><input
            id="review-key"
            v-model="adminKey"
            type="password"
            autocomplete="off"
            placeholder="本地私有配置中的 ADMIN_KEY"
          />
          <p class="help">
            密钥不会写入浏览器存储。配音密钥通过后端私有配置提供。
          </p>
        </div>
        <dl class="environment">
          <div v-for="item in snapshot?.runtime || []" :key="item.id">
            <dt>{{ item.label }}</dt>
            <dd :class="{ missing: !item.ready && !item.optional }">
              <span class="env-dot" :class="{ ready: item.ready }"></span>{{ item.value
              }}<span v-if="!item.ready && !item.optional"> · 待配置</span>
            </dd>
          </div>
        </dl>
      </div>
    </details>
    <p v-if="loading && !snapshot" class="notice" role="status">
      正在读取流程和产物…
    </p>
    <p v-if="pollError" class="notice danger" role="alert">
      {{ pollError
      }}<button type="button" @click="refresh(true)">重新连接</button>
    </p>
    <p v-if="error" class="notice danger" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <template v-if="snapshot">
      <section class="run-summary" aria-label="当前执行状态">
        <span class="state-indicator" :class="status"></span>
        <div>
          <strong>{{ label(status) }}</strong>
          <p>
            {{ activeStage?.label || '准备开始'
            }}<span v-if="activeStage?.detail">
              · {{ activeStage.detail }}</span>
          </p>
        </div>
        <div class="summary-end">
          <span>{{ snapshot.timezone }} ·
            {{ time(snapshot.workflow.updated_at) }}</span><button
            class="icon-button"
            type="button"
            aria-label="刷新流程状态"
            @click="refresh(true)"
          >
            <RefreshCw :size="17" aria-hidden="true" />
          </button>
        </div>
      </section>
      <div class="workspace">
        <aside ref="flowSidebar" class="flow-sidebar" aria-label="制作流程">
          <div class="sidebar-heading">
            <h2>全流程</h2>
            <span>点击查看环节</span>
          </div>
          <label class="follow-toggle"><input v-model="followCurrent" type="checkbox" @change="followCurrent && activeStage && pickStage(activeStage.id, true)" />跟随当前环节</label>
          <ol ref="flowList" class="flow-list">
            <li
              v-for="(item, index) in stages"
              :key="item.id"
              :class="{ optional: item.id === 'notify' }"
            >
              <button
                type="button"
                class="stage-button"
                :class="[
                  item.status,
                  {
                    selected: selectedStage === item.id && panel === 'workflow',
                  },
                ]"
                :aria-pressed="
                  selectedStage === item.id && panel === 'workflow'
                "
                :aria-current="
                  snapshot.workflow.current === item.id ? 'step' : undefined
                "
                :data-testid="`stage-${item.id}`"
                @click="pickStage(item.id)"
              >
                <span class="step-marker"><Check
                  v-if="item.status === 'completed'"
                  :size="15"
                  aria-hidden="true"
                /><span v-else>{{
                  String(index + 1).padStart(2, '0')
                }}</span></span><span class="step-name">{{ item.label
                }}<small>{{ label(item.status)
                }}<span v-if="item.total">
                  · {{ item.done }}/{{ item.total }}</span></small></span><ChevronRight
                  :size="14"
                  class="step-arrow"
                  aria-hidden="true"
                />
              </button>
            </li>
          </ol>
          <button
            type="button"
            class="template-nav"
            :aria-pressed="panel === 'template'"
            @click="panel = 'template'"
          >
            <Code2 :size="17" aria-hidden="true" />模板编辑<ArrowUpRight
              :size="15"
              aria-hidden="true"
            />
          </button>
          <p class="sidebar-note">
            每 5 秒同步真实状态。QQ 通知可在成片就绪后独立执行。
          </p>
        </aside>
        <section class="work-surface" :aria-labelledby="panel === 'template' ? 'template-editor-title' : 'stage-title'">
          <KeepAlive>
            <TemplateEditor v-if="panel === 'template'" v-model:admin-key="adminKey" />
          </KeepAlive>
          <template v-if="panel === 'workflow' && stage">
            <header class="surface-heading">
              <div>
                <p class="secondary">
                  {{ selectedDate
                  }}<span v-if="stage.total">
                    · 已完成 {{ stage.done }} / {{ stage.total }} 段</span>
                </p>
                <h2 id="stage-title">{{ stage.label }}</h2>
              </div>
              <span class="status-tag" :class="stage.status">{{
                label(stage.status)
              }}</span>
            </header>
            <p class="body-copy">{{ stage.description }}</p>
            <p
              v-if="stage.detail"
              class="stage-detail"
              :class="{
                danger: ['failed', 'interrupted', 'uncertain'].includes(
                  stage.status,
                ),
              }"
            >
              {{ stage.detail
              }}<span v-if="stage.error" class="error-code">{{
                stage.error
              }}</span>
            </p>
            <dl v-if="stage.started_at" class="timing">
              <div>
                <dt>开始</dt>
                <dd>{{ time(stage.started_at) }}</dd>
              </div>
              <div v-if="stage.finished_at">
                <dt>结束</dt>
                <dd>{{ time(stage.finished_at) }}</dd>
              </div>
            </dl>
            <p v-if="!snapshot.recorded && report" class="help">
              该历史日报未记录逐步执行日志，操作台不会据此补造进度。
            </p>
            <template v-if="['collection', 'selection'].includes(stage.id)">
              <div class="section-heading">
                <h3>
                  本期项目
                  <span class="secondary">{{ report?.items.length || 0 }}</span>
                </h3>
                <button
                  v-if="activeStage && selectedStage !== activeStage.id"
                  type="button"
                  class="text-button"
                  @click="selectedStage = activeStage.id"
                >
                  查看当前环节<ChevronRight :size="14" aria-hidden="true" />
                </button>
              </div>
              <div v-if="report?.items.length" class="project-list">
                <a
                  v-for="item in report.items"
                  :key="item.full_name"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                ><span class="rank">{{
                  String(item.rank).padStart(2, '0')
                }}</span><span><strong>{{ item.full_name }}</strong>
                  <p>{{ item.summary }}</p></span><span class="growth">+{{ item.daily_stars.toLocaleString() }} ★</span></a>
              </div>
              <div v-else class="empty-work">
                <Circle :size="26" aria-hidden="true" />
                <h3>{{ working ? '正在准备当天项目' : '还没有本期项目' }}</h3>
                <p>
                  输入管理密钥后，一键运行今日流程。榜单采集、筛选和脚本编排会依次执行。
                </p>
              </div>
              <p
                v-if="report?.completeness === 'insufficient_ai_projects'"
                class="help"
              >
                本期只有
                {{ report.item_count }} 个符合范围的项目，未补入旧数据。
              </p>
            </template>
            <template v-if="stage.id === 'script'">
              <h3>口播脚本</h3>
              <div class="script-text">
                {{ report?.script || '脚本生成后会显示在这里。' }}
              </div>
              <h3>发布文案</h3>
              <p class="caption-copy">
                {{ report?.caption || '等待脚本编排。' }}
              </p>
            </template>
            <template v-if="stage.id === 'assets'">
              <p class="help">
                上传真实演示录屏或项目截图，并注明来源。MP4 / PNG /
                JPEG，单个不超过 100
                MiB。已生成成片使用固化副本，不会因素材库更新而改变。
              </p>
              <ul class="asset-list">
                <li v-for="item in snapshot.assets" :key="item.project">
                  <button
                    type="button"
                    :aria-pressed="assetProject === item.project"
                    @click="chooseAsset(item.project)"
                  >
                    <span>{{ item.project }}</span><span
                      :class="item.status === 'ready' ? 'success' : 'danger'"
                    >{{
                      item.status === 'ready'
                        ? '已备齐'
                        : item.status === 'invalid'
                          ? '需更换素材'
                          : '缺少素材'
                    }}</span>
                  </button>
                </li>
              </ul>
              <form
                v-if="snapshot.assets.length"
                class="asset-form"
                @submit.prevent="upload"
              >
                <h3>补充项目素材</h3>
                <label for="asset-project">对应项目</label><select
                  id="asset-project"
                  :value="assetProject"
                  @change="
                    chooseAsset(($event.target as HTMLSelectElement).value)
                  "
                >
                  <option
                    v-for="item in snapshot.assets"
                    :key="item.project"
                    :value="item.project"
                  >
                    {{ item.project }}
                  </option>
                </select><label for="asset-source">素材来源链接</label><input
                  id="asset-source"
                  v-model="assetSource"
                  type="url"
                  required
                  placeholder="https://github.com/owner/repo"
                /><label for="asset-file">演示文件</label><input
                  id="asset-file"
                  :key="assetProject"
                  type="file"
                  accept="video/mp4,image/png,image/jpeg"
                  :disabled="busy || working"
                  @change="pickedFile"
                />
                <p v-if="currentAsset?.filename" class="help">
                  当前素材：{{ currentAsset.filename }}
                </p>
                <button
                  type="submit"
                  class="primary"
                  :disabled="busy || working || !assetFile"
                >
                  {{
                    busy
                      ? uploadPercent !== null
                        ? `正在上传 ${uploadPercent}%`
                        : '正在校验…'
                      : '校验并保存素材'
                  }}
                </button>
              </form>
              <p v-else class="empty-copy">
                项目筛选完成后，这里会逐项列出素材准备情况。
              </p>
            </template>
            <template v-if="stage.id === 'voice' || stage.id === 'captions'">
              <div v-if="stage.total" class="segment-progress">
                <progress
                  :value="stage.done"
                  :max="stage.total"
                  :aria-label="`${stage.label}已完成段数`"
                ></progress><span>{{ stage.done }} / {{ stage.total }} 段</span>
              </div>
              <audio
                v-if="
                  snapshot.artifacts.some(
                    (item) => item.name === 'audio.m4a' && item.ready,
                  )
                "
                :src="dailyFile(selectedDate, 'audio.m4a')"
                controls
                preload="metadata"
                aria-label="本期中文配音"
              ></audio>
              <p v-else class="empty-copy">
                {{
                  stage.id === 'voice'
                    ? '完整音轨生成后，可在这里试听。'
                    : '字幕采用实际音轨的意群边界，文字以口播原稿校正。成片就绪后可下载 SRT 检查。'
                }}
              </p>
              <h3>对照原稿</h3>
              <div class="script-text">
                {{ report?.script || '等待脚本生成。' }}
              </div>
            </template>
            <template v-if="stage.id === 'render' || stage.id === 'review'">
              <div
                v-if="
                  snapshot.render_progress &&
                    stage.id === 'render' &&
                    stage.status === 'running'
                "
                class="render-meter"
              >
                <span>{{
                  snapshot.render_progress.phase === 'bundling'
                    ? '正在打包模板'
                    : '正在渲染画面与编码'
                }}</span><strong v-if="snapshot.render_progress.total_frames">{{ snapshot.render_progress.rendered_frames }} /
                  {{ snapshot.render_progress.total_frames }} 帧</strong><progress
                  v-if="snapshot.render_progress.total_frames"
                  :value="snapshot.render_progress.rendered_frames"
                  :max="snapshot.render_progress.total_frames"
                  aria-label="实际已渲染帧数"
                ></progress>
              </div>
              <div class="preview-toolbar">
                <h3>视频预览</h3>
                <div v-if="sample">
                  <button
                    type="button"
                    :aria-pressed="!showSample"
                    :disabled="!videoReady"
                    @click="useSample = false"
                  >
                    本期成片
                  </button><button
                    type="button"
                    :aria-pressed="showSample"
                    @click="useSample = true"
                  >
                    接入样片
                  </button>
                </div>
              </div>
              <div v-if="videoReady || sample" class="preview-grid">
                <div>
                  <video
                    :key="videoUrl"
                    :src="videoUrl"
                    :poster="posterUrl"
                    controls
                    playsinline
                    preload="metadata"
                    :aria-label="
                      showSample ? 'Remotion 接入样片' : '本期成片预览'
                    "
                  ></video>
                  <p v-if="showSample" class="sample-note">
                    Remotion 能力样片 · 非本期日榜
                  </p>
                </div>
                <div class="preview-notes">
                  <h3>
                    {{ showSample ? '先验收画面与声音' : '校对当前版本' }}
                  </h3>
                  <p>
                    {{
                      showSample
                        ? '样片演示本地模板、MiMo 配音和字幕对齐，不创建发布任务。'
                        : '核对项目来源、口播、字幕及发布文案。批准只绑定你当前看到的版本。'
                    }}
                  </p>
                  <dl v-if="videoMeta" class="media-spec">
                    <div>
                      <dt>画面</dt>
                      <dd>{{ videoMeta.width }} × {{ videoMeta.height }}</dd>
                    </div>
                    <div>
                      <dt>帧率</dt>
                      <dd>{{ videoMeta.fps }} FPS</dd>
                    </div>
                    <div>
                      <dt>时长</dt>
                      <dd>{{ videoMeta.duration_seconds.toFixed(1) }} 秒</dd>
                    </div>
                  </dl>
                  <template v-if="!showSample">
                    <h3>口播</h3>
                    <div class="script-text compact">{{ report?.script }}</div>
                    <h3>发布文案</h3>
                    <p class="caption-copy">{{ report?.caption }}</p>
                  </template>
                </div>
              </div>
              <div v-else class="empty-work">
                <Play :size="26" aria-hidden="true" />
                <h3>等待成片</h3>
                <p>
                  素材、配音和字幕就绪后，Remotion
                  开始渲染。完成后可在这里预览。
                </p>
              </div>
              <div v-if="stage.id === 'review'" class="review-actions">
                <p v-if="status === 'pending_review'">
                  请先完整查看本期成片。以下批准会提交抖音发布任务。
                </p>
                <button
                  v-if="status === 'pending_review'"
                  type="button"
                  class="primary"
                  :disabled="busy || showSample || !videoReady"
                  data-testid="approve-video"
                  @click="action('approve')"
                >
                  批准当前视频及文案并提交发布
                </button><button
                  v-if="status === 'pending_review'"
                  type="button"
                  :disabled="busy"
                  @click="action('reject')"
                >
                  退回，不发布
                </button>
                <p v-if="showSample" class="help">
                  接入样片不能作为本期日报批准。
                </p>
              </div>
            </template>
            <template v-if="stage.id === 'publish'">
              <div class="publish-actions">
                <button
                  type="button"
                  :disabled="busy || working || loginPolling"
                  @click="openLogin"
                >
                  {{
                    loginPolling
                      ? '等待扫码登录…'
                      : loginOpen
                        ? '重新获取登录二维码'
                        : '登录抖音（扫码）'
                  }}
                </button><button
                  v-if="status === 'approved'"
                  type="button"
                  class="primary"
                  :disabled="busy || working"
                  @click="action('publish')"
                >
                  登录就绪后重试发布
                </button>
              </div>
              <p class="help">
                上传前再次核验批准摘要。提交结果不确定时，请先在抖音作品管理中确认；操作台不会自动重复发布。
              </p>
              <div v-if="loginOpen" class="login-screen">
                <p role="status">{{ loginStatus }}</p>
                <img
                  v-if="loginImage"
                  :src="loginImage"
                  alt="抖音创作者后台登录二维码，请用手机抖音扫码"
                />
              </div>
            </template>
            <template v-if="stage.id === 'notify'">
              <h3>QQ 日报通知</h3>
              <p class="body-copy">
                发送日报链接，方便回到操作台查看成片和审核。消息送达与抖音发布分别记录。
              </p>
              <button
                type="button"
                :disabled="
                  busy ||
                    !snapshot.runtime.find((item) => item.id === 'notify')
                      ?.ready ||
                    !['pending_review', 'approved', 'published'].includes(
                      status,
                    ) ||
                    report?.qq_status === 'sent'
                "
                @click="action('notify')"
              >
                {{
                  report?.qq_status === 'sent'
                    ? '本期通知已送达'
                    : '发送本期日报链接'
                }}
              </button>
              <p
                v-if="
                  !snapshot.runtime.find((item) => item.id === 'notify')?.ready
                "
                class="help"
              >
                当前未配置 QQ 接入口，视频流程可继续使用。
              </p>
            </template>
          </template>
          <section class="artifacts" aria-label="本期产物">
            <h3>本期产物</h3>
            <div>
              <template v-for="item in snapshot.artifacts" :key="item.name">
                <a
                  v-if="item.ready"
                  :href="dailyFile(selectedDate, item.name)"
                  download
                ><ArrowDownToLine :size="14" aria-hidden="true" />{{
                  item.label
                }}</a><span v-else class="artifact-pending">{{ item.label }}<small>待生成</small></span>
              </template>
            </div>
          </section>
          <details class="event-log">
            <summary>
              执行记录 <span>{{ events.length }} 条</span>
            </summary>
            <ol v-if="events.length">
              <li v-for="(event, index) in events" :key="index">
                <time :datetime="event.at">{{ time(event.at) }}</time><span>{{
                  stages.find((item) => item.id === event.stage)?.label
                }}</span>
                <p>{{ event.message }}</p>
                <small>{{ label(event.status) }}</small>
              </li>
            </ol>
            <p v-else class="help">
              任务开始后会记录环节变化。历史任务不会补造日志。
            </p>
          </details>
        </section>
      </div>
    </template>
  </div>
</template>
<style scoped src="@/assets/styles/daily-console.css"></style>
