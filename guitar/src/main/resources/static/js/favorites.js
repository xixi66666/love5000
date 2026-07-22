import { apiRequest } from './api.js';
import { loadSession } from './session.js';
import { escapeHtml } from './sheet.js';

export function validateFolderName(value) {
  const name = String(value ?? '').trim();
  return name.length >= 1 && name.length <= 50 ? '' : '收藏夹名称须为 1 到 50 个字符';
}

export function createFavoriteState(folders = []) {
  const normalized = folders.map(folder => ({ ...folder, sheetCount: Number(folder.sheetCount || 0) }));
  return { folders: normalized, selectedFolderId: normalized[0]?.id ?? null, sheets: [], loading: false, error: null };
}

export function selectFolderInState(state, folderId) {
  return { ...state, selectedFolderId: folderId, sheets: [], loading: true, error: null };
}

export function removeSheetFromState(state, sheetId) {
  if (!state.sheets.some(sheet => Number(sheet.id) === Number(sheetId))) return state;
  return {
    ...state,
    sheets: state.sheets.filter(sheet => Number(sheet.id) !== Number(sheetId)),
    folders: state.folders.map(folder => Number(folder.id) === Number(state.selectedFolderId)
      ? { ...folder, sheetCount: Math.max(0, Number(folder.sheetCount || 0) - 1) } : folder)
  };
}

export function requiresFolderDeleteConfirmation(folder) { return Number(folder?.sheetCount || 0) > 0; }

export function deleteFolderFromState(state, folderId) {
  const folders = state.folders.filter(folder => Number(folder.id) !== Number(folderId));
  const selectedFolderId = Number(state.selectedFolderId) === Number(folderId) ? (folders[0]?.id ?? null) : state.selectedFolderId;
  return { ...state, folders, selectedFolderId, sheets: Number(state.selectedFolderId) === Number(folderId) ? [] : state.sheets };
}

function initFavoritesPage() {
  const root = document.querySelector('#favorites-app');
  if (!root) return;
  const folderList = document.querySelector('#folder-list');
  const sheets = document.querySelector('#favorite-sheets');
  const status = document.querySelector('#favorites-status');
  const createForm = document.querySelector('#create-folder-form');
  const folderDialog = document.querySelector('#folder-dialog');
  const folderDialogForm = document.querySelector('#folder-dialog-form');
  const confirmDialog = document.querySelector('#confirm-dialog');
  const toast = document.querySelector('#toast');
  let state = createFavoriteState();
  let lastFocus = null;

  const setStatus = message => { status.textContent = message; };
  const notify = message => { toast.textContent = message; toast.hidden = false; setTimeout(() => { toast.hidden = true; }, 4000); };
  const currentFolder = () => state.folders.find(folder => Number(folder.id) === Number(state.selectedFolderId));
  const renderFolders = () => {
    folderList.innerHTML = state.folders.length ? state.folders.map(folder => `<li><button class="folder-link ${Number(folder.id) === Number(state.selectedFolderId) ? 'is-active' : ''}" type="button" data-folder-id="${folder.id}" aria-current="${Number(folder.id) === Number(state.selectedFolderId) ? 'page' : 'false'}"><span>${escapeHtml(folder.name)}</span><span class="count">${Number(folder.sheetCount || 0)}</span></button></li>`).join('') : '<li class="muted">还没有收藏夹</li>';
    const disabled = !currentFolder();
    document.querySelector('#rename-folder').disabled = disabled;
    document.querySelector('#delete-folder').disabled = disabled;
  };
  const renderSheets = () => {
    if (state.loading) { sheets.innerHTML = '<div class="skeleton-list" aria-label="正在加载"><i></i><i></i></div>'; return; }
    if (state.error) { sheets.innerHTML = `<div class="empty-state error-state"><h2>加载失败</h2><p>${escapeHtml(state.error.message || '网络异常，请重试')}</p><button class="button primary" id="retry-folder" type="button">重试</button></div>`; document.querySelector('#retry-folder')?.addEventListener('click', loadSelectedFolder); return; }
    if (!state.selectedFolderId) { sheets.innerHTML = '<div class="empty-state"><h2>暂无收藏夹</h2><p>先在左侧新建一个收藏夹。</p></div>'; return; }
    if (!state.sheets.length) { sheets.innerHTML = '<div class="empty-state"><h2>收藏夹为空</h2><p>从曲谱详情页加入内容。</p></div>'; return; }
    sheets.innerHTML = state.sheets.map(sheet => `<article class="compact-row"><div><a class="row-title" href="/sheet.html?id=${encodeURIComponent(sheet.id)}">${escapeHtml(sheet.songName || '未命名曲谱')}</a><p>${escapeHtml(sheet.singer || '未知歌手')} · ${escapeHtml(sheet.keySignature || '调性未填')} · ${escapeHtml(sheet.difficulty || '难度未填')}</p></div><div class="row-actions"><span>${Number(sheet.favoriteCount || 0)} 收藏</span><button class="button secondary danger-text" type="button" data-remove-sheet="${sheet.id}">移除</button></div></article>`).join('');
  };
  const render = () => { renderFolders(); renderSheets(); };
  async function loadSelectedFolder() {
    if (!state.selectedFolderId) { render(); setStatus('暂无收藏夹'); return; }
    state = { ...state, loading: true, error: null }; renderSheets();
    try {
      const records = await apiRequest(`/api/favorite-folders/${encodeURIComponent(state.selectedFolderId)}/sheets`);
      state = { ...state, sheets: Array.isArray(records) ? records : [], loading: false };
      state.folders = state.folders.map(folder => Number(folder.id) === Number(state.selectedFolderId) ? { ...folder, sheetCount: state.sheets.length } : folder);
      setStatus(`${state.sheets.length} 份曲谱`); render();
    } catch (error) { state = { ...state, loading: false, error }; setStatus(error.status === 403 ? '无权访问' : '加载失败'); renderSheets(); }
  }
  async function loadFolders() {
    setStatus('正在加载');
    try {
      const folders = await apiRequest('/api/favorite-folders');
      state = createFavoriteState(Array.isArray(folders) ? folders : []); render(); await loadSelectedFolder();
    } catch (error) { state = { ...state, error }; setStatus(error.status === 403 ? '无权访问' : '加载失败'); renderSheets(); }
  }
  function openDialog(dialog) { lastFocus = document.activeElement; dialog.showModal(); requestAnimationFrame(() => dialog.querySelector('input,button,textarea')?.focus()); }
  function closeDialog(dialog) { dialog.close(); lastFocus?.focus(); }
  async function saveFolder(name, folderId = null) {
    const error = validateFolderName(name);
    const errorNode = folderId ? document.querySelector('#folder-dialog-error') : document.querySelector('#create-folder-error');
    errorNode.textContent = error;
    if (error) return;
    const button = folderId ? folderDialogForm.querySelector('[type=submit]') : createForm.querySelector('[type=submit]');
    button.disabled = true;
    try {
      const folder = await apiRequest(folderId ? `/api/favorite-folders/${encodeURIComponent(folderId)}` : '/api/favorite-folders', { method: folderId ? 'PUT' : 'POST', body: { name: name.trim(), sortOrder: currentFolder()?.sortOrder || 0 } });
      if (folderId) state.folders = state.folders.map(item => Number(item.id) === Number(folderId) ? { ...item, ...folder } : item);
      else { state.folders.push({ ...folder, sheetCount: 0 }); state.selectedFolderId = folder.id; state.sheets = []; createForm.reset(); }
      render(); if (folderId) closeDialog(folderDialog); notify(folderId ? '收藏夹已重命名' : '收藏夹已创建');
    } catch (requestError) { errorNode.textContent = requestError.message || '保存失败，请重试'; }
    finally { button.disabled = false; }
  }

  folderList.addEventListener('click', event => { const button = event.target.closest('[data-folder-id]'); if (!button || Number(button.dataset.folderId) === Number(state.selectedFolderId)) return; state = selectFolderInState(state, Number(button.dataset.folderId)); render(); loadSelectedFolder(); });
  createForm.addEventListener('submit', event => { event.preventDefault(); saveFolder(createForm.elements.name.value); });
  document.querySelector('#rename-folder').addEventListener('click', event => { const folder = currentFolder(); if (!folder) return; folderDialogForm.elements.folderId.value = folder.id; folderDialogForm.elements.name.value = folder.name; openDialog(folderDialog); });
  folderDialogForm.addEventListener('submit', event => { event.preventDefault(); saveFolder(folderDialogForm.elements.name.value, folderDialogForm.elements.folderId.value); });
  document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => closeDialog(button.closest('dialog'))));
  document.querySelector('#delete-folder').addEventListener('click', () => {
    const folder = currentFolder(); if (!folder) return;
    document.querySelector('#confirm-title').textContent = `删除“${folder.name}”`; document.querySelector('#confirm-message').textContent = requiresFolderDeleteConfirmation(folder) ? `其中 ${folder.sheetCount} 份曲谱会从收藏中移除，曲谱本身不会被删除。` : '此收藏夹为空。';
    document.querySelector('#confirm-action').dataset.folderId = folder.id; openDialog(confirmDialog);
  });
  document.querySelector('#confirm-action').addEventListener('click', async event => {
    const folderId = event.currentTarget.dataset.folderId; event.currentTarget.disabled = true;
    try { await apiRequest(`/api/favorite-folders/${encodeURIComponent(folderId)}`, { method: 'DELETE' }); state = deleteFolderFromState(state, folderId); closeDialog(confirmDialog); render(); await loadSelectedFolder(); notify('收藏夹已删除'); }
    catch (error) { document.querySelector('#confirm-error').textContent = error.message || '删除失败，请重试'; }
    finally { event.currentTarget.disabled = false; }
  });
  sheets.addEventListener('click', async event => {
    const button = event.target.closest('[data-remove-sheet]'); if (!button) return;
    button.disabled = true; const before = state; state = removeSheetFromState(state, button.dataset.removeSheet); render();
    try { await apiRequest(`/api/favorite-folders/${encodeURIComponent(state.selectedFolderId)}/sheets/${encodeURIComponent(button.dataset.removeSheet)}`, { method: 'DELETE' }); setStatus(`${state.sheets.length} 份曲谱`); notify('已移出收藏夹'); }
    catch (error) { state = before; render(); notify(error.message || '移除失败，请重试'); }
  });
  [folderDialog, confirmDialog].forEach(dialog => dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(dialog); }));
  loadSession().then(user => { if (!user) window.location.href = `/auth.html?return=${encodeURIComponent('/favorites.html')}`; else loadFolders(); }).catch(error => { state = { ...state, error }; renderSheets(); });
}

if (typeof document !== 'undefined') initFavoritesPage();
