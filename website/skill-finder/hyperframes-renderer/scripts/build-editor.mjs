import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import {inspectTemplate} from './template.mjs';
import {escapeHtml} from './manifest.mjs';
import {renderComposition, themeValues, demoManifest, captionLayout} from './composition.mjs';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
if (!process.argv[2]) throw new Error('Usage: node scripts/build-editor.mjs <template-project>');
const project = path.resolve(process.argv[2]);
const diagnostics = [];
try {
  const defaults = JSON.parse(fs.readFileSync(path.join(project, 'src/template-defaults.json'), 'utf8'));
  themeValues({}, defaults);
  const files = ['src/template.html', 'src/demo.html'];
  const templates = [], programs = [];
  for (const filename of files) {
    const source = fs.readFileSync(path.join(project, filename), 'utf8');
    try {
      const {scripts} = inspectTemplate(source);
      renderComposition(source, demoManifest(), defaults, {demo: filename.endsWith('demo.html')});
      templates.push(source);
      programs.push(`function authored${programs.length}(){\n${scripts.join('\n;\n')}\n}`);
    } catch (error) {
      diagnostics.push({file: filename, line: Number(/template.html:(\d+)/.exec(error.stack)?.[1] || 1),
        column: 1, message: String(error.message).slice(0, 600)});
    }
  }
  if (!diagnostics.length) {
    const gsap = fs.readFileSync(path.join(renderer, 'node_modules/gsap/dist/gsap.min.js'), 'utf8');
    const source = `${gsap}\n(() => {\nconst e=${escapeHtml.toString()};\nconst themeValues=${themeValues.toString()};\nconst captionLayout=${captionLayout.toString()};\nconst renderComposition=${renderComposition.toString()};\nconst demoManifest=${demoManifest.toString()};\nconst templates=${JSON.stringify(templates)};\nconst defaults=${JSON.stringify(defaults)};\n${programs.join('\n')}\n${previewRuntime.toString()}\npreviewRuntime();\n})();`;
    new vm.Script(source, {filename: 'app.js'});
    fs.mkdirSync(path.join(project, 'preview'), {recursive: true});
    fs.writeFileSync(path.join(project, 'preview/app.js'), source);
  }
} catch (error) {
  diagnostics.push({file: 'template', line: 1, column: 1, message: String(error.message).slice(0, 600)});
}
fs.writeFileSync(path.join(project, 'diagnostics.json'), JSON.stringify({ok: diagnostics.length === 0, diagnostics}));

// 此函数编译到外部 app.js；无 eval、内联脚本或具有同源权限的子iframe。
function previewRuntime() {
  let data, playing = false, currentTime = 0, lastFrame = 0;
  let stage, slider, clock, playButton, duration = 1;
  function notify(error) {
    window.parent.postMessage({kind: 'sf-template-error', message: String(error.message || error).slice(0, 400)}, '*');
  }
  function seek(time) {
    currentTime = Math.max(0, Math.min(time, duration - 1 / 30));
    for (const timeline of Object.values(window.__timelines || {})) timeline.pause().seek(currentTime, false);
    for (const media of stage.querySelectorAll('audio,video')) {
      const start = Number(media.dataset.start || 0), length = Number(media.dataset.duration || duration);
      const active = currentTime >= start && currentTime < start + length;
      const localTime = Math.max(0, Math.min(currentTime - start, Math.max(0, (media.duration || length) - .04)));
      if (!active || !playing) {media.pause(); if (Math.abs(media.currentTime - localTime) > .04) media.currentTime = localTime;}
      else {
        if (Math.abs(media.currentTime - localTime) > .25) media.currentTime = localTime;
        media.play().catch(() => {});
      }
    }
    slider.value = String(currentTime);
    clock.textContent = `${currentTime.toFixed(1)} / ${duration.toFixed(1)}s`;
  }
  function resize() {
    if (!stage || !data) return;
    const height = data.demo ? 720 : 1920;
    const scale = Math.max(.01, Math.min(window.innerWidth / 1080, (window.innerHeight - 48) / height));
    stage.style.transform = `scale(${scale})`;
    stage.parentElement.style.height = `${height * scale}px`;
    stage.parentElement.style.width = `${1080 * scale}px`;
  }
  function mount(value) {
    data = value; playing = false; currentTime = 0;
    for (const timeline of Object.values(window.__timelines || {})) timeline.kill();
    const props = data.demo ? {...demoManifest(), theme: data.props.theme} : data.props;
    const composition = renderComposition(templates[data.demo ? 1 : 0], props, defaults, {demo: data.demo});
    duration = composition.duration;
    const parsed = new DOMParser().parseFromString(composition.html, 'text/html');
    // 脚本已在构建时编译成函数，DOM中不保留可执行script标签。
    parsed.querySelectorAll('script').forEach(node => node.remove());
    document.querySelectorAll('style[data-template]').forEach(node => node.remove());
    for (const style of parsed.querySelectorAll('style')) {
      const tag = document.createElement('style'); tag.dataset.template = 'true'; tag.textContent = style.textContent;
      document.head.append(tag);
    }
    document.documentElement.style.cssText = 'width:100%;height:100%;overflow:hidden;background:#15191c';
    document.body.style.cssText = 'margin:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;flex-direction:column;overflow:hidden;background:#15191c';
    document.body.replaceChildren();
    const wrap = document.createElement('div'); wrap.style.cssText = 'position:relative;flex-shrink:0;overflow:hidden';
    stage = document.createElement('div'); stage.style.cssText = 'position:absolute;left:0;top:0;transform-origin:top left;width:1080px';
    for (const node of [...parsed.body.childNodes]) stage.append(document.importNode(node, true));
    wrap.append(stage); document.body.append(wrap);
    const controls = document.createElement('div');
    controls.style.cssText = 'height:44px;display:flex;gap:12px;align-items:center;justify-content:center;width:100%;padding:6px 14px;color:#fff;font:12px Arial;background:#15191c';
    playButton = document.createElement('button'); playButton.textContent = '播放';
    playButton.addEventListener('click', () => {playing = !playing; playButton.textContent = playing ? '暂停' : '播放'; if (currentTime >= duration-.05) currentTime = 0; seek(currentTime);});
    slider = document.createElement('input'); slider.type = 'range'; slider.min = '0'; slider.max = String(duration-1/30); slider.step = String(1/30); slider.style.width = '55%';
    slider.addEventListener('input', () => seek(Number(slider.value)));
    clock = document.createElement('span'); controls.append(playButton, slider, clock); document.body.append(controls);
    (data.demo ? authored1 : authored0)();
    resize(); seek(0);
  }
  window.addEventListener('resize', resize);
  window.addEventListener('message', event => {
    if (event.source !== window.parent || event.data?.kind !== 'sf-template-props' || !Array.isArray(event.data.props?.scenes)) return;
    try {mount({props: event.data.props, demo: event.data.demo === true});} catch (error) {notify(error);}
  });
  window.addEventListener('error', event => notify(event.error || event.message));
  function animate(now) {
    if (playing && data) {
      const step = Math.min(.1, (now - lastFrame) / 1000);
      try {seek(currentTime + step);} catch (error) {playing = false; notify(error);}
      if (currentTime >= duration - 1 / 30) {playing = false; playButton.textContent = '播放'; seek(currentTime);}
    }
    lastFrame = now; requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
  window.parent.postMessage({kind: 'sf-template-ready'}, '*');
}
