import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {localFile, validateManifest} from './manifest.mjs';

const rendererProject = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const project = process.env.REMOTION_TEMPLATE_DIR || rendererProject;
const input = process.argv[2];
const demo = process.argv.includes('--demo');
const check = process.argv.includes('--check');
const concurrency = Number(process.env.REMOTION_CONCURRENCY || '2');
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 8) throw new Error('REMOTION_CONCURRENCY must be 1..8');
if (!input) throw new Error('Usage: node scripts/render.mjs <render-manifest.json>');
const directory = path.dirname(path.resolve(input));
// 能力演示只渲染工程自带 Composition，不依赖外部音频或项目素材。
const props = demo ? {day: '本地能力演示', scenes: []}
  : validateManifest(JSON.parse(fs.readFileSync(input, 'utf8')), {allowSilent: check});
const files = new Map();
let lastProgressWrite = 0;
const saveProgress = (value, force = false) => {
  if (!force && Date.now() - lastProgressWrite < 1000) return;
  lastProgressWrite = Date.now();
  const target = path.join(directory, 'render-progress.json');
  fs.writeFileSync(`${target}.tmp`, JSON.stringify({...value, updated_at: new Date().toISOString()}));
  fs.renameSync(`${target}.tmp`, target);
};
const token = randomBytes(18).toString('hex');
const mime = {'.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.ttc': 'font/collection', '.ttf': 'font/ttf'};
// 只暴露本次清单列出的媒体文件，随机路由令牌，不托管整个日报或私有数据目录。
const server = http.createServer((req, res) => {
  const filename = files.get(req.url);
  if (!filename) {res.writeHead(404); res.end(); return;}
  const size = fs.statSync(filename).size;
  let start = 0, end = size - 1;
  if (req.headers.range) {
    const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
    if (!range) {res.writeHead(416); res.end(); return;}
    start = Number(range[1]); end = range[2] ? Math.min(Number(range[2]), end) : end;
    if (start > end || start >= size) {res.writeHead(416); res.end(); return;}
  }
  res.writeHead(req.headers.range ? 206 : 200, {
    'Content-Type': mime[path.extname(filename).toLowerCase()] ?? 'application/octet-stream',
    'Content-Length': end - start + 1, 'Accept-Ranges': 'bytes',
    'Access-Control-Allow-Origin': '*',
    ...(req.headers.range ? {'Content-Range': `bytes ${start}-${end}/${size}`} : {}),
  });
  if (req.method === 'HEAD') {res.end(); return;}
  fs.createReadStream(filename, {start, end}).pipe(res);
});

try {
  await new Promise((resolve, reject) => {server.once('error', reject); server.listen(0, '127.0.0.1', resolve);});
  const port = server.address().port;
  const media = (name) => {
    const route = `/${token}/${files.size}`;
    files.set(route, localFile(directory, name));
    return `http://127.0.0.1:${port}${route}`;
  };
  for (const scene of props.scenes) {
    if (scene.audio) scene.audio = media(scene.audio);
    if (scene.asset) {
      if (!['image', 'video'].includes(scene.asset.kind) || typeof scene.asset.source !== 'string') throw new Error('Invalid source asset');
      scene.asset.src = media(scene.asset.src);
    }
  }
  if (props.font) props.font = media(props.font);
  saveProgress({phase: 'bundling', rendered_frames: 0, total_frames: 0}, true);
  const serveUrl = await bundle({entryPoint: path.join(project, 'src/index.ts'),
    outDir: path.join(directory, '.remotion-bundle'),
    webpackOverride: config => ({...config, resolve: {...config.resolve,
      modules: [path.join(rendererProject, 'node_modules'), ...(config.resolve?.modules ?? ['node_modules'])]}})});
  console.log('REMOTION_BUNDLE_READY');
  const common = {serveUrl, inputProps: props, browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || undefined,
    timeoutInMilliseconds: 120000, logLevel: 'error',
    offthreadVideoCacheSizeInBytes: 128 * 1024 * 1024, offthreadVideoThreads: 1};
  const composition = await selectComposition({...common, id: demo ? 'RenderDemo' : 'SkillFinderDaily'});
  console.log(`REMOTION_COMPOSITION_READY ${composition.durationInFrames} frames`);
  saveProgress({phase: 'rendering', rendered_frames: 0, total_frames: composition.durationInFrames}, true);
  if (!check) await renderMedia({...common, composition, codec: 'h264', audioCodec: 'aac', sampleRate: 48000,
    pixelFormat: 'yuv420p', concurrency, crf: 20, x264Preset: 'fast',
    outputLocation: path.join(directory, demo ? 'demo.mp4' : 'video.mp4'),
    onProgress: ({progress, renderedFrames, encodedFrames}) => {
      saveProgress({phase: 'rendering', rendered_frames: renderedFrames,
        encoded_frames: encodedFrames, total_frames: composition.durationInFrames});
      if (process.env.REMOTION_PROGRESS === '1') console.log(`RENDER ${Math.round(progress * 100)}%`);
    },
  });
  await renderStill({...common, composition, frame: Math.min(45, composition.durationInFrames - 1),
    output: path.join(directory, 'poster.png')});
  const result = {renderer: 'remotion', width: composition.width, height: composition.height,
    fps: composition.fps, duration_seconds: composition.durationInFrames / composition.fps,
    scenes: props.scenes.length,
    template_revision: props.template_revision ?? 'base',
    missing_assets: props.scenes.filter(s => s.heading.includes('/') && !s.asset).length};
  fs.writeFileSync(path.join(directory, 'render-result.json'), JSON.stringify(result, null, 2));
  saveProgress({phase: 'completed', rendered_frames: composition.durationInFrames,
    total_frames: composition.durationInFrames}, true);
  console.log(JSON.stringify(result));
} catch (error) {
  // 渲染器没有必要向调用方输出环境变量或完整浏览器异常。
  console.error(`Remotion render failed: ${error.name}`);
  process.exitCode = 1;
} finally {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
