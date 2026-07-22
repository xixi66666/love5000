import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createFavoriteState,
  deleteFolderFromState,
  removeSheetFromState,
  requiresFolderDeleteConfirmation,
  selectFolderInState
} from '../../main/resources/static/js/favorites.js';

const folders = [
  { id: 1, name: '练习', sheetCount: 2 },
  { id: 2, name: '演出', sheetCount: 0 }
];

test('初始化时选择首个收藏夹并保持空列表', () => {
  const state = createFavoriteState(folders);
  assert.equal(state.selectedFolderId, 1);
  assert.deepEqual(state.sheets, []);
});

test('切换收藏夹时清空旧曲谱和错误状态', () => {
  const state = { ...createFavoriteState(folders), sheets: [{ id: 8 }], error: new Error('offline') };
  const next = selectFolderInState(state, 2);
  assert.equal(next.selectedFolderId, 2);
  assert.deepEqual(next.sheets, []);
  assert.equal(next.error, null);
});

test('移除收藏是幂等本地更新并递减当前文件夹计数', () => {
  const state = { ...createFavoriteState(folders), sheets: [{ id: 8 }, { id: 9 }] };
  const once = removeSheetFromState(state, 8);
  const twice = removeSheetFromState(once, 8);
  assert.deepEqual(twice.sheets.map(sheet => sheet.id), [9]);
  assert.equal(twice.folders[0].sheetCount, 1);
});

test('只有非空收藏夹删除前需要确认', () => {
  assert.equal(requiresFolderDeleteConfirmation(folders[0]), true);
  assert.equal(requiresFolderDeleteConfirmation(folders[1]), false);
});

test('删除当前收藏夹后选择下一个可用收藏夹', () => {
  const next = deleteFolderFromState(createFavoriteState(folders), 1);
  assert.deepEqual(next.folders.map(folder => folder.id), [2]);
  assert.equal(next.selectedFolderId, 2);
});
