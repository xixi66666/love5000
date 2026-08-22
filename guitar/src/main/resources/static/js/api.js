const CSRF_KEY = 'guitar.csrf';

export class ApiError extends Error {
  constructor(status, code, message, data = null) {
    super(message || '请求失败');
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'REQUEST_FAILED';
    this.data = data;
  }
}

function browserStorage() {
  return typeof sessionStorage === 'undefined' ? null : sessionStorage;
}

function clearSessionAndRedirect() {
  browserStorage()?.removeItem(CSRF_KEY);
  if (typeof window !== 'undefined' && window.location) window.location.href = '/auth.html';
}

async function readJson(response) {
  try { return await response.json(); } catch { return {}; }
}

async function ensureCsrf() {
  const stored = browserStorage()?.getItem(CSRF_KEY);
  if (stored) return stored;
  const response = await fetch('/api/auth/session', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  const envelope = await readJson(response);
  if (!response.ok || envelope.success === false) throw new ApiError(response.status, envelope.code, envelope.message, envelope.data);
  const token = envelope.data?.csrfToken;
  if (token) browserStorage()?.setItem(CSRF_KEY, token);
  return token;
}

export async function apiRequest(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  let csrf;
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    csrf = await ensureCsrf();
    if (csrf) headers.set('X-CSRF-Token', csrf);
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
      options = { ...options, body: JSON.stringify(options.body) };
    }
  }
  const response = await fetch(path, { ...options, method, credentials: 'same-origin', headers });
  const envelope = await readJson(response);
  if (response.status === 401) {
    clearSessionAndRedirect();
    throw new ApiError(response.status, envelope.code || 'AUTH_REQUIRED', envelope.message || '请先登录', envelope.data);
  }
  if (!response.ok || envelope.success === false) throw new ApiError(response.status, envelope.code, envelope.message, envelope.data);
  if (envelope.data?.csrfToken) browserStorage()?.setItem(CSRF_KEY, envelope.data.csrfToken);
  return envelope.data;
}

export function clearCsrf() { browserStorage()?.removeItem(CSRF_KEY); }
