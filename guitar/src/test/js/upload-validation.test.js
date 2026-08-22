import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createSubmitLock,
  moveFile,
  selectFilesForMode,
  validateFiles
} from '../../main/resources/static/js/upload.js';
import { validateAdminReason } from '../../main/resources/static/js/admin.js';
import { validateFolderName } from '../../main/resources/static/js/favorites.js';

const MB = 1024 * 1024;
const file = (name, size, type) => ({ name, size, type });

test('PDF 与多图模式切换时清空另一模式文件', () => {
  const pdf = file('score.pdf', MB, 'application/pdf');
  const image = file('page.jpg', MB, 'image/jpeg');
  let selection = selectFilesForMode({ mode: 'PDF', files: [pdf] }, 'IMAGES', [image]);
  assert.equal(selection.mode, 'IMAGES');
  assert.deepEqual(selection.files, [image]);
  selection = selectFilesForMode(selection, 'PDF', [pdf]);
  assert.deepEqual(selection.files, [pdf]);
});

test('PDF 只能选择一个且不得超过 30MB', () => {
  assert.equal(validateFiles('PDF', [file('score.pdf', 30 * MB, 'application/pdf')]), '');
  assert.match(validateFiles('PDF', [file('score.pdf', 30 * MB + 1, 'application/pdf')]), /30MB/);
  assert.match(validateFiles('PDF', [file('a.pdf', MB, 'application/pdf'), file('b.pdf', MB, 'application/pdf')]), /一个/);
});

test('图片每张不得超过 10MB 且最多 20 张', () => {
  assert.equal(validateFiles('IMAGES', [file('page.webp', 10 * MB, 'image/webp')]), '');
  assert.match(validateFiles('IMAGES', [file('page.png', 10 * MB + 1, 'image/png')]), /10MB/);
  assert.match(validateFiles('IMAGES', Array.from({ length: 21 }, (_, index) => file(`${index}.jpg`, MB, 'image/jpeg'))), /20/);
});

test('文件扩展名和基础类型在上传前校验', () => {
  assert.match(validateFiles('PDF', [file('score.txt', MB, 'text/plain')]), /PDF/);
  assert.match(validateFiles('IMAGES', [file('page.gif', MB, 'image/gif')]), /JPG|PNG|WebP/);
});

test('上移下移保持确定的文件顺序且不越界', () => {
  const files = ['01.jpg', '02.jpg', '03.jpg'];
  assert.deepEqual(moveFile(files, 2, -1), ['01.jpg', '03.jpg', '02.jpg']);
  assert.deepEqual(moveFile(files, 0, -1), files);
  assert.deepEqual(moveFile(files, 2, 1), files);
});

test('提交锁拒绝并发重复提交并在结束后释放', async () => {
  const lock = createSubmitLock();
  let finish;
  const first = lock.run(() => new Promise(resolve => { finish = resolve; }));
  assert.equal(lock.pending, true);
  assert.equal(await lock.run(async () => 'duplicate'), undefined);
  finish('done');
  assert.equal(await first, 'done');
  assert.equal(lock.pending, false);
  assert.equal(await lock.run(async () => 'again'), 'again');
});

test('收藏夹名称 trim 后限制 1 到 50 个字符', () => {
  assert.equal(validateFolderName(' 练习 '), '');
  assert.notEqual(validateFolderName('   '), '');
  assert.notEqual(validateFolderName('a'.repeat(51)), '');
});

test('下架理由 trim 后限制 1 到 500 个字符', () => {
  assert.equal(validateAdminReason(' 版权整改 '), '');
  assert.notEqual(validateAdminReason('  '), '');
  assert.notEqual(validateAdminReason('a'.repeat(501)), '');
});
