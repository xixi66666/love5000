import test from 'node:test';
import assert from 'node:assert/strict';

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalSessionStorage = globalThis.sessionStorage;

function setupBrowser() {
  const storage = new Map();
  globalThis.sessionStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  globalThis.window = { location: { href: '' } };
  return storage;
}

test.afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
  globalThis.sessionStorage = originalSessionStorage;
});

test('解析失败 envelope 为 ApiError 并保留 code/message', async () => {
  setupBrowser();
  globalThis.fetch = async () => new Response(JSON.stringify({ success: false, code: 'BAD_INPUT', message: '输入无效' }), { status: 400, headers: { 'content-type': 'application/json' } });
  const { apiRequest, ApiError } = await import('../../main/resources/static/js/api.js?envelope=' + Date.now());
  await assert.rejects(() => apiRequest('/api/test'), error => error instanceof ApiError && error.status === 400 && error.code === 'BAD_INPUT' && error.message === '输入无效');
});

test('写请求自动获取 session 并注入 X-CSRF-Token', async () => {
  setupBrowser();
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (url === '/api/auth/session') return new Response(JSON.stringify({ success: true, data: { csrfToken: 'csrf-123', principal: null } }), { status: 200, headers: { 'content-type': 'application/json' } });
    return new Response(JSON.stringify({ success: true, data: { ok: true } }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  const { apiRequest } = await import('../../main/resources/static/js/api.js?csrf=' + Date.now());
  await apiRequest('/api/auth/logout', { method: 'POST', body: '{}' });
  assert.equal(calls[0].url, '/api/auth/session');
  assert.equal(calls[1].options.headers.get('X-CSRF-Token'), 'csrf-123');
});

test('401 清理 session 并跳转 auth.html', async () => {
  const storage = setupBrowser();
  storage.set('guitar.csrf', 'old');
  globalThis.fetch = async () => new Response(JSON.stringify({ success: false, code: 'AUTH_REQUIRED', message: '请先登录' }), { status: 401, headers: { 'content-type': 'application/json' } });
  const { apiRequest } = await import('../../main/resources/static/js/api.js?unauth=' + Date.now());
  await assert.rejects(() => apiRequest('/api/private'));
  assert.equal(window.location.href, '/auth.html');
  assert.equal(sessionStorage.getItem('guitar.csrf'), null);
});
