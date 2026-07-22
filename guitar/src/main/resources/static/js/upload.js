import { ApiError, apiRequest } from './api.js';
import { getCsrfToken, loadSession } from './session.js';

const MB = 1024 * 1024;
const PDF_LIMIT = 30 * MB;
const IMAGE_LIMIT = 10 * MB;
const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);
const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

export function selectFilesForMode(_current, mode, files = []) {
  return { mode: mode === 'IMAGES' ? 'IMAGES' : 'PDF', files: Array.from(files) };
}

export function validateFiles(mode, files = []) {
  const selected = Array.from(files);
  if (mode === 'PDF') {
    if (selected.length !== 1) return 'PDF 模式只能选择一个文件';
    const chosen = selected[0];
    if (chosen.size > PDF_LIMIT) return 'PDF 文件不得超过 30MB';
    if (extension(chosen.name) !== 'pdf' || chosen.type !== 'application/pdf') return '请选择扩展名和类型正确的 PDF 文件';
    return '';
  }
  if (selected.length < 1 || selected.length > 20) return '多图模式请选择 1 到 20 张图片';
  for (const chosen of selected) {
    if (chosen.size > IMAGE_LIMIT) return '每张图片不得超过 10MB';
    if (!IMAGE_EXTENSIONS.has(extension(chosen.name)) || !IMAGE_TYPES.has(chosen.type)) return '图片仅支持 JPG、PNG 或 WebP';
  }
  return '';
}

export function moveFile(files, index, delta) {
  const next = Array.from(files);
  const target = index + delta;
  if (index < 0 || target < 0 || index >= next.length || target >= next.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function createSubmitLock() {
  let pending = false;
  return {
    get pending() { return pending; },
    async run(operation) {
      if (pending) return undefined;
      pending = true;
      try { return await operation(); } finally { pending = false; }
    }
  };
}

function extension(name) { return String(name || '').split('.').pop().toLowerCase(); }

export function uploadMultipart(path, method, formData, { csrfToken, onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(method, path);
    request.withCredentials = true;
    request.setRequestHeader('Accept', 'application/json');
    if (csrfToken) request.setRequestHeader('X-CSRF-Token', csrfToken);
    request.upload.addEventListener('progress', event => {
      if (event.lengthComputable) onProgress?.(Math.round(event.loaded / event.total * 100));
    });
    request.addEventListener('load', () => {
      let envelope = {};
      try { envelope = JSON.parse(request.responseText || '{}'); } catch { /* 统一按未知响应处理 */ }
      if (request.status === 401) window.location.href = '/auth.html';
      if (request.status < 200 || request.status >= 300 || envelope.success === false) {
        reject(new ApiError(request.status, envelope.code, envelope.message || '上传失败，请稍后重试', envelope.data));
        return;
      }
      resolve(envelope.data);
    });
    request.addEventListener('error', () => reject(new ApiError(0, 'NETWORK_ERROR', '网络异常，请检查连接后重试')));
    request.addEventListener('abort', () => reject(new ApiError(0, 'REQUEST_ABORTED', '上传已取消')));
    request.send(formData);
  });
}

function initUploadPage() {
  const form = document.querySelector('#sheet-form');
  if (!form) return;
  const editId = new URLSearchParams(window.location.search).get('id');
  const fileInput = document.querySelector('#sheet-files');
  const fileList = document.querySelector('#selected-files');
  const fileError = document.querySelector('#file-error');
  const formError = document.querySelector('#form-error');
  const dropZone = document.querySelector('#drop-zone');
  const progress = document.querySelector('#upload-progress');
  const progressText = document.querySelector('#progress-text');
  const createButton = document.querySelector('#create-submit');
  const metadataButton = document.querySelector('#metadata-submit');
  const filesButton = document.querySelector('#files-submit');
  const lock = createSubmitLock();
  let selection = { mode: 'PDF', files: [] };

  const currentMode = () => form.elements.fileMode.value;
  const setBusy = busy => {
    [createButton, metadataButton, filesButton].filter(Boolean).forEach(button => { button.disabled = busy; });
    form.setAttribute('aria-busy', String(busy));
  };
  const showError = message => { formError.textContent = message || ''; formError.hidden = !message; };
  const updateProgress = value => {
    progress.hidden = false; progress.value = value; progressText.textContent = `上传进度 ${value}%`;
  };
  const syncAccept = () => {
    const pdf = currentMode() === 'PDF';
    fileInput.accept = pdf ? '.pdf,application/pdf' : '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';
    fileInput.multiple = !pdf;
    document.querySelector('#drop-hint').textContent = pdf ? '拖入或选择一个 PDF' : '拖入或选择 1-20 张图片';
  };
  const setFiles = files => {
    selection = selectFilesForMode(selection, currentMode(), files);
    fileError.textContent = validateFiles(selection.mode, selection.files);
    renderFiles();
  };
  const renderFiles = () => {
    fileList.innerHTML = selection.files.map((file, index) => {
      const isImage = IMAGE_TYPES.has(file.type);
      const preview = isImage ? `<img src="${URL.createObjectURL(file)}" alt="${escapeAttribute(file.name)} 缩略图">` : '<span class="file-type">PDF</span>';
      return `<li class="selected-file" data-index="${index}">${preview}<span class="file-name">${escapeText(file.name)}</span><span class="file-size">${formatBytes(file.size)}</span><div class="file-order"><button class="icon-button" type="button" data-move="-1" aria-label="上移 ${escapeAttribute(file.name)}" title="上移" ${index === 0 ? 'disabled' : ''}>${arrowIcon('up')}</button><button class="icon-button" type="button" data-move="1" aria-label="下移 ${escapeAttribute(file.name)}" title="下移" ${index === selection.files.length - 1 ? 'disabled' : ''}>${arrowIcon('down')}</button></div></li>`;
    }).join('');
  };
  const metadata = includeMode => {
    const data = Object.fromEntries(new FormData(form));
    const result = {
      songName: data.songName.trim(), singer: data.singer.trim(), arranger: data.arranger.trim(),
      description: data.description.trim(), keywords: data.keywords.trim(), sheetType: data.sheetType,
      difficulty: data.difficulty, keySignature: data.keySignature.trim(),
      capoPosition: data.capoPosition === '' ? null : Number(data.capoPosition), tuning: data.tuning.trim()
    };
    if (includeMode) result.fileMode = currentMode();
    return result;
  };
  const validateForm = requireFiles => {
    showError('');
    if (!form.reportValidity()) return false;
    if (requireFiles) {
      const error = validateFiles(currentMode(), selection.files);
      fileError.textContent = error;
      if (error) { fileInput.focus(); return false; }
    }
    return true;
  };
  const multipart = (includeMetadata = true) => {
    const data = new FormData();
    if (includeMetadata) data.append('metadata', new Blob([JSON.stringify(metadata(true))], { type: 'application/json' }));
    else data.append('mode', currentMode());
    selection.files.forEach(file => data.append('files', file, file.name));
    return data;
  };
  const runLocked = operation => lock.run(async () => {
    setBusy(true); progress.hidden = true;
    try { await operation(); } catch (error) { showError(error.message || '操作失败，请稍后重试'); }
    finally { setBusy(false); }
  });

  form.querySelectorAll('[name=fileMode]').forEach(radio => radio.addEventListener('change', () => {
    selection = selectFilesForMode(selection, currentMode(), []); fileInput.value = ''; fileError.textContent = ''; syncAccept(); renderFiles();
  }));
  fileInput.addEventListener('change', () => setFiles(fileInput.files));
  dropZone.addEventListener('dragover', event => { event.preventDefault(); dropZone.classList.add('is-dragging'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('is-dragging'));
  dropZone.addEventListener('drop', event => { event.preventDefault(); dropZone.classList.remove('is-dragging'); setFiles(event.dataTransfer.files); });
  fileList.addEventListener('click', event => {
    const button = event.target.closest('[data-move]');
    if (!button) return;
    const item = button.closest('[data-index]');
    selection.files = moveFile(selection.files, Number(item.dataset.index), Number(button.dataset.move));
    renderFiles();
    fileList.querySelector(`[data-index="${Number(item.dataset.index) + Number(button.dataset.move)}"] [data-move="${button.dataset.move}"]`)?.focus();
  });
  createButton?.addEventListener('click', () => {
    if (!validateForm(true)) return;
    runLocked(async () => {
      const data = await uploadMultipart('/api/sheets', 'POST', multipart(true), { csrfToken: getCsrfToken(), onProgress: updateProgress });
      window.location.href = `/sheet.html?id=${encodeURIComponent(data.id)}`;
    });
  });
  metadataButton?.addEventListener('click', () => {
    if (!validateForm(false)) return;
    runLocked(async () => {
      const data = await apiRequest(`/api/sheets/${encodeURIComponent(editId)}`, { method: 'PUT', body: metadata(false) });
      showToast('曲谱资料已保存');
      document.title = `${data.songName || '编辑曲谱'} · Guitar`;
    });
  });
  filesButton?.addEventListener('click', () => {
    if (!validateForm(true)) return;
    runLocked(async () => {
      await uploadMultipart(`/api/sheets/${encodeURIComponent(editId)}/files`, 'PUT', multipart(false), { csrfToken: getCsrfToken(), onProgress: updateProgress });
      showToast('曲谱文件已替换'); selection.files = []; fileInput.value = ''; renderFiles();
    });
  });

  async function bootstrap() {
    const user = await loadSession();
    if (!user) { window.location.href = `/auth.html?return=${encodeURIComponent(window.location.pathname + window.location.search)}`; return; }
    if (editId) {
      document.body.classList.add('is-editing');
      document.querySelector('#page-title').textContent = '编辑曲谱';
      try {
        const data = await apiRequest(`/api/sheets/${encodeURIComponent(editId)}`);
        ['songName', 'singer', 'arranger', 'description', 'keywords', 'sheetType', 'difficulty', 'keySignature', 'capoPosition', 'tuning'].forEach(key => { if (form.elements[key] && data[key] != null) form.elements[key].value = data[key]; });
        const mode = data.fileMode || inferMode(data.files);
        if (form.elements.fileMode.value !== mode) form.querySelector(`[name=fileMode][value="${mode}"]`)?.click();
      } catch (error) { showError(error.message || '无法加载曲谱资料'); setBusy(true); }
    }
  }
  syncAccept(); bootstrap().catch(error => showError(error.message || '无法读取登录状态'));
}

function inferMode(files = []) { return files.some(file => file.mimeType === 'application/pdf' || file.fileExtension === 'pdf') ? 'PDF' : 'IMAGES'; }
function escapeText(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])); }
function escapeAttribute(value) { return escapeText(value); }
function formatBytes(value) { return value >= MB ? `${(value / MB).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`; }
function arrowIcon(direction) { const path = direction === 'up' ? 'm18 15-6-6-6 6' : 'm6 9 6 6 6-6'; return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`; }
function showToast(message) { const toast = document.querySelector('#toast'); if (!toast) return; toast.textContent = message; toast.hidden = false; setTimeout(() => { toast.hidden = true; }, 4000); }

if (typeof document !== 'undefined') initUploadPage();
