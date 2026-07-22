import { apiRequest } from './api.js';
import { loadSession } from './session.js';
import { buildSearchQuery, escapeHtml, getResultState, listFromResponse, normalizeSort, readSearchState, resetPageOnFilterChange } from './sheet.js';

const state = { ...readSearchState(window.location.search) };
const form = document.querySelector('#search-form');
const results = document.querySelector('#results');
const status = document.querySelector('#results-status');
const pagination = document.querySelector('#pagination');
const drawer = document.querySelector('#filter-drawer');

function syncForm() { Object.entries(state).forEach(([key, value]) => { const field = form.elements[key]; if (field) field.value = value; }); }
function updateUrl() { history.replaceState(null, '', `/?${buildSearchQuery(state)}`); }
function text(value, fallback = '未提供') { return escapeHtml(value ?? fallback); }
function render(items) {
  results.innerHTML = items.map(item => `<article class="sheet-row"><div class="sheet-main"><a class="sheet-title" href="/sheet.html?id=${encodeURIComponent(item.id)}&${buildSearchQuery(state)}">${text(item.songName, '未命名曲谱')}</a><p class="sheet-subtitle">${text(item.singer, '未知歌手')} · ${text(item.arranger, '原版编配')}</p></div><dl class="sheet-meta"><div><dt>类型</dt><dd>${text(item.sheetType)}</dd></div><div><dt>难度</dt><dd>${text(item.difficulty)}</dd></div><div><dt>调性</dt><dd>${text(item.keySignature)}</dd></div><div><dt>变调夹</dt><dd>${item.capoPosition == null ? '无' : escapeHtml(item.capoPosition)}</dd></div><div><dt>调弦</dt><dd>${text(item.tuning)}</dd></div><div><dt>数据</dt><dd>${Number(item.viewCount || 0)} 浏览 · ${Number(item.favoriteCount || 0)} 收藏</dd></div></dl><p class="sheet-foot">上传者 ${text(item.uploaderNickname)} · ${text(formatDate(item.updateTime || item.createTime), '时间未知')}</p></article>`).join('');
}
function formatDate(value) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN'); }
function renderSkeleton() { results.innerHTML = '<div class="skeleton-list" aria-label="正在加载"><i></i><i></i><i></i></div>'; }
function renderPagination(page, size, total) { const pages = Math.max(1, Math.ceil(total / size)); pagination.innerHTML = pages <= 1 ? '' : `<button class="button secondary" data-page="${Math.max(1, page - 1)}" ${page <= 1 ? 'disabled' : ''}>上一页</button><span>第 ${page} / ${pages} 页</span><button class="button secondary" data-page="${Math.min(pages, page + 1)}" ${page >= pages ? 'disabled' : ''}>下一页</button>`; }
async function search() {
  status.textContent = '正在加载'; renderSkeleton();
  try { const data = listFromResponse(await apiRequest(`/api/sheets?${buildSearchQuery(state)}`)); render(data.items); renderPagination(data.page, data.size, data.total); status.textContent = data.items.length ? `找到 ${data.total} 份曲谱` : '暂无匹配曲谱'; if (!data.items.length) results.innerHTML = '<div class="empty-state"><h2>没有匹配结果</h2><p>换一个关键词或减少筛选条件再试试。</p></div>'; }
  catch (error) { status.textContent = '加载失败'; results.innerHTML = `<div class="empty-state error-state"><h2>暂时无法加载</h2><p>${text(error.message, '网络异常，请稍后重试')}</p><button class="button primary" id="retry-search" type="button">重试</button></div>`; pagination.innerHTML = ''; document.querySelector('#retry-search')?.addEventListener('click', search); }
}
form.addEventListener('submit', event => { event.preventDefault(); const values = Object.fromEntries(new FormData(form)); Object.assign(state, values, { sort: normalizeSort(values.sort), page: 1 }); updateUrl(); drawer?.removeAttribute('data-open'); search(); });
pagination.addEventListener('click', event => { const page = event.target.closest('[data-page]')?.dataset.page; if (page) { state.page = Number(page); updateUrl(); search(); } });
document.querySelector('#filter-open')?.addEventListener('click', () => drawer?.setAttribute('data-open', 'true'));
document.querySelector('#filter-close')?.addEventListener('click', () => drawer?.removeAttribute('data-open'));
syncForm(); loadSession().then(user => { const link = document.querySelector('[data-auth-link]'); if (user && link) { link.textContent = user.nickname || '个人'; link.href = '/profile.html'; } }).catch(() => {}); search();
