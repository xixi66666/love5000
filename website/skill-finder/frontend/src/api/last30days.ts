import { http } from '@/api/client'

export type Last30DaysStatus =
  | 'working'
  | 'no-results'
  | 'partial'
  | 'error'
  | 'skipped'
  | 'unconfigured'

export interface Last30DaysCluster {
  title: string
  summary: string
  sources: string[]
  engagement_total: number
}

export interface Last30DaysItem {
  candidate_id: string
  title: string
  source: string
  url: string
  published_at: string
  summary: string
  engagement: Record<string, unknown>
  relevance_score: number | null
  cluster: number | null
}

export interface Last30DaysResponse {
  status: Last30DaysStatus
  query: string
  items: Last30DaysItem[]
  clusters: Last30DaysCluster[]
  sources: string[]
  source_status: Record<string, unknown>
  fetched_at: string
  message?: string | null
}

export interface Last30DaysStatusResponse {
  status: Last30DaysStatus
  sources: string[]
  message?: string | null
}

export type Last30DaysDirection = 'agent' | 'skill'

export interface Last30DaysRankingResponse {
  direction: Last30DaysDirection
  status: Last30DaysStatus
  items: Last30DaysItem[]
  clusters: Last30DaysCluster[]
  sources: string[]
  source_status: Record<string, unknown>
  fetched_at: string
  message?: string | null
}

export async function fetchLast30daysStatus(): Promise<Last30DaysStatusResponse> {
  const { data } = await http.get<Last30DaysStatusResponse>('/last30days/status')
  return data
}

export async function postLast30days(query: string, limit = 50): Promise<Last30DaysResponse> {
  const { data } = await http.post<Last30DaysResponse>('/last30days', {
    query: query.trim(),
    limit,
  })
  return data
}

export async function fetchLast30daysRankings(
  direction: Last30DaysDirection,
): Promise<Last30DaysRankingResponse> {
  const { data } = await http.get<Last30DaysRankingResponse>('/last30days/rankings', {
    params: { direction },
  })
  return data
}

// 引擎刷新可能需要几分钟，覆盖默认的 15s 超时（后端引擎超时 600s + 余量）。
const REFRESH_TIMEOUT_MS = 620_000

export async function refreshLast30daysRankings(
  direction: Last30DaysDirection,
): Promise<Last30DaysRankingResponse> {
  const { data } = await http.post<Last30DaysRankingResponse>(
    '/last30days/rankings/refresh',
    { direction },
    { timeout: REFRESH_TIMEOUT_MS },
  )
  return data
}
