import {escapeHtml as e} from './manifest.mjs';

export const templateFiles = ['src/template.html', 'src/demo.html', 'src/template-defaults.json'];
export const placeholders = ['WIDTH', 'HEIGHT', 'DURATION', 'DAY', 'SCENES', 'THEME_CSS', 'FONT_CSS'];

export function themeValues(input = {}, defaults = {}) {
  const known = ['accent', 'background', 'foreground', 'headlineSize', 'captionSize', 'captionBottom',
    'safeRight', 'mediaTop', 'motion', 'brand', 'tagline'];
  const value = Object.fromEntries(known.map(key => [key, input[key] ?? defaults[key]]));
  for (const name of ['accent', 'background', 'foreground']) {
    if (!/^#[a-fA-F0-9]{6}$/.test(value[name] ?? '')) throw new Error('Invalid theme color');
  }
  const ranges = {headlineSize: [40, 120], captionSize: [28, 80], captionBottom: [100, 500],
    safeRight: [50, 240], mediaTop: [450, 950], motion: [0, 2]};
  for (const [key, [min, max]] of Object.entries(ranges)) {
    if (!Number.isFinite(value[key]) || value[key] < min || value[key] > max) throw new Error('Invalid theme number');
  }
  for (const key of ['brand', 'tagline']) if (typeof value[key] !== 'string' || value[key].length > 120) throw new Error('Invalid brand');
  return value;
}

// 仅改变同一条实测字幕的排版，不能据此生成新的播放时间。
export function captionLayout(text, width, size) {
  const units = value => Array.from(value).reduce((sum, char) => sum + (/[\u0000-\u00ff]/u.test(char) ? .56 : 1), 0);
  const clean = text.replace(/\s+/gu, ' ').trim();
  if (units(clean) * size <= width) return {text: clean, size};
  const chars = Array.from(clean);
  let split = 1, score = Infinity;
  for (let index = 1; index < chars.length; index++) {
    const left = chars.slice(0, index).join(''), right = chars.slice(index).join('');
    const insideWord = /[a-z0-9]$/i.test(left) && /^[a-z0-9]/i.test(right);
    const badPunctuation = /^[，。！？、：；,.!?;:]/u.test(right);
    const cost = Math.max(units(left), units(right)) + (insideWord ? 4 : 0) + (badPunctuation ? 4 : 0);
    if (cost < score) {score = cost; split = index;}
  }
  const lines = [chars.slice(0, split).join('').trim(), chars.slice(split).join('').trim()];
  return {text: lines.join('\n'), size: Math.min(size, Math.floor(width / Math.max(...lines.map(units))))};
}

export function renderComposition(template, manifest, defaults, {demo = false} = {}) {
  const width = 1080, height = demo ? 720 : 1920;
  const duration = manifest.scenes.reduce((total, scene) => total + scene.durationInFrames / 30, 0);
  const theme = themeValues(manifest.theme, defaults);
  const captionHeight = theme.captionSize * 2.9 + 24;
  const mediaHeight = Math.max(280, Math.min(660, height - theme.captionBottom - captionHeight - 100 - theme.mediaTop));
  const css = Object.entries(theme).filter(([key]) => !['brand', 'tagline'].includes(key))
    .map(([key, value]) => `--${key}:${value}${typeof value === 'number' && key !== 'motion' ? 'px' : ''};`).join('')
    + `--mediaHeight:${mediaHeight}px;`;
  let offset = 0;
  const scenes = manifest.scenes.map((scene, index) => {
    const start = offset, length = scene.durationInFrames / 30;
    offset += length;
    const asset = scene.asset ? scene.asset.kind === 'video'
      ? `<video id="video-${index}" class="source-media" src="${e(scene.asset.src)}" data-start="${start}" data-duration="${length}" data-track-index="2" muted playsinline preload="auto"></video>`
      : `<img class="source-media" src="${e(scene.asset.src)}" alt="" />`
      : `<div class="editorial-art"><span>${e(String(index + 1).padStart(2, '0'))}</span><strong>${e(scene.label)}</strong><div class="art-rule"></div><small>AI PROJECT BRIEF</small></div>`;
    const captions = scene.captions.map(cue => {
      const layout = captionLayout(cue.text, width - 76 - theme.safeRight - 44, theme.captionSize);
      return `<div class="caption" style="font-size:${layout.size}px" data-cue-start="${cue.start}" data-cue-end="${cue.end}">${e(layout.text)}</div>`;
    }).join('');
    const titleSize = Math.min(theme.headlineSize, Math.max(48, (theme.mediaTop - 245 - 110) / 2.2));
    const title = captionLayout(scene.heading, (demo ? 710 : width - 76 - theme.safeRight) * .97, titleSize);
    const summaryTop = Math.max(440, 245 + title.size * 2.2 + 18);
    const summaryLines = Math.max(1, Math.min(3, Math.floor((theme.mediaTop - summaryTop - 22) / 49.6)));
    return `<section id="scene-${index}" class="scene" data-start="${start}" data-duration="${length}" data-track-index="0">
      <header><span class="brand">${e(theme.brand)}</span><span class="date">${e(manifest.day)}</span></header>
      <div class="label">${e(scene.label)}<span class="counter">${String(index + 1).padStart(2, '0')} / ${String(manifest.scenes.length).padStart(2, '0')}</span></div>
      <h1 style="font-size:${title.size}px;white-space:pre-line">${e(title.text)}</h1><p class="summary" style="top:${summaryTop}px;-webkit-line-clamp:${summaryLines}">${e(scene.summary)}</p>
      <div class="media-window">${asset}<div class="media-rule"></div></div>
      <div class="source">${scene.asset ? `来源 ${e(scene.asset.source)}` : '文字说明 · 未提供来源演示素材'}</div>
      <div class="captions">${captions}</div><footer><span>${e(theme.tagline)}</span><b>SKILL / FINDER</b></footer>
      <div class="scene-progress"></div>
      ${scene.audio ? `<audio id="voice-${index}" src="${e(scene.audio)}" data-start="${start}" data-duration="${length}" data-track-index="10" preload="auto"></audio>` : ''}
    </section>`;
  }).join('\n');
  const values = {WIDTH: width, HEIGHT: height, DURATION: duration, DAY: e(manifest.day), SCENES: scenes,
    THEME_CSS: `:root{${css}}`, FONT_CSS: manifest.font ? `@font-face{font-family:Daily;src:url("${e(manifest.font)}")}body{font-family:Daily,sans-serif}` : ''};
  return {html: template.replace(/\{\{([A-Z_]+)\}\}/g, (token, name) => {
    if (!(name in values)) throw new Error(`Unknown template placeholder: ${name}`);
    return String(values[name]);
  }), width, height, duration};
}

export function demoManifest() {
  return {day: '本地引擎能力演示', scenes: [
    {heading: '把发现，做成作品。', label: 'HYPERFRAMES / 01', summary: 'HTML 排版 · GSAP 精确时间线 · 本地自动渲染', narration: '', durationInFrames: 90, captions: []},
    {heading: '从脚本到动态画面。', label: 'HYPERFRAMES / 02', summary: '纸白、橙色、墨黑。保留一键制作与可编辑模板。', narration: '', durationInFrames: 90, captions: []},
    {heading: '真实素材，真实时间。', label: 'HYPERFRAMES / 03', summary: '独立渲染引擎对比样片 · 无配音调用 · 无外部素材', narration: '', durationInFrames: 90, captions: []},
  ]};
}
