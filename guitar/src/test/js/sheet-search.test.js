import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSearchQuery, resetPageOnFilterChange, escapeHtml, normalizeSort } from '../../main/resources/static/js/sheet.js';

test('搜索参数只序列化非空值并保留白名单排序', () => {
  const query = buildSearchQuery({ keyword: '  小情歌 ', singer: '', sort: 'MOST_VIEWED', page: 2, size: 20 });
  assert.equal(query, 'keyword=%E5%B0%8F%E6%83%85%E6%AD%8C&sort=MOST_VIEWED&page=2&size=20');
  assert.equal(normalizeSort('unknown'), 'LATEST');
});

test('筛选条件变化将页码重置为 1', () => {
  assert.deepEqual(resetPageOnFilterChange({ keyword: 'new', page: 7 }), { keyword: 'new', page: 1 });
});

test('文本输出始终进行 HTML 转义', () => {
  assert.equal(escapeHtml('<img src=x onerror=alert(1)> & "x"'), '&lt;img src=x onerror=alert(1)&gt; &amp; &quot;x&quot;');
});

test('列表渲染状态可表达空结果与错误重试', async () => {
  const { getResultState } = await import('../../main/resources/static/js/sheet.js?state=' + Date.now());
  assert.equal(getResultState({ loading: false, error: null, items: [] }).type, 'empty');
  assert.equal(getResultState({ loading: false, error: new Error('offline'), items: [] }).type, 'error');
});
