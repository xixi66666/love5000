<!-- Operate：同一工作面完成源码编辑、样式调整、真实预览与版本启用，草稿始终独立于成片。 -->
<script setup lang="ts">
import axios from 'axios'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Code2, Play, RotateCcw, Save } from 'lucide-vue-next'
import { dailyApi } from '@/api/dailyReports'
import type {
  CompileDiagnostic,
  TemplateDocument,
  TemplatePreview,
  TemplateTheme,
} from '@/api/templates'

const adminKey = defineModel<string>('adminKey', { default: '' })
const document = ref<TemplateDocument | null>(null)
const sources = ref<Record<string, string>>({})
const theme = ref<TemplateTheme | null>(null)
const selectedFile = ref('src/video.tsx')
const mode = ref<'source' | 'style'>('source')
const composition = ref('SkillFinderDaily')
const preview = ref<TemplatePreview | null>(null)
const iframe = ref<HTMLIFrameElement | null>(null)
const sourceArea = ref<HTMLTextAreaElement | null>(null)
const busy = ref(false)
const status = ref('')
const error = ref('')
const diagnostics = ref<CompileDiagnostic[]>([])
const compiledSources = ref('')
const restoreRevision = ref('')
const runtimeFailed = ref(false)
let disposed = false
const endpoint = '/daily-reports/template'
const currentFile = computed(() =>
  document.value?.sources.find((file) => file.path === selectedFile.value),
)
const sourceText = computed({
  get: () => sources.value[selectedFile.value] || '',
  set: (value) => {
    sources.value[selectedFile.value] = value
  },
})
const dirty = computed(
  () =>
    !!document.value &&
    (JSON.stringify(theme.value) !== JSON.stringify(document.value.theme) ||
      document.value.sources.some(
        (file) => file.editable && sources.value[file.path] !== file.code,
      )),
)
const previewStale = computed(
  () =>
    !!preview.value && compiledSources.value !== JSON.stringify(sources.value),
)
const previewUrl = computed(() =>
  preview.value
    ? new URL(
        `${dailyApi.defaults.baseURL}${endpoint}/previews/${preview.value.id}/index.html`,
        window.location.origin,
      ).href
    : '',
)
const lines = computed(() =>
  sourceText.value
    .split('\n')
    .map((_, index) => index + 1)
    .join('\n'),
)
const headers = () => ({ 'X-Admin-Key': adminKey.value })
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

function authorized() {
  if (!window.isSecureContext) {
    error.value = '请通过 HTTPS 或本机连接编辑模板。'
    return false
  }
  if (!adminKey.value) {
    error.value = '请输入管理密钥以连接模板编辑器。'
    return false
  }
  return true
}
function applyDocument(value: TemplateDocument) {
  document.value = value
  theme.value = clone(value.theme)
  sources.value = Object.fromEntries(
    value.sources.map((file) => [file.path, file.code]),
  )
  if (!value.sources.some((file) => file.path === selectedFile.value))
    selectedFile.value = value.sources[0].path
  diagnostics.value = []
  restoreRevision.value = ''
}
function body() {
  return {
    expected_revision: document.value!.revision,
    theme: clone(theme.value),
    sources: Object.fromEntries(
      document
        .value!.sources.filter((file) => file.editable)
        .map((file) => [file.path, sources.value[file.path]]),
    ),
  }
}
function failure(reason: unknown) {
  status.value = '检查未完成，草稿尚未启用。'
  diagnostics.value = []
  if (axios.isAxiosError(reason)) {
    const data = reason.response?.data as
      { diagnostics?: CompileDiagnostic[] } | undefined
    if (data?.diagnostics) {
      diagnostics.value = data.diagnostics
      error.value = '模板未通过编译，请按下方文件与行号修改。'
      return
    }
    if (reason.response?.status === 401) {
      error.value = '管理密钥不正确，请重新输入。'
      return
    }
    if (reason.response?.status === 409) {
      error.value =
        '模板已被更新，或当前有任务执行。请稍后重试；版本冲突时先重新载入。'
      return
    }
    if (reason.response?.status === 422) {
      error.value = '模板未通过参数或运行检查，当前生效版本保持不变。'
      return
    }
    if (reason.response?.status === 503) {
      error.value = '编译服务未就绪，请检查操作台的 Node 和渲染依赖。'
      return
    }
  }
  error.value = '操作未完成，请检查网络后重试。草稿仍保留在编辑区。'
}
function setPreview(value: TemplatePreview) {
  preview.value = value
  compiledSources.value = JSON.stringify(sources.value)
  runtimeFailed.value = false
}
async function compileRequest() {
  status.value = '正在检查 TypeScript 并编译预览…'
  const { data } = await dailyApi.post<TemplatePreview>(
    endpoint + '/preview',
    body(),
    { headers: headers(), timeout: 120000 },
  )
  if (!disposed) {
    setPreview(data)
    status.value = '预览已更新，可播放或拖动时间轴。'
  }
}
async function connect() {
  if (!authorized()) return
  busy.value = true
  error.value = ''
  status.value = '正在载入当前模板…'
  try {
    const { data } = await dailyApi.get<TemplateDocument>(endpoint, {
      headers: headers(),
    })
    if (disposed) return
    applyDocument(data)
    await compileRequest()
  } catch (reason) {
    if (!disposed) failure(reason)
  } finally {
    if (!disposed) busy.value = false
  }
}
async function compile() {
  if (!authorized() || !document.value) return
  busy.value = true
  error.value = ''
  diagnostics.value = []
  try {
    await compileRequest()
  } catch (reason) {
    if (!disposed) failure(reason)
  } finally {
    if (!disposed) busy.value = false
  }
}
async function save() {
  if (!authorized() || !document.value) return
  busy.value = true
  error.value = ''
  diagnostics.value = []
  status.value = '正在编译并渲染检查帧，成功后启用新版本…'
  try {
    const { data } = await dailyApi.put<
      TemplateDocument & { preview: TemplatePreview }
    >(endpoint, body(), { headers: headers(), timeout: 240000 })
    if (disposed) return
    applyDocument(data)
    setPreview(data.preview)
    status.value =
      '新版本已启用，将用于后续生成的视频。已有成片与审核记录保持原样。'
  } catch (reason) {
    if (!disposed) failure(reason)
  } finally {
    if (!disposed) busy.value = false
  }
}
async function restore() {
  if (!authorized() || !document.value || !restoreRevision.value) return
  busy.value = true
  error.value = ''
  status.value = '正在恢复模板版本…'
  try {
    const { data } = await dailyApi.post<TemplateDocument>(
      endpoint + '/restore',
      {
        expected_revision: document.value.revision,
        revision: restoreRevision.value,
      },
      { headers: headers() },
    )
    if (disposed) return
    applyDocument(data)
    await compileRequest()
    status.value = '已恢复所选版本，将用于后续视频。'
  } catch (reason) {
    if (!disposed) failure(reason)
  } finally {
    if (!disposed) busy.value = false
  }
}
function discard() {
  if (document.value) {
    applyDocument(clone(document.value))
    error.value = ''
    status.value = '已恢复当前生效版本的源码和样式。'
  }
}
function changeField(key: keyof TemplateTheme, kind: string, value: string) {
  if (theme.value)
    theme.value = {
      ...theme.value,
      [key]: kind === 'number' ? Number(value) : value,
    }
}
function sendProps() {
  if (!preview.value || !iframe.value?.contentWindow || !theme.value) return
  const props = clone(preview.value.props)
  const base = new URL('.', previewUrl.value)
  if (props.font) props.font = new URL(props.font, base).href
  for (const scene of props.scenes) {
    if (scene.audio) scene.audio = new URL(scene.audio, base).href
    if (scene.asset) scene.asset.src = new URL(scene.asset.src, base).href
  }
  props.theme = clone(theme.value)
  iframe.value.contentWindow.postMessage(
    {
      kind: 'sf-template-props',
      props,
      demo: composition.value === 'RenderDemo',
    },
    '*',
  )
}
function receive(event: MessageEvent) {
  if (event.source !== iframe.value?.contentWindow) return
  if (event.data?.kind === 'sf-template-ready') sendProps()
  if (event.data?.kind === 'sf-template-error') {
    runtimeFailed.value = true
    error.value =
      'React 运行错误：' +
      (typeof event.data.message === 'string'
        ? event.data.message.slice(0, 400)
        : '请检查源码后重新编译。')
  }
}
function insertTab(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    if (!busy.value && dirty.value) void save()
    return
  }
  if (event.key !== 'Tab' || busy.value || !currentFile.value?.editable) return
  event.preventDefault()
  const area = event.target as HTMLTextAreaElement
  const start = area.selectionStart
  sourceText.value =
    sourceText.value.slice(0, start) +
    '  ' +
    sourceText.value.slice(area.selectionEnd)
  void nextTick(() => {
    area.selectionStart = area.selectionEnd = start + 2
  })
}
function syncLines(event: Event) {
  const area = event.target as HTMLTextAreaElement
  const gutter = area.previousElementSibling
  if (gutter) gutter.scrollTop = area.scrollTop
}
function inspectDiagnostic(file: string, line: number, column: number) {
  if (document.value?.sources.some(item => item.path === file)) selectedFile.value = file
  mode.value = 'source'
  void nextTick(() => {
    const area = sourceArea.value
    if (!area) return
    const offset = sourceText.value.split('\n').slice(0, Math.max(0, line - 1)).reduce((sum, text) => sum + text.length + 1, 0)
    area.focus()
    area.setSelectionRange(offset + column - 1, offset + column - 1)
    area.scrollTop = Math.max(0, (line - 4) * 21.6)
  })
}
function preventLoss(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
watch([theme, composition], () => sendProps(), { deep: true })
onMounted(() => {
  window.addEventListener('message', receive)
  window.addEventListener('beforeunload', preventLoss)
  if (adminKey.value) void connect()
})
onUnmounted(() => {
  disposed = true
  window.removeEventListener('message', receive)
  window.removeEventListener('beforeunload', preventLoss)
})
</script>

<template>
  <section class="template-editor" aria-labelledby="template-editor-title">
    <header class="editor-heading">
      <div>
        <p>Remotion / 模板工作区</p>
        <h2 id="template-editor-title">修改源码，直接看效果。</h2>
      </div>
      <Code2 :size="25" aria-hidden="true" />
    </header>
    <p class="editor-intro">
      在这里编辑 React / TSX、调整样式、预览动画，再保存启用。视频规格沿用 1080
      × 1920 / 30 FPS。
    </p>
    <form v-if="!document" class="editor-connect" @submit.prevent="connect">
      <label for="template-key">管理密钥</label>
      <div>
        <input
          id="template-key"
          v-model="adminKey"
          type="password"
          autocomplete="off"
          placeholder="与操作台管理密钥相同"
        /><button type="submit" :disabled="busy">
          {{ busy ? '正在连接…' : '连接模板编辑器' }}
        </button>
      </div>
      <p>
        直接编辑 src/video.tsx、src/demo.tsx 和
        src/types.ts。修改会保存在本服务的模板版本中。
      </p>
    </form>
    <p v-if="status" class="editor-status" role="status">{{ status }}</p>
    <p v-if="error" class="editor-error" role="alert">{{ error }}</p>
    <template v-if="document && theme">
      <div class="editor-toolbar">
        <span>生效版本 <code>{{ document.revision.slice(0, 8) }}</code><strong v-if="dirty"> · 草稿未保存</strong></span>
        <div>
          <button
            type="button"
            :disabled="busy"
            data-testid="compile-template"
            @click="compile"
          >
            <Play :size="14" aria-hidden="true" />编译预览
          </button><button
            type="button"
            class="save-template"
            :disabled="busy || !dirty || runtimeFailed"
            data-testid="save-template"
            @click="save"
          >
            <Save :size="14" aria-hidden="true" />保存并启用
          </button>
        </div>
      </div>
      <div class="editor-layout">
        <div class="editing-pane">
          <div class="editing-tabs" role="group" aria-label="编辑方式">
            <button
              type="button"
              :aria-pressed="mode === 'source'"
              @click="mode = 'source'"
            >
              React 源码
            </button><button
              type="button"
              :aria-pressed="mode === 'style'"
              @click="mode = 'style'"
            >
              可视化样式
            </button>
          </div>
          <template v-if="mode === 'source'">
            <label for="template-file" class="field-label">模板文件</label><select id="template-file" v-model="selectedFile">
              <option
                v-for="file in document.sources"
                :key="file.path"
                :value="file.path"
              >
                {{ file.path }}{{ file.editable ? '' : '（视频规格，只读）' }}
              </option>
            </select>
            <div class="code-editor">
              <pre aria-hidden="true">{{ lines }}</pre>
              <textarea
                id="template-source"
                ref="sourceArea"
                v-model="sourceText"
                :readonly="busy || !currentFile?.editable"
                aria-label="React 模板源码"
                spellcheck="false"
                wrap="off"
                @keydown="insertTab"
                @scroll="syncLines"
              ></textarea>
            </div>
            <p class="editor-help">
              支持 Tab
              缩进。编译预览只更新草稿；保存并启用后，后续视频才使用新版本。
            </p>
          </template>
          <div v-else class="theme-fields">
            <label
              v-for="field in document.fields"
              :key="field.key"
              :for="`theme-${field.key}`"
            ><span>{{ field.label }}</span><input
              :id="`theme-${field.key}`"
              :type="
                field.kind === 'number'
                  ? 'number'
                  : field.kind === 'color'
                    ? 'color'
                    : 'text'
              "
              :value="theme[field.key]"
              :min="field.min"
              :max="field.max"
              :step="field.step"
              :maxlength="field.maxLength"
              :disabled="busy"
              @input="
                changeField(
                  field.key,
                  field.kind,
                  ($event.target as HTMLInputElement).value,
                )
              "
            /><code v-if="field.kind === 'color'">{{
              theme[field.key]
            }}</code></label><button
              type="button"
              :disabled="busy"
              @click="theme = clone(document.defaults)"
            >
              恢复默认样式
            </button>
            <p class="editor-help">
              样式修改会立即传入右侧预览。自定义源码通过 props.theme
              读取这些参数。
            </p>
          </div>
          <ol
            v-if="diagnostics.length"
            class="compile-errors"
            aria-label="编译错误"
          >
            <li v-for="(item, index) in diagnostics" :key="index">
              <button
                type="button"
                @click="inspectDiagnostic(item.file, item.line, item.column)"
              >
                {{ item.file }}:{{ item.line }}:{{ item.column }}
              </button>
              <pre>{{ item.message }}</pre>
            </li>
          </ol>
        </div>
        <aside class="template-preview" aria-label="真实 Remotion 预览">
          <label for="preview-composition">预览内容</label><select id="preview-composition" v-model="composition">
            <option value="SkillFinderDaily">主视频模板</option>
            <option value="RenderDemo">演示动画模板</option>
          </select>
          <p v-if="previewStale" class="preview-stale">
            源码已修改，请编译以更新画面。
          </p>
          <iframe
            v-if="preview"
            ref="iframe"
            :key="preview.id"
            :src="previewUrl"
            title="Remotion 模板实时预览"
            sandbox="allow-scripts"
            allow="autoplay"
            referrerpolicy="no-referrer"
            @load="sendProps"
          ></iframe>
          <div v-else class="preview-empty">
            编译完成后，可在这里播放动画、试听音轨并拖动时间轴。
          </div>
          <p class="editor-help">
            预览使用开发示例或已有样片，不生成新的配音，也不提交发布。
          </p>
        </aside>
      </div>
      <footer class="editor-footer">
        <div>
          <button type="button" :disabled="busy || !dirty" @click="discard">
            <RotateCcw :size="14" aria-hidden="true" />放弃本次修改
          </button><button type="button" :disabled="busy || dirty" @click="connect">
            重新载入
          </button>
        </div>
        <div class="version-controls">
          <label for="template-version">历史版本</label><select
            id="template-version"
            v-model="restoreRevision"
            :disabled="busy"
          >
            <option value="">选择要恢复的版本</option>
            <option
              v-for="version in document.versions"
              :key="version.revision"
              :value="version.revision"
              :disabled="version.revision === document.revision"
            >
              {{ version.revision.slice(0, 8) }} ·
              {{ new Date(version.created_at).toLocaleString('zh-CN') }}
            </option>
          </select><button
            type="button"
            :disabled="busy || dirty || !restoreRevision"
            @click="restore"
          >
            恢复此版本
          </button>
        </div>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.template-editor {
  min-width: 0;
}
.editor-heading,
.editor-toolbar,
.editor-toolbar > div,
.editor-footer,
.editor-footer > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.editor-heading {
  align-items: flex-start;
}
.editor-heading p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
h2 {
  font-size: 26px;
  line-height: 1.4;
  letter-spacing: -0.02em;
}
.editor-intro,
.editor-help,
.editor-connect p {
  color: var(--color-text-secondary);
  line-height: 1.8;
}
.editor-intro {
  font-size: 14px;
  margin-top: 16px;
  max-width: 75ch;
}
.editor-help,
.editor-connect p {
  font-size: 12px;
  margin-top: 12px;
}
.editor-connect {
  margin-top: 24px;
  max-width: 620px;
}
.editor-connect > div {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
.editor-connect input {
  flex: 1;
  min-width: 0;
}
button,
input,
select,
textarea {
  font: inherit;
  color: var(--color-text-primary);
}
button,
select,
input {
  border: 1px solid var(--color-border-strong);
  background: var(--color-canvas);
  border-radius: 7px;
  min-height: 40px;
  padding: 9px 12px;
}
button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  white-space: nowrap;
  font-size: 12px;
}
button:hover:not(:disabled) {
  border-color: var(--color-accent);
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
input::placeholder {
  color: var(--color-text-secondary);
}
.editor-status,
.editor-error {
  font-size: 13px;
  line-height: 1.8;
  margin-top: 18px;
}
.editor-error,
.compile-errors {
  color: var(--color-danger);
}
.editor-toolbar {
  margin: 24px 0 20px;
  padding-block: 16px;
  border-block: 1px solid var(--color-border);
  font-size: 11px;
  flex-wrap: wrap;
}
.editor-toolbar strong {
  font-weight: 500;
  color: var(--color-accent);
}
code {
  font-family: var(--font-mono);
  font-size: 11px;
}
.save-template {
  background: var(--color-accent);
  color: var(--color-accent-ink);
  border-color: var(--color-accent);
}
.editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(210px, 0.8fr);
  gap: 22px;
  align-items: start;
}
.editing-pane,
.template-preview {
  min-width: 0;
}
.editing-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.editing-tabs button[aria-pressed='true'] {
  color: var(--color-accent);
  border-color: var(--color-accent);
}
.field-label,
.template-preview > label {
  display: block;
  font-size: 12px;
  margin-bottom: 8px;
}
select {
  width: 100%;
  font-size: 12px;
}
.code-editor {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  height: 520px;
  margin-top: 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-canvas);
}
.code-editor pre,
.code-editor textarea {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.8;
  padding: 14px 12px;
  tab-size: 2;
  margin: 0;
  border: 0;
  white-space: pre;
}
.code-editor pre {
  text-align: right;
  color: var(--color-text-secondary);
  padding-inline: 7px;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
  user-select: none;
}
.code-editor textarea {
  resize: none;
  min-width: 0;
  width: 100%;
  height: 100%;
  outline-offset: -3px;
  background: transparent;
  overflow: auto;
}
.theme-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 14px;
}
.theme-fields label {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  font-size: 12px;
  min-width: 0;
}
.theme-fields label > span {
  width: 100%;
  color: var(--color-text-secondary);
}
.theme-fields input {
  width: 100%;
  min-width: 0;
}
.theme-fields input[type='color'] {
  width: 54px;
  padding: 3px;
}
.theme-fields > p {
  grid-column: 1/-1;
}
.template-preview > select {
  margin-bottom: 12px;
}
.template-preview iframe {
  width: 100%;
  height: 610px;
  max-height: 75vh;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #101618;
  display: block;
}
.preview-empty {
  padding: 60px 24px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  min-height: 360px;
  line-height: 1.9;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.preview-stale {
  font-size: 12px;
  margin-bottom: 12px;
  color: var(--color-accent);
}
.compile-errors {
  margin: 20px 0 0;
  padding-left: 18px;
}
.compile-errors li {
  margin-top: 12px;
}
.compile-errors button {
  padding: 0;
  border: 0;
  min-height: 28px;
  background: transparent;
  color: inherit;
  text-decoration: underline;
}
.compile-errors pre {
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
}
.editor-footer {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
  flex-wrap: wrap;
  align-items: flex-end;
}
.editor-footer > div {
  flex-wrap: wrap;
  justify-content: flex-start;
}
.version-controls {
  max-width: 100%;
}
.version-controls label {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.version-controls select {
  width: 220px;
  max-width: 100%;
}
@media (max-width: 1100px) {
  .editor-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-preview {
    max-width: 400px;
  }
  .template-preview iframe {
    height: 640px;
  }
  .editor-footer {
    gap: 22px;
  }
}
@media (max-width: 560px) {
  .editor-connect > div {
    flex-direction: column;
  }
  .editor-toolbar > div {
    flex-wrap: wrap;
  }
  .code-editor {
    height: 420px;
  }
  .theme-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .template-preview iframe {
    height: 570px;
  }
  .editor-heading h2 {
    font-size: 23px;
  }
  .version-controls {
    width: 100%;
  }
  .version-controls select {
    width: 100%;
  }
}
</style>
