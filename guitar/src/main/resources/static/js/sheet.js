export const SORTS = Object.freeze({ LATEST: 'LATEST', MOST_FAVORITED: 'MOST_FAVORITED', MOST_VIEWED: 'MOST_VIEWED' });
export const FILTER_KEYS = ['keyword', 'songName', 'singer', 'sheetType', 'difficulty', 'keySignature', 'capoPosition', 'tuning'];

export function normalizeSort(value) { return SORTS[value] || SORTS.LATEST; }

export function buildSearchQuery(state = {}) {
  const params = new URLSearchParams();
  [...FILTER_KEYS, 'sort', 'page', 'size'].forEach(key => {
    const value = state[key];
    if (value !== undefined && value !== null && String(value).trim() !== '') params.set(key, String(value).trim());
  });
  if (!params.has('sort')) params.set('sort', SORTS.LATEST);
  if (!params.has('page')) params.set('page', '1');
  if (!params.has('size')) params.set('size', '20');
  return params.toString();
}

export function resetPageOnFilterChange(state = {}) { return { ...state, page: 1 }; }

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

export function getResultState({ loading, error, items = [] }) {
  if (loading) return { type: 'loading' };
  if (error) return { type: 'error', error };
  if (!items.length) return { type: 'empty' };
  return { type: 'results' };
}

export function readSearchState(search = '') {
  const params = new URLSearchParams(search);
  const state = {};
  [...FILTER_KEYS, 'sort', 'page', 'size'].forEach(key => { if (params.get(key)) state[key] = params.get(key); });
  state.sort = normalizeSort(state.sort);
  state.page = Math.max(1, Number(state.page || 1));
  state.size = Math.min(50, Math.max(1, Number(state.size || 20)));
  return state;
}

export function listFromResponse(data) {
  return { items: data?.records || data?.items || data?.content || [], total: Number(data?.total || 0), page: Number(data?.page || 1), size: Number(data?.size || 20) };
}
