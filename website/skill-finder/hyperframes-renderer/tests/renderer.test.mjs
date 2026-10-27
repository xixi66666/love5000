import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import test from 'node:test';
import {parseHTML} from 'linkedom';
import {validateManifest, localFile} from '../scripts/manifest.mjs';
import {captionLayout, demoManifest, renderComposition} from '../scripts/composition.mjs';
import {inspectTemplate, withCsp} from '../scripts/template.mjs';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const defaults = JSON.parse(fs.readFileSync(path.join(renderer, 'src/template-defaults.json'), 'utf8'));
const template = fs.readFileSync(path.join(renderer, 'src/template.html'), 'utf8');
const manifest = () => ({day: '模板验收', scenes: [{heading: '项目标题', label: 'TOOL', summary: '用途与限制',
  narration: '实际口播', audio: 'voice.wav', durationInFrames: 120,
  captions: [{text: '实际字幕', start: .2, end: 3.5}],
  asset: {kind: 'video', src: 'source.mp4', source: 'https://github.com/example/tool', durationInFrames: 30}}]});

test('rejects overlapping or out-of-range captions instead of altering timing', () => {
  for (const cues of [[{text: '越界', start: 0, end: 5}],
    [{text: '前句', start: 0, end: 2}, {text: '重叠', start: 1, end: 3}]]) {
    const value = manifest(); value.scenes[0].captions = cues;
    assert.throws(() => validateManifest(value), /caption timing/);
  }
  const value = manifest(), before = structuredClone(value);
  validateManifest(value); assert.deepEqual(value, before);
});

test('production requires narration; one-frame template checks can be silent', () => {
  const value = manifest(); delete value.scenes[0].audio;
  assert.throws(() => validateManifest(value), /Narration/);
  assert.equal(validateManifest(value, {allowSilent: true}), value);
});

test('manifest paths cannot read outside the report or through a symlink', t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'hf-path-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const report = path.join(directory, 'report'); fs.mkdirSync(report);
  fs.writeFileSync(path.join(directory, 'private.wav'), 'private');
  fs.writeFileSync(path.join(report, 'voice.wav'), 'voice');
  assert.equal(localFile(report, 'voice.wav'), fs.realpathSync(path.join(report, 'voice.wav')));
  for (const name of ['../private.wav', 'voice.wav?token=private', 'C:/private.wav', 'file:///private.wav']) {
    assert.throws(() => localFile(report, name));
  }
  // Windows 目录联接无需创建文件符号链接所需的管理员权限。
  fs.symlinkSync(directory, path.join(report, 'outside'), process.platform === 'win32' ? 'junction' : 'dir');
  assert.throws(() => localFile(report, 'outside/private.wav'), /within the report/);
});

test('article text is escaped and unknown theme fields cannot inject CSS', () => {
  const value = manifest(); value.scenes[0].heading = '<img src=x onerror=alert(1)>';
  value.scenes[0].captions[0].text = '</div><script>alert(1)</script>';
  value.theme = {injected: 'red;}body{display:none'};
  const result = renderComposition(template, value, defaults);
  const {document} = parseHTML(result.html);
  assert.equal(document.querySelector('h1').textContent.replace(/\s/g, ''), value.scenes[0].heading.replace(/\s/g, ''));
  assert.equal(document.querySelectorAll('[onerror]').length, 0);
  assert.ok(!result.html.includes('<script>alert(1)</script>'));
  assert.ok(!result.html.includes('--injected'));
  assert.throws(() => renderComposition(template, {...value, theme: {accent: 'red;display:none'}}, defaults), /theme color/);
});

test('Chinese headings balance both lines without leaving a single trailing character', () => {
  const value = manifest(); value.scenes[0].heading = '每天的视频，交给模板。';
  const {document} = parseHTML(renderComposition(template, value, defaults).html);
  const lines = document.querySelector('h1').textContent.split('\n');
  assert.equal(lines.join(''), value.scenes[0].heading);
  assert.equal(lines.length, 2);
  assert.ok(lines.every(line => line.length >= 4));
});

test('audio and scene offsets use real frame durations; short source videos do not loop', () => {
  const value = manifest(); value.scenes.push(structuredClone(value.scenes[0]));
  const result = renderComposition(template, value, defaults);
  const {document} = parseHTML(result.html);
  assert.equal(result.duration, 8);
  assert.equal(document.querySelector('#voice-1').dataset.start, '4');
  assert.equal(document.querySelector('#video-1').dataset.duration, '4');
  assert.equal(document.querySelectorAll('video[loop]').length, 0);
  assert.equal(document.querySelector('.caption').dataset.cueEnd, '3.5');
});

test('long mixed-language captions keep every character in at most two lines', () => {
  const text = '通过 HyperFrames 模板自动生成视频，同时保留实际来源和字幕时间。';
  const layout = captionLayout(text, 680, 68);
  assert.equal(layout.text.replace(/\s/g, ''), text.replace(/\s/g, ''));
  assert.ok(layout.text.split('\n').length <= 2);
  assert.ok(layout.size > 0 && layout.size <= 68);
});

test('theme extremes leave room between media, source and captions', () => {
  const value = manifest(); value.theme = {...defaults, captionSize: 68, captionBottom: 420, mediaTop: 700};
  const {html} = renderComposition(template, value, defaults);
  const mediaHeight = Number(/--mediaHeight:(\d+(?:\.\d+)?)px/.exec(html)[1]);
  assert.ok(700 + mediaHeight + 80 <= 1920 - 420 - (68 * 2.9 + 24));
});

for (const fragment of ['<iframe src="https://example.com"></iframe>',
  '<img src="file:///private.png">', '<img srcset="https://example.com/a.png 2x">',
  '<style>@import "https://example.com/a.css";</style>',
  '<style>body{background:url(https://example.com/a.png)}</style>',
  '<script src="https://example.com/a.js"></script>', '<div onclick="alert(1)"></div>']) {
  test(`template validator rejects external or executable resource: ${fragment.slice(0, 55)}`, () => {
    assert.throws(() => inspectTemplate(template.replace('</body>', `${fragment}</body>`)));
  });
}

test('generated font/media whitelist is explicit and CSP blocks network access', () => {
  const value = manifest(); value.font = 'font.ttc';
  const {html} = renderComposition(template, value, defaults);
  assert.doesNotThrow(() => inspectTemplate(html, {generated: true,
    resources: new Set(['gsap.min.js', 'voice.wav', 'source.mp4', 'font.ttc'])}));
  assert.throws(() => inspectTemplate(html, {generated: true}));
  assert.ok(withCsp(html).includes("connect-src 'none'"));
  assert.ok(html.lastIndexOf('font-family:Daily,sans-serif') > html.lastIndexOf('font-family:sans-serif'));
  assert.ok(!html.includes('Arial') && !html.includes('Microsoft YaHei'));
  assert.equal(demoManifest().scenes.reduce((total, scene) => total + scene.durationInFrames, 0), 270);
});

test('editor builds external JavaScript without eval and reports invalid authored source', t => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'hf-editor-'));
  t.after(() => fs.rmSync(project, {recursive: true, force: true}));
  fs.cpSync(path.join(renderer, 'src'), path.join(project, 'src'), {recursive: true});
  const build = () => {
    const result = spawnSync(process.execPath, [path.join(renderer, 'scripts/build-editor.mjs'), project], {encoding: 'utf8'});
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(fs.readFileSync(path.join(project, 'diagnostics.json'), 'utf8'));
  };
  assert.equal(build().ok, true);
  const source = fs.readFileSync(path.join(project, 'preview/app.js'), 'utf8');
  assert.doesNotThrow(() => new vm.Script(source));
  assert.ok(!/\beval\s*\(|new Function\s*\(/.test(source));
  fs.writeFileSync(path.join(project, 'src/template.html'), template.replace('const timeline =', 'const ='));
  const invalid = build();
  assert.equal(invalid.ok, false);
  assert.equal(invalid.diagnostics[0].file, 'src/template.html');
});
