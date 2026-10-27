import fs from 'node:fs';
import path from 'node:path';

export function validateManifest(value, {allowSilent = false} = {}) {
  if (!value || typeof value.day !== 'string' || value.day.length > 120 || !Array.isArray(value.scenes) ||
      value.scenes.length < 1 || value.scenes.length > 30) throw new Error('Invalid scene manifest');
  let frames = 0;
  for (const scene of value.scenes) {
    for (const field of ['heading', 'label', 'summary', 'narration']) {
      if (typeof scene[field] !== 'string' || scene[field].length > 5000) throw new Error('Invalid scene text');
    }
    if (!Number.isInteger(scene.durationInFrames) || scene.durationInFrames < 1 ||
        scene.durationInFrames > 30 * 600 || !Array.isArray(scene.captions)) throw new Error('Invalid scene');
    if (typeof scene.audio !== 'string' && !allowSilent) throw new Error('Narration audio is required');
    let lastEnd = 0;
    for (const cue of scene.captions) {
      if (typeof cue.text !== 'string' || cue.text.length > 1000 || !Number.isFinite(cue.start) ||
          !Number.isFinite(cue.end) || cue.start < lastEnd - 0.01 || cue.start < 0 ||
          cue.end <= cue.start || cue.end > scene.durationInFrames / 30 + 0.1) throw new Error('Invalid caption timing');
      lastEnd = cue.end;
    }
    if (scene.asset && (!['image', 'video'].includes(scene.asset.kind) ||
        typeof scene.asset.src !== 'string' || typeof scene.asset.source !== 'string' ||
        !/^https:\/\/[^\s<>]+$/.test(scene.asset.source))) throw new Error('Invalid source asset');
    frames += scene.durationInFrames;
  }
  if (frames > 30 * 1800) throw new Error('Video exceeds 30 minutes');
  return value;
}

export function localFile(root, name) {
  if (typeof name !== 'string' || !name || path.isAbsolute(name) || /[?#\x00:]/.test(name)) throw new Error('Invalid media path');
  const resolvedRoot = fs.realpathSync(root);
  const resolved = fs.realpathSync(path.resolve(root, name));
  const relative = path.relative(resolvedRoot, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || !fs.statSync(resolved).isFile()) {
    throw new Error('Media must stay within the report directory');
  }
  return resolved;
}

// 文本永远经HTML转义，不能把日报标题/字幕变成作者代码。
export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
}
