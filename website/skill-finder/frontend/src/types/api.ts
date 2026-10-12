export type Category = 'AGENT' | 'SKILL' | 'MCP' | 'PLUGIN'

export type SortKey = 'daily_stars' | 'weekly_stars' | 'monthly_stars' | 'total_stars'

export interface TrendPoint {
  snapshot_date: string
  stars_count: number
}

export interface RepositoryListItem {
  id: number
  owner: string
  name: string
  description: string | null
  html_url: string
  language: string | null
  topics: string[]
  categories: Category[]
  stars_count: number
  daily_stars: number | null
  weekly_stars: number | null
  monthly_stars: number | null
  last_synced_at: string | null
  trend: TrendPoint[]
}

export interface RepositoryListResponse {
  items: RepositoryListItem[]
  page: number
  page_size: number
  total: number
  last_successful_collection_at: string | null
}

export interface RepositoryIntroduction {
  introduction: string
  highlights: string[]
  requirements: string[]
  usage: string
  audience: string
  domains: string[]
}

export interface RepositoryDetail {
  id: number
  owner: string
  name: string
  description: string | null
  introduction: RepositoryIntroduction | null
  html_url: string
  homepage: string | null
  language: string | null
  topics: string[]
  categories: Category[]
  matched_rules: string[]
  stars_count: number
  forks_count: number
  open_issues_count: number
  daily_stars: number | null
  weekly_stars: number | null
  monthly_stars: number | null
  last_synced_at: string | null
  github_created_at: string | null
  trend: TrendPoint[]
}

export interface LanguageStat {
  language: string
  count: number
}

export interface StatsResponse {
  total_repositories: number
  positive_growth_today: number
  last_successful_collection_at: string | null
  last_run_status: string | null
}

export interface RepositoryQuery {
  page?: number
  page_size?: number
  sort?: SortKey
  category?: Category | ''
  language?: string | ''
  min_stars?: number | null
  q?: string
}
