import axios from 'axios'

export interface DailyProject {
  rank: number
  full_name: string
  url: string
  summary: string
  daily_stars: number
}
export interface DailyReport {
  date: string
  title?: string
  status: string
  publisher_status?: string
  qq_status?: string
  script?: string
  caption?: string
  review_digest?: string
  items: DailyProject[]
  item_count?: number
  completeness?: string
  render?: {
    width: number
    height: number
    fps: number
    duration_seconds: number
    tts_provider?: string
  }
}
export interface WorkflowStage {
  id: string
  label: string
  description: string
  status: string
  detail: string
  done: number
  total: number
  started_at?: string
  finished_at?: string
  error?: string
}
export interface ConsoleSnapshot {
  date: string
  today: string
  timezone: string
  status: string
  recorded: boolean
  workflow: {
    current: string | null
    updated_at: string
    stages: WorkflowStage[]
    events: { at: string; stage: string; status: string; message: string }[]
  }
  runtime: {
    id: string
    label: string
    value: string
    ready: boolean
    optional?: boolean
  }[]
  assets: {
    project: string
    status: string
    source: string
    filename: string
  }[]
  artifacts: { name: string; label: string; ready: boolean }[]
  render_progress: {
    phase: string
    rendered_frames: number
    total_frames: number
    updated_at: string
  } | null
  samples: {
    id: string
    duration_seconds: number
    width: number
    height: number
    fps: number
  }[]
  template: {
    composition: string
    width: number
    height: number
    fps: number
    directory: string
    editor_url: string
    api: string
    files: { path: string; description: string }[]
  }
}
export const dailyApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})
export function dailyFile(day: string, filename: string) {
  return `${dailyApi.defaults.baseURL}/daily-reports/${encodeURIComponent(day)}/files/${encodeURIComponent(filename)}`
}
export function sampleFile(id: string, filename: string) {
  return `${dailyApi.defaults.baseURL}/daily-reports/samples/${encodeURIComponent(id)}/files/${encodeURIComponent(filename)}`
}
