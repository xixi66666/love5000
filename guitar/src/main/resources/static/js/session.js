import { apiRequest, clearCsrf } from './api.js';

let current = null;
let csrfToken = null;

export async function loadSession() {
  const data = await apiRequest('/api/auth/session');
  current = data?.user || null;
  csrfToken = data?.csrfToken || csrfToken;
  return current;
}
export function getSession() { return current; }
export function getCsrfToken() { return csrfToken; }
export function isAuthenticated() { return Boolean(current); }
export function isAdmin() { return current?.role === 'ADMIN'; }
export async function logout() {
  try { await apiRequest('/api/auth/logout', { method: 'POST' }); } finally { current = null; csrfToken = null; clearCsrf(); }
}
