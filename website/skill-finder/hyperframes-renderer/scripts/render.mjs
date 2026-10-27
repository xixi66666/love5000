import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {validateManifest, localFile} from './manifest.mjs';
import {demoManifest, renderComposition} from './composition.mjs';
import {inspectTemplate, withCsp} from './template.mjs';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const project = path.resolve(process.env.HYPERFRAMES_TEMPLATE_DIR || renderer);
const input = process.argv[2];
const demo = process.argv.includes('--demo'), check = process.argv.includes('--check');
if (!input) throw new Error('Usage: node scripts/render.mjs <render-manifest.json> [--check] [--demo]');
const directory = path.dirname(path.resolve(input));
const workers = Number(process.env.HYPERFRAMES_CONCURRENCY || '1');
if (!Number.isInteger(workers) || workers < 1 || workers > 8) throw new Error('HYPERFRAMES_CONCURRENCY must be 1..8');

export function executable(command) {
  if (path.isAbsolute(command)) {
    if (!fs.statSync(command).isFile()) throw new Error('Executable is not a file');
    return command;
  }
  for (const folder of (process.env.PATH || '').split(path.delimiter)) {
    for (const suffix of process.platform === 'win32' ? ['', '.exe', '.cmd'] : ['']) {
      const candidate = path.join(folder, command + suffix);
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    }
  }
  throw new Error(`Required executable is unavailable: ${path.basename(command)}`);
}

let lastProgress = 0;
function progress(value, force = false) {
  if (!force && Date.now() - lastProgress < 400) return;
  lastProgress = Date.now();
  const filename = path.join(directory, 'render-progress.json');
  fs.writeFileSync(`${filename}.tmp`, JSON.stringify({...value, updated_at: new Date().toISOString()}));
  fs.renameSync(`${filename}.tmp`, filename);
}

function run(command, args) {
  const result = spawnSync(command, args, {encoding: 'utf8', timeout: 600000, windowsHide: true, maxBuffer: 4 * 1024 * 1024});
  if (result.error || result.status !== 0) throw new Error('Media command failed');
  return result.stdout;
}

let stage;
try {
  fs.mkdirSync(directory, {recursive: true});
  progress({phase: 'preparing', rendered_frames: 0, total_frames: 0}, true);
  const browser = process.env.HYPERFRAMES_BROWSER_EXECUTABLE
    ? executable(process.env.HYPERFRAMES_BROWSER_EXECUTABLE)
    : ['chromium', 'chromium-browser', 'google-chrome', 'chrome'].map(name => {
      try { return executable(name); } catch { return undefined; }
    }).find(Boolean);
  if (!browser) throw new Error('Configure HYPERFRAMES_BROWSER_EXECUTABLE with an installed Chromium');
  const ffmpeg = executable(process.env.HYPERFRAMES_FFMPEG_COMMAND || 'ffmpeg');
  const ffprobe = executable(process.env.HYPERFRAMES_FFPROBE_COMMAND || 'ffprobe');
  // 官方 API 会读取这两个明确支持的二进制变量，禁止隐式下载。
  process.env.HYPERFRAMES_FFMPEG_PATH = ffmpeg;
  process.env.HYPERFRAMES_FFPROBE_PATH = ffprobe;
  const manifest = demo ? demoManifest() : validateManifest(JSON.parse(fs.readFileSync(input, 'utf8')), {allowSilent: check});
  const defaults = JSON.parse(fs.readFileSync(path.join(project, 'src/template-defaults.json'), 'utf8'));
  const template = fs.readFileSync(path.join(project, demo ? 'src/demo.html' : 'src/template.html'), 'utf8');
  inspectTemplate(template);
  stage = fs.mkdtempSync(path.join(directory, '.hyperframes-project-'));
  fs.copyFileSync(path.join(renderer, 'node_modules/gsap/dist/gsap.min.js'), path.join(stage, 'gsap.min.js'));
  const resources = new Set(['gsap.min.js']);
  let serial = 0;
  const freeze = filename => {
    const original = localFile(directory, filename);
    const extension = path.extname(original).toLowerCase();
    if (!['.wav', '.mp3', '.mp4', '.png', '.jpg', '.jpeg', '.ttf', '.ttc', '.otf'].includes(extension)) throw new Error('Unsupported manifest media');
    const name = `media-${serial++}${extension}`;
    fs.copyFileSync(original, path.join(stage, name));
    resources.add(name);
    return name;
  };
  for (const scene of manifest.scenes) {
    if (scene.audio) scene.audio = freeze(scene.audio);
    if (scene.asset) scene.asset.src = freeze(scene.asset.src);
  }
  if (manifest.font) manifest.font = freeze(manifest.font);
  const composition = renderComposition(template, manifest, defaults, {demo});
  inspectTemplate(composition.html, {generated: true, resources});
  fs.writeFileSync(path.join(stage, 'index.html'), withCsp(composition.html));
  const {createRenderJob, executeRenderJob, resolveConfig, createFileServer,
    createCaptureSession, initializeSession, captureFrameToBuffer, closeCaptureSession} = await import('@hyperframes/producer');
  const config = resolveConfig({fps: {num: 30, den: 1}, quality: 'high', chromePath: browser, concurrency: workers,
    browserGpuMode: 'software', forceScreenshot: true, useDrawElement: false,
    enableBrowserPool: false, enableChunkedEncode: false, lowMemoryMode: true});
  const totalFrames = Math.round(composition.duration * 30);
  if (check) {
    progress({phase: 'checking', rendered_frames: 0, total_frames: 1}, true);
    const server = await createFileServer({projectDir: stage, fps: {num: 30, den: 1}});
    let session;
    try {
      session = await createCaptureSession(server.url, stage,
        {width: composition.width, height: composition.height, fps: {num: 30, den: 1}, format: 'png'}, null, config);
      await initializeSession(session);
      const frame = Math.min(45, totalFrames - 1);
      const capture = await captureFrameToBuffer(session, frame, frame / 30);
      fs.writeFileSync(path.join(directory, 'poster.png'), capture.buffer);
    } finally {
      if (session) await closeCaptureSession(session);
      server.close();
    }
  } else {
    const output = path.join(directory, demo ? 'demo.mp4' : 'video.mp4');
    const job = createRenderJob({fps: 30, quality: 'high', format: 'mp4', workers,
      crf: 18, hdrMode: 'force-sdr', strictness: 'strict', producerConfig: config});
    await executeRenderJob(job, stage, output, current => {
      progress({phase: current.status, rendered_frames: current.framesRendered ?? 0,
        total_frames: current.totalFrames ?? 0});
    });
    if (job.status !== 'complete') throw new Error('HyperFrames did not complete');
    // 保留官方渲染的视频帧，只统一交付音轨格式；演示片附静音轨，不合成假人声。
    progress({phase: 'audio_format', rendered_frames: job.framesRendered ?? totalFrames, total_frames: job.totalFrames ?? totalFrames}, true);
    const standardized = path.join(directory, '.hyperframes-audio.mp4');
    const probe = JSON.parse(run(ffprobe, ['-v', 'quiet', '-show_streams', '-of', 'json', output]));
    const hasAudio = probe.streams.some(stream => stream.codec_type === 'audio');
    if (!hasAudio && !demo) throw new Error('Narration audio missing from rendered video');
    run(ffmpeg, ['-y', '-v', 'error', '-i', output, ...(!hasAudio ? ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'] : []),
      '-map', '0:v:0', '-map', hasAudio ? '0:a:0' : '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
      '-t', String(totalFrames / 30), '-movflags', '+faststart', standardized]);
    fs.renameSync(standardized, output);
    run(ffmpeg, ['-y', '-v', 'error', '-ss', String(Math.min(1.5, (totalFrames - 1) / 30)), '-i', output,
      '-frames:v', '1', path.join(directory, 'poster.png')]);
  }
  const result = {renderer: 'hyperframes', engine_version: '0.8.186', width: composition.width,
    height: composition.height, fps: 30, duration_seconds: totalFrames / 30,
    scenes: manifest.scenes.length, template_revision: manifest.template_revision ?? 'base',
    missing_assets: manifest.scenes.filter(scene => scene.heading.includes('/') && !scene.asset).length};
  fs.writeFileSync(path.join(directory, 'render-raw-result.json'), JSON.stringify(result, null, 2));
  progress({phase: 'completed', rendered_frames: check ? 1 : totalFrames, total_frames: check ? 1 : totalFrames}, true);
  console.log(JSON.stringify(result));
} catch (error) {
  progress({phase: 'failed', rendered_frames: 0, total_frames: 0}, true);
  // 上游异常可能含文件路径或媒体 URL；接口与终端只输出固定边界信息。
  console.error(`HyperFrames render failed: ${error.name}`);
  process.exitCode = 1;
} finally {
  // 只清理本脚本刚创建的隔离stage，既有日报素材/审核记录保持原样。
  if (stage && path.dirname(stage) === directory && path.basename(stage).startsWith('.hyperframes-project-')) {
    fs.rmSync(stage, {recursive: true, force: true});
  }
}
