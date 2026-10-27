export type TemplateEngine = 'remotion' | 'hyperframes'

export interface TemplateTheme {
  accent: string
  background: string
  foreground: string
  brand: string
  tagline: string
  headlineSize: number
  captionSize: number
  captionBottom: number
  safeRight: number
  mediaTop: number
  motion: number
}
export interface TemplateDocument {
  engine?: TemplateEngine
  engine_label?: string
  current_engine?: string
  revision: string
  theme: TemplateTheme
  defaults: TemplateTheme
  sources: { path: string; code: string; editable: boolean }[]
  versions: { revision: string; created_at: string; engine?: TemplateEngine }[]
  fields: {
    key: keyof TemplateTheme
    label: string
    kind: 'color' | 'text' | 'number'
    min?: number
    max?: number
    step?: number
    maxLength?: number
  }[]
}
export interface TemplatePreview {
  engine?: TemplateEngine
  id: string
  revision: string
  created_at: string
  props: {
    day: string
    theme: TemplateTheme
    font?: string
    scenes: {
      audio?: string
      asset?: { src: string }
      [key: string]: unknown
    }[]
  }
}
export interface CompileDiagnostic {
  file: string
  line: number
  column: number
  message: string
}
