'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../../main/resources/static/motion.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function eventTarget(target = {}) {
  const listeners = new Map();
  target.addEventListener = (name, callback) => {
    const callbacks = listeners.get(name) || [];
    callbacks.push(callback);
    listeners.set(name, callbacks);
  };
  target.emit = (name, detail = {}) => {
    (listeners.get(name) || []).forEach(callback => callback(detail));
  };
  return target;
}

function element() {
  const classes = new Set();
  const attributes = new Map();
  const properties = new Map();
  return eventTarget({
    dataset: {},
    children: [],
    contains(other) { return other === this || this.children.some(child => child.contains(other)); },
    style: { setProperty: (name, value) => properties.set(name, value) },
    properties,
    classList: {
      add: name => classes.add(name),
      remove: name => classes.delete(name),
      contains: name => classes.has(name),
      toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name)
    },
    setAttribute: (name, value) => attributes.set(name, value),
    getAttribute: name => attributes.get(name) || null
  });
}

function fixture(options = {}) {
  const scene = element();
  const label = { textContent: '' };
  const toggle = element();
  toggle.querySelector = () => label;
  const preference = eventTarget({ matches: Boolean(options.reduced) });
  const video = element();
  video.dataset.src = options.missingSource ? '' : '/media/motion-background.mp4';
  video.readyState = 0;
  video.paused = true;
  video.loadCalls = 0;
  video.playCalls = 0;
  video.pauseCalls = 0;
  let videoSource = '';
  Object.defineProperty(video, 'src', {
    get: () => videoSource,
    set: value => { videoSource = value; }
  });
  video.getAttribute = name => name === 'src' ? videoSource : null;
  video.load = () => { video.loadCalls += 1; };
  video.play = () => {
    video.playCalls += 1;
    if (options.rejectPlay) return Promise.reject(new Error('Autoplay denied'));
    video.paused = false;
    return Promise.resolve();
  };
  video.pause = () => { video.pauseCalls += 1; video.paused = true; };
  const elements = {
    'ambient-scene': scene,
    'ambient-video': options.missingVideo ? null : video,
    'motion-toggle': toggle
  };
  const document = eventTarget({
    readyState: 'complete',
    hidden: false,
    getElementById: name => elements[name] || null
  });
  const window = {
    matchMedia: () => preference,
    getComputedStyle: () => ({ opacity: '1', transform: 'none' })
  };
  vm.runInNewContext(source, { window, document, console }, { filename: 'motion.js' });
  return {
    motion: window.AgentMotion, scene, video, toggle, label, preference, document,
    visibility(hidden) {
      document.hidden = hidden;
      document.emit('visibilitychange');
    },
    changePreference(reduced) {
      preference.matches = reduced;
      preference.emit('change', { matches: reduced });
    }
  };
}

function animatedElement(children = []) {
  const target = element();
  target.children = children;
  target.createdAnimations = [];
  target.animate = () => {
    let resolve;
    let reject;
    let settled = false;
    const animation = {
      cancelled: false,
      completed: false,
      finished: new Promise((done, fail) => { resolve = done; reject = fail; }),
      complete() {
        if (settled) return;
        settled = true;
        animation.completed = true;
        resolve();
      },
      cancel() {
        animation.cancelled = true;
        if (settled) return;
        settled = true;
        const error = new Error('Animation cancelled');
        error.name = 'AbortError';
        reject(error);
      }
    };
    target.createdAnimations.push(animation);
    return animation;
  };
  return target;
}

function deadline(promise) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Motion promise did not settle')), 1000);
    promise.then(value => { clearTimeout(timeout); resolve(value); }, error => {
      clearTimeout(timeout);
      reject(error);
    });
  });
}

test('reduced motion avoids video download and page animations before explicit opt-in', async () => {
  const env = fixture({ reduced: true });
  const content = animatedElement();
  env.motion.scene('ideas');
  await env.motion.leave(content);
  await env.motion.enter(content);
  assert.equal(env.motion.reduced, true);
  assert.equal(env.video.src, '');
  assert.equal(env.video.loadCalls, 0);
  assert.equal(env.video.playCalls, 0);
  assert.equal(content.createdAnimations.length, 0);
  assert.equal(env.toggle.getAttribute('aria-pressed'), 'true');
  assert.equal(env.label.textContent, '播放背景');
});

test('explicit play loads local media once and navigation preserves continuous playback', async () => {
  const env = fixture({ reduced: true });
  env.toggle.emit('click');
  await flush();
  assert.equal(env.video.src, '/media/motion-background.mp4');
  assert.equal(env.video.loadCalls, 1);
  assert.equal(env.video.playCalls, 1);
  assert.equal(env.toggle.getAttribute('aria-pressed'), 'false');
  assert.equal(env.label.textContent, '暂停背景');
  env.video.emit('loadeddata');
  assert.equal(env.scene.classList.contains('is-video-ready'), true);
  env.motion.scene('finance');
  env.motion.scene('history');
  assert.equal(env.scene.dataset.page, 'history');
  assert.equal(env.video.loadCalls, 1);
  assert.equal(env.video.playCalls, 1);
  assert.equal(env.motion.reduced, true);
});

test('manual pause survives a hidden-to-visible cycle until the user resumes', async () => {
  const env = fixture();
  await flush();
  env.toggle.emit('click');
  assert.equal(env.video.paused, true);
  env.visibility(true);
  env.visibility(false);
  await flush();
  assert.equal(env.video.playCalls, 1);
  assert.equal(env.toggle.getAttribute('aria-pressed'), 'true');
  assert.equal(env.label.textContent, '播放背景');
  env.toggle.emit('click');
  await flush();
  assert.equal(env.video.playCalls, 2);
  assert.equal(env.video.paused, false);
});

test('visibility pauses playback and resumes it when the user has not paused', async () => {
  const env = fixture();
  await flush();
  env.visibility(true);
  assert.equal(env.video.paused, true);
  env.visibility(false);
  await flush();
  assert.equal(env.video.playCalls, 2);
  assert.equal(env.video.loadCalls, 1);
  assert.equal(env.video.paused, false);
});

test('autoplay rejection preserves a usable play control and static background', async () => {
  const env = fixture({ rejectPlay: true });
  await flush();
  assert.equal(env.label.textContent, '播放背景');
  assert.equal(env.toggle.getAttribute('aria-pressed'), 'true');
  assert.equal(env.toggle.disabled, false);
  assert.equal(env.scene.classList.contains('is-video-ready'), false);
  env.visibility(true);
  env.visibility(false);
  await flush();
  assert.equal(env.video.playCalls, 1);
  env.toggle.emit('click');
  await flush();
  assert.equal(env.video.playCalls, 2);
  assert.equal(env.label.textContent, '播放背景');
});

test('finished leave retains its frame until enter releases all animation effects', async () => {
  const env = fixture();
  const child = animatedElement();
  const content = animatedElement([child]);
  const leaving = env.motion.leave(content);
  const leaveAnimation = content.createdAnimations[0];
  leaveAnimation.complete();
  await deadline(leaving);
  assert.equal(leaveAnimation.cancelled, false);
  const entering = env.motion.enter(content);
  assert.equal(leaveAnimation.cancelled, true);
  content.createdAnimations[1].complete();
  child.createdAnimations[0].complete();
  await deadline(entering);
  assert.equal(content.createdAnimations[1].cancelled, true);
  assert.equal(child.createdAnimations[0].cancelled, true);
});

test('rapid navigation cancellation settles old transitions without unhandled rejection', async () => {
  const env = fixture();
  const child = animatedElement();
  const content = animatedElement([child]);
  const leaving = env.motion.leave(content);
  const entering = env.motion.enter(content);
  const replacement = env.motion.leave(content);
  assert.equal(content.createdAnimations[0].cancelled, true);
  assert.equal(content.createdAnimations[1].cancelled, true);
  assert.equal(child.createdAnimations[0].cancelled, true);
  content.createdAnimations[2].complete();
  await deadline(Promise.all([leaving, entering, replacement]));
  const finalEnter = env.motion.enter(content);
  content.createdAnimations[3].complete();
  child.createdAnimations[1].complete();
  await deadline(finalEnter);
  await flush();
});

test('reset releases a retained leave frame before the next route data is available', async () => {
  const env = fixture();
  const content = animatedElement();
  const leaving = env.motion.leave(content);
  content.createdAnimations[0].complete();
  await deadline(leaving);
  assert.equal(content.createdAnimations[0].cancelled, false);
  env.motion.reset(content);
  assert.equal(content.createdAnimations[0].cancelled, true);
  assert.equal(content.createdAnimations.length, 1);
  env.motion.reset(content);
  env.motion.reset(null);
});

test('reset cancels descendant subview effects and settles them without touching other views', async () => {
  const env = fixture();
  const subview = animatedElement();
  const content = animatedElement([subview]);
  const unrelated = animatedElement();
  const leaving = env.motion.leave(content);
  const subviewLeaving = env.motion.leave(subview);
  const otherEntering = env.motion.enter(unrelated);
  env.motion.reset(content);
  assert.equal(content.createdAnimations[0].cancelled, true);
  assert.equal(subview.createdAnimations[0].cancelled, true);
  assert.equal(unrelated.createdAnimations[0].cancelled, false);
  await deadline(Promise.all([leaving, subviewLeaving]));
  unrelated.createdAnimations[0].complete();
  await deadline(otherEntering);
  await flush();
});

test('changing to reduced motion cancels pending effects and disables new transitions', async () => {
  const env = fixture();
  const content = animatedElement([animatedElement()]);
  const entering = env.motion.enter(content);
  env.changePreference(true);
  await deadline(entering);
  assert.equal(env.motion.reduced, true);
  assert.equal(env.video.paused, true);
  assert.equal(content.createdAnimations[0].cancelled, true);
  await env.motion.leave(content);
  assert.equal(content.createdAnimations.length, 1);
  env.toggle.emit('click');
  await flush();
  assert.equal(env.video.paused, false);
  assert.equal(env.motion.reduced, true);
});

test('unsupported or failing animation APIs leave content visible and settle safely', async () => {
  const env = fixture();
  await env.motion.enter(element());
  await env.motion.leave(element());
  const child = animatedElement();
  child.animate = () => { throw new Error('Animation unsupported'); };
  const content = animatedElement([child]);
  await deadline(env.motion.enter(content));
  assert.equal(content.createdAnimations[0].cancelled, true);
  await flush();
});

test('missing or failed media disables playback with a static fallback', async () => {
  for (const options of [{ missingVideo: true }, { missingSource: true }]) {
    const env = fixture(options);
    assert.equal(env.label.textContent, '静态背景');
    assert.equal(env.toggle.disabled, true);
    assert.equal(env.toggle.getAttribute('aria-pressed'), 'true');
    assert.equal(env.video.playCalls, 0);
  }
  const env = fixture();
  await flush();
  env.video.emit('loadeddata');
  env.video.emit('error');
  assert.equal(env.scene.classList.contains('is-video-ready'), false);
  assert.equal(env.scene.classList.contains('is-video-unavailable'), true);
  assert.equal(env.video.paused, true);
  assert.equal(env.label.textContent, '静态背景');
  assert.equal(env.toggle.disabled, true);
  env.toggle.emit('click');
  env.visibility(true);
  env.visibility(false);
  assert.equal(env.video.playCalls, 1);
});
