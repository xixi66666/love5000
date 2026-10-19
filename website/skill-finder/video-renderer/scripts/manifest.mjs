import fs from 'node:fs';
import path from 'node:path';

export function validateManifest(value, {allowSilent = false} = {}) {
  if (!value || typeof value.day !== 'string' || !Array.isArray(value.scenes) ||
      value.scenes.length < 1 || value.scenes.length > 30) throw new Error('Invalid scene manifest');
  let frames = 0;
  for (const scene of value.scenes) {
    if (typeof scene.heading !== 'string' || typeof scene.summary !== 'string' ||
        !Number.isInteger(scene.durationInFrames) || scene.durationInFrames < 1 ||
        scene.durationInFrames > 30 * 600 || !Array.isArray(scene.captions)) throw new Error('Invalid scene');
    if (typeof scene.audio !== 'string' && !allowSilent) throw new Error('Narration audio is required');
    for (const cue of scene.captions) {
      if (typeof cue.text !== 'string' || !Number.isFinite(cue.start) || !Number.isFinite(cue.end) ||
          cue.start < 0 || cue.end <= cue.start || cue.end > scene.durationInFrames / 30 + 0.1) {
        throw new Error('Invalid caption timing');
      }
    }
    frames += scene.durationInFrames;
  }
  if (frames > 30 * 1800) throw new Error('Video exceeds 30 minutes');
  return value;
}

export function localFile(root, name) {
  if (typeof name !== 'string' || path.isAbsolute(name) || /[?#\x00]/.test(name)) throw new Error('Invalid media path');
  const resolvedRoot = fs.realpathSync(root);
  const resolved = fs.realpathSync(path.resolve(root, name));
  const relative = path.relative(resolvedRoot, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || !fs.statSync(resolved).isFile()) {
    throw new Error('Media must stay within the report directory');
  }
  return resolved;
}
