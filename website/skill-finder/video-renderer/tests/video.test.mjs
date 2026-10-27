import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import test from 'node:test';
import assert from 'node:assert/strict';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const testRoot = path.join(renderer, '.test-tmp');
fs.mkdirSync(testRoot, {recursive: true});
const output = path.join(fs.mkdtempSync(path.join(testRoot, 'video-layout-')), 'video.cjs');
await build({entryPoints: [path.join(renderer, 'src/video.tsx')], outfile: output,
  bundle: true, platform: 'node', format: 'cjs', packages: 'external', logLevel: 'silent'});
const {activeCaption, captionLayout, sceneStage, sourceFrame, summaryExcerpt} = createRequire(import.meta.url)(output);
test.after(() => fs.rmSync(path.dirname(output), {recursive: true, force: true}));

test('scene shots change on a three second beat without changing the scene duration', () => {
  assert.equal(sceneStage(0, 450, 30), 0);
  assert.equal(sceneStage(89, 450, 30), 0);
  assert.equal(sceneStage(90, 450, 30), 1);
  assert.equal(sceneStage(180, 450, 30), 2);
  assert.equal(sceneStage(449, 450, 30), 2);
  assert.equal(sceneStage(60, 180, 30), 1);
});

test('a short source plays once then holds its last frame instead of looping', () => {
  assert.equal(sourceFrame(45, 90, 60), 0);
  assert.equal(sourceFrame(105, 90, 60), 15);
  assert.equal(sourceFrame(150, 90, 60), 59);
  assert.equal(sourceFrame(900, 90, 60), 59);
  assert.equal(sourceFrame(900, 90), 810);
});

test('remotion encodes limited-range BT.709 yuv420p for the shared acceptance check', () => {
  const source = fs.readFileSync(path.join(renderer, 'scripts/render.mjs'), 'utf8');
  assert.match(source, /pixelFormat: 'yuv420p'/);
  assert.match(source, /colorSpace: 'bt709'/);
});

test('caption selection respects supplier timing and actual gaps', () => {
  const cues = [{text: '真实时间', start: 0.4, end: 1.2}, {text: '保留间隔', start: 1.5, end: 2}];
  assert.equal(activeCaption(cues, 0.39), undefined);
  assert.equal(activeCaption(cues, 0.4)?.text, '真实时间');
  assert.equal(activeCaption(cues, 1.2), undefined);
  assert.equal(activeCaption(cues, 1.5)?.text, '保留间隔');
  assert.equal(activeCaption(cues, 2), undefined);
});

test('long bilingual captions stay within two lines and retain every character', () => {
  const text = '通过 Remotion 生成真正可编程的视频，保留完整的项目来源和演示画面。';
  const result = captionLayout(text, 818, 48);
  assert.equal(result.lines.length, 2);
  assert.equal(result.lines.join('').replace(/\s/gu, ''), text.replace(/\s/gu, ''));
  assert.ok(result.fontSize > 30 && result.fontSize <= 48);
  assert.ok(result.lines.every(line => !/^[，。！？、：；]/u.test(line)));
  assert.deepEqual(captionLayout('清晰字幕', 818, 48), {lines: ['清晰字幕'], fontSize: 48});
});

test('the screen excerpt is explicit and does not mutate the original project description', () => {
  const summary = '这是一段有来源的项目介绍。'.repeat(30);
  assert.ok(summaryExcerpt(summary, 76).endsWith('…'));
  assert.ok(Array.from(summaryExcerpt(summary, 76)).length <= 77);
  assert.equal(summary, '这是一段有来源的项目介绍。'.repeat(30));
  assert.equal(summaryExcerpt(' 简短描述。 '), '简短描述。');
});
