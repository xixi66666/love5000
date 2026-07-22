import { apiRequest } from './api.js';
import { isAdmin, loadSession } from './session.js';
import { escapeHtml, listFromResponse } from './sheet.js';

export function validateAdminReason(value) {
  const reason = String(value ?? '').trim();
  return reason.length >= 1 && reason.length <= 500 ? '' : '下架理由须为 1 到 500 个字符';
}

function initAdminPage() {
  const root = document.querySelector('#admin-app');
  if (!root) return;
  const form = document.querySelector('#admin-filters');
  const list = document.querySelector('#admin-sheets');
  const status = document.querySelector('#admin-status');
  const pagination = document.querySelector('#admin-pagination');
  const offlineDialog = document.querySelector('#offline-dialog');
  const offlineForm = document.querySelector('#offline-form');
  const confirmDialog = document.querySelector('#restore-dialog');
  const toast = document.querySelector('#toast');
  const state = { page: 1, size: 20, keyword: '', status: '', sort: 'LATEST' };
  let lastFocus = null;

  const notify = message => { toast.textContent = message; toast.hidden = false; setTimeout(() => { toast.hidden = true; }, 4000); };
  const query = () => { const params = new URLSearchParams(); Object.entries(state).forEach(([key, value]) => { if (value !== '') params.set(key, value); }); return params.toString(); };
  const openDialog = dialog => { lastFocus = document.activeElement; dialog.showModal(); requestAnimationFrame(() => dialog.querySelector('textarea,button')?.focus()); };
  const closeDialog = dialog => { dialog.close(); lastFocus?.focus(); };
  function render(records) {
    if (!records.length) { list.innerHTML = '<div class="empty-state"><h2>没有曲谱</h2><p>调整状态或关键词后重试。</p></div>'; return; }
    list.innerHTML = records.map(sheet => `<article class="admin-row"><div class="admin-row-main"><a class="row-title" href="/sheet.html?id=${encodeURIComponent(sheet.id)}">${escapeHtml(sheet.songName || '未命名曲谱')}</a><p>${escapeHtml(sheet.singer || '未知歌手')} · 上传者 ${escapeHtml(sheet.uploaderNickname || '未知')}</p></div><dl class="row-facts"><div><dt>状态</dt><dd><span class="status-badge status-${String(sheet.status || '').toLowerCase()}">${statusText(sheet.status)}</span></dd></div><div><dt>类型 / 难度</dt><dd>${escapeHtml(sheet.sheetType || '-')} / ${escapeHtml(sheet.difficulty || '-')}</dd></div><div><dt>浏览 / 收藏</dt><dd>${Number(sheet.viewCount || 0)} / ${Number(sheet.favoriteCount || 0)}</dd></div></dl><div class="row-actions">${sheet.status === 'PUBLISHED' ? `<button class="button secondary danger-text" type="button" data-offline="${sheet.id}" data-name="${escapeHtml(sheet.songName || '未命名曲谱')}">下架</button>` : ''}${sheet.status === 'OFFLINE' ? `<button class="button secondary" type="button" data-restore="${sheet.id}" data-name="${escapeHtml(sheet.songName || '未命名曲谱')}">恢复</button>` : ''}</div></article>`).join('');
  }
  function renderPagination(data) {
    const pages = Math.max(1, Math.ceil(data.total / data.size));
    pagination.innerHTML = pages <= 1 ? '' : `<button class="button secondary" type="button" data-page="${Math.max(1, data.page - 1)}" ${data.page <= 1 ? 'disabled' : ''}>上一页</button><span>第 ${data.page} / ${pages} 页</span><button class="button secondary" type="button" data-page="${Math.min(pages, data.page + 1)}" ${data.page >= pages ? 'disabled' : ''}>下一页</button>`;
  }
  async function loadSheets() {
    status.textContent = '正在加载'; list.innerHTML = '<div class="skeleton-list" aria-label="正在加载"><i></i><i></i><i></i></div>';
    try { const data = listFromResponse(await apiRequest(`/api/admin/sheets?${query()}`)); render(data.items); renderPagination(data); status.textContent = `${data.total} 份曲谱`; }
    catch (error) { status.textContent = error.status === 403 ? '无权访问' : '加载失败'; list.innerHTML = `<div class="empty-state error-state"><h2>无法加载管理列表</h2><p>${escapeHtml(error.message || '网络异常')}</p><button class="button primary" id="retry-admin" type="button">重试</button></div>`; document.querySelector('#retry-admin')?.addEventListener('click', loadSheets); }
  }
  form.addEventListener('submit', event => { event.preventDefault(); Object.assign(state, Object.fromEntries(new FormData(form)), { page: 1 }); loadSheets(); });
  pagination.addEventListener('click', event => { const page = event.target.closest('[data-page]')?.dataset.page; if (!page) return; state.page = Number(page); loadSheets(); });
  list.addEventListener('click', event => {
    const offline = event.target.closest('[data-offline]');
    const restore = event.target.closest('[data-restore]');
    if (offline) { offlineForm.reset(); offlineForm.elements.sheetId.value = offline.dataset.offline; document.querySelector('#offline-name').textContent = offline.dataset.name; document.querySelector('#offline-error').textContent = ''; openDialog(offlineDialog); }
    if (restore) { document.querySelector('#restore-name').textContent = restore.dataset.name; document.querySelector('#restore-action').dataset.sheetId = restore.dataset.restore; document.querySelector('#restore-error').textContent = ''; openDialog(confirmDialog); }
  });
  offlineForm.addEventListener('submit', async event => {
    event.preventDefault(); const reason = offlineForm.elements.reason.value.trim(); const error = validateAdminReason(reason); document.querySelector('#offline-error').textContent = error; if (error) { offlineForm.elements.reason.focus(); return; }
    const button = offlineForm.querySelector('[type=submit]'); button.disabled = true;
    try { await apiRequest(`/api/admin/sheets/${encodeURIComponent(offlineForm.elements.sheetId.value)}/offline`, { method: 'POST', body: { reason } }); closeDialog(offlineDialog); notify('曲谱已下架'); loadSheets(); }
    catch (requestError) { document.querySelector('#offline-error').textContent = requestError.message || '下架失败，请重试'; }
    finally { button.disabled = false; }
  });
  document.querySelector('#restore-action').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true;
    try { await apiRequest(`/api/admin/sheets/${encodeURIComponent(button.dataset.sheetId)}/restore`, { method: 'POST' }); closeDialog(confirmDialog); notify('曲谱已恢复'); loadSheets(); }
    catch (error) { document.querySelector('#restore-error').textContent = error.message || '恢复失败，请重试'; }
    finally { button.disabled = false; }
  });
  document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => closeDialog(button.closest('dialog'))));
  [offlineDialog, confirmDialog].forEach(dialog => dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(dialog); }));
  loadSession().then(() => {
    if (!isAdmin()) { sessionStorage.setItem('guitar.notice', '仅管理员可访问管理后台'); window.location.replace('/'); return; }
    root.hidden = false; loadSheets();
  }).catch(() => { window.location.replace('/'); });
}

function statusText(status) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', OFFLINE: '已下架', DELETED: '已删除' })[status] || status || '未知'; }

if (typeof document !== 'undefined') initAdminPage();
