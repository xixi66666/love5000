import { apiRequest } from './api.js';
import { loadSession } from './session.js';
import { escapeHtml, listFromResponse } from './sheet.js';

const MB = 1024 * 1024;
const AVATAR_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const AVATAR_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);

export function validateAvatar(file) {
  if (!file) return '请选择头像文件';
  if (file.size > 5 * MB) return '头像不得超过 5MB';
  const extension = String(file.name || '').split('.').pop().toLowerCase();
  return AVATAR_TYPES.has(file.type) && AVATAR_EXTENSIONS.has(extension) ? '' : '头像仅支持 JPG、PNG 或 WebP';
}

function initProfilePage() {
  const root = document.querySelector('#profile-app');
  if (!root) return;
  const nicknameForm = document.querySelector('#nickname-form');
  const avatarForm = document.querySelector('#avatar-form');
  const uploads = document.querySelector('#my-uploads');
  const uploadsStatus = document.querySelector('#uploads-status');
  const deleteDialog = document.querySelector('#delete-sheet-dialog');
  const toast = document.querySelector('#toast');
  let user = null;
  let lastFocus = null;

  const notify = message => { toast.textContent = message; toast.hidden = false; setTimeout(() => { toast.hidden = true; }, 4000); };
  const renderUser = current => {
    user = current;
    document.querySelector('#profile-initial').textContent = String(current.nickname || 'G').trim().slice(0, 1).toUpperCase();
    document.querySelector('#profile-name').textContent = current.nickname || '未设置昵称';
    document.querySelector('#profile-phone').textContent = current.phone || '';
    nicknameForm.elements.nickname.value = current.nickname || '';
    document.querySelector('#admin-entry').hidden = current.role !== 'ADMIN';
  };
  const renderUploads = records => {
    if (!records.length) { uploads.innerHTML = '<div class="empty-state"><h2>还没有上传</h2><p>上传第一份曲谱后会显示在这里。</p><a class="button primary" href="/upload.html">上传曲谱</a></div>'; return; }
    uploads.innerHTML = records.map(sheet => `<article class="compact-row"><div><a class="row-title" href="/sheet.html?id=${encodeURIComponent(sheet.id)}">${escapeHtml(sheet.songName || '未命名曲谱')}</a><p>${escapeHtml(sheet.singer || '未知歌手')} · <span class="status-badge status-${String(sheet.status || 'published').toLowerCase()}">${statusText(sheet.status)}</span></p></div><div class="row-actions"><span>${Number(sheet.viewCount || 0)} 浏览</span><a class="button secondary" href="/upload.html?id=${encodeURIComponent(sheet.id)}">编辑</a><button class="button secondary danger-text" type="button" data-delete-sheet="${sheet.id}" data-name="${escapeHtml(sheet.songName || '未命名曲谱')}">删除</button></div></article>`).join('');
  };
  async function loadUploads() {
    uploadsStatus.textContent = '正在加载'; uploads.innerHTML = '<div class="skeleton-list" aria-label="正在加载"><i></i><i></i></div>';
    try {
      // 当前公开检索接口仅返回已发布曲谱；按当前 Session 昵称筛出我的公开上传，编辑/删除仍由服务端所有权校验兜底。
      const data = listFromResponse(await apiRequest('/api/sheets?page=1&size=50&sort=LATEST'));
      const items = data.items.filter(sheet => !user?.nickname || sheet.uploaderNickname === user.nickname);
      renderUploads(items); uploadsStatus.textContent = `${items.length} 份公开曲谱`;
    }
    catch (error) { uploadsStatus.textContent = '加载失败'; uploads.innerHTML = `<div class="empty-state error-state"><h2>无法加载我的上传</h2><p>${escapeHtml(error.message || '网络异常')}</p><button class="button primary" id="retry-uploads" type="button">重试</button></div>`; document.querySelector('#retry-uploads')?.addEventListener('click', loadUploads); }
  }
  nicknameForm.addEventListener('submit', async event => {
    event.preventDefault(); const name = nicknameForm.elements.nickname.value.trim(); const errorNode = document.querySelector('#nickname-error');
    if (name.length < 1 || name.length > 30) { errorNode.textContent = '昵称须为 1 到 30 个字符'; nicknameForm.elements.nickname.focus(); return; }
    const button = nicknameForm.querySelector('[type=submit]'); button.disabled = true; errorNode.textContent = '';
    try { const updated = await apiRequest('/api/users/me', { method: 'PUT', body: { nickname: name } }); renderUser(updated); notify('昵称已更新'); }
    catch (error) { errorNode.textContent = error.message || '更新失败，请重试'; }
    finally { button.disabled = false; }
  });
  avatarForm.addEventListener('submit', async event => {
    event.preventDefault(); const avatar = avatarForm.elements.avatar.files[0]; const errorNode = document.querySelector('#avatar-error'); const error = validateAvatar(avatar); errorNode.textContent = error; if (error) { avatarForm.elements.avatar.focus(); return; }
    const button = avatarForm.querySelector('[type=submit]'); button.disabled = true;
    try { const data = new FormData(); data.append('avatar', avatar, avatar.name); const updated = await apiRequest('/api/users/me/avatar', { method: 'POST', body: data }); renderUser(updated); avatarForm.reset(); notify('头像已更新'); }
    catch (requestError) { errorNode.textContent = requestError.message || '头像上传失败，请重试'; }
    finally { button.disabled = false; }
  });
  uploads.addEventListener('click', event => {
    const button = event.target.closest('[data-delete-sheet]'); if (!button) return;
    lastFocus = button; document.querySelector('#delete-sheet-name').textContent = button.dataset.name; document.querySelector('#delete-sheet-action').dataset.sheetId = button.dataset.deleteSheet; document.querySelector('#delete-sheet-error').textContent = ''; deleteDialog.showModal(); requestAnimationFrame(() => document.querySelector('#delete-sheet-cancel').focus());
  });
  document.querySelector('#delete-sheet-action').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true;
    try { await apiRequest(`/api/sheets/${encodeURIComponent(button.dataset.sheetId)}`, { method: 'DELETE' }); deleteDialog.close(); notify('曲谱已删除'); loadUploads(); }
    catch (error) { document.querySelector('#delete-sheet-error').textContent = error.message || '删除失败，请重试'; }
    finally { button.disabled = false; }
  });
  const closeDelete = () => { deleteDialog.close(); lastFocus?.focus(); };
  document.querySelector('#delete-sheet-cancel').addEventListener('click', closeDelete);
  deleteDialog.addEventListener('cancel', event => { event.preventDefault(); closeDelete(); });
  loadSession().then(current => { if (!current) { window.location.href = `/auth.html?return=${encodeURIComponent('/profile.html')}`; return; } renderUser(current); root.hidden = false; loadUploads(); }).catch(() => { window.location.href = '/auth.html'; });
}

function statusText(status) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', OFFLINE: '已下架', DELETED: '已删除' })[status] || '已发布'; }

if (typeof document !== 'undefined') initProfilePage();
