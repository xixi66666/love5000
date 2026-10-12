import { http } from '@/api/client'
import type {
  LanguageStat,
  RepositoryDetail,
  RepositoryListResponse,
  RepositoryQuery,
  StatsResponse,
} from '@/types/api'

export async function fetchRepositories(query: RepositoryQuery = {}): Promise<RepositoryListResponse> {
  const params = { ...query }
  if (params.category === '') delete params.category
  if (params.language === '') delete params.language
  if (params.min_stars == null) delete params.min_stars
  const { data } = await http.get<RepositoryListResponse>('/repositories', { params })
  return data
}

export async function fetchRepositoryDetail(
  owner: string,
  name: string,
  signal?: AbortSignal,
): Promise<RepositoryDetail> {
  const { data } = await http.get<RepositoryDetail>(
    `/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`,
    { signal },
  )
  return data
}

export async function fetchLanguages(): Promise<LanguageStat[]> {
  const { data } = await http.get<LanguageStat[]>('/languages')
  return data
}

export async function fetchStats(): Promise<StatsResponse> {
  const { data } = await http.get<StatsResponse>('/stats')
  return data
}
