export type Cue = {text: string; start: number; end: number};
export type Scene = {
  heading: string;
  label: string;
  summary: string;
  narration: string;
  growth?: number;
  durationInFrames: number;
  audio?: string;
  captions: Cue[];
  asset?: {src: string; kind: 'image' | 'video'; source: string; durationInFrames?: number};
};
export type TemplateTheme = {
  accent: string; background: string; foreground: string; brand: string; tagline: string;
  headlineSize: number; captionSize: number; captionBottom: number; safeRight: number; mediaTop: number; motion: number;
};
export type DailyProps = {day: string; scenes: Scene[]; font?: string; preview?: boolean; theme?: TemplateTheme};
