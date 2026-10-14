(function () {
  'use strict';

  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const animations = new WeakMap();
  const activeAnimations = new Set();
  const scenes = {
    auth: { x: '50%', y: '50%', scale: 1, tint: 'rgba(19, 31, 26, .10)' },
    workspace: { x: '49%', y: '50%', scale: 1, tint: 'rgba(19, 31, 26, .10)' },
    ideas: { x: '51%', y: '49%', scale: 1.01, tint: 'rgba(32, 34, 27, .08)' },
    reading: { x: '49%', y: '51%', scale: 1, tint: 'rgba(20, 32, 28, .10)' },
    finance: { x: '51%', y: '51%', scale: 1.01, tint: 'rgba(24, 33, 35, .10)' },
    memories: { x: '49%', y: '49%', scale: 1, tint: 'rgba(28, 33, 27, .08)' },
    history: { x: '51%', y: '50%', scale: 1.01, tint: 'rgba(26, 32, 32, .10)' },
    settings: { x: '50%', y: '50%', scale: 1, tint: 'rgba(24, 31, 29, .10)' }
  };
  let reduced = preference.matches;
  let sceneElement;
  let video;
  let toggle;
  let userPaused = false;
  let explicitPlayback = false;
  let autoplayBlocked = false;
  let unavailable = false;
  let playAttempt = 0;

  function cancelRecord(record) {
    record.items.forEach(function (animation) { animation.cancel(); });
    activeAnimations.delete(record);
    if (animations.get(record.element) === record) animations.delete(record.element);
  }

  function cancelElement(element) {
    const record = animations.get(element);
    if (record) cancelRecord(record);
  }

  function reset(element) {
    if (!element) return;
    activeAnimations.forEach(function (record) {
      if (record.element === element || element.contains(record.element)) cancelRecord(record);
    });
  }

  function settled(animation) {
    return animation.finished.catch(function () {});
  }

  function leave(element) {
    if (!element) return Promise.resolve();
    const current = window.getComputedStyle(element);
    const start = { opacity: current.opacity, transform: current.transform };
    cancelElement(element);
    if (reduced || typeof element.animate !== 'function') return Promise.resolve();
    try {
      const animation = element.animate([
        start,
        { opacity: 0, transform: 'translateY(-10px)' }
      ], { duration: 150, easing: 'cubic-bezier(.4, 0, 1, 1)', fill: 'forwards' });
      const record = { element: element, items: [animation] };
      animations.set(element, record);
      activeAnimations.add(record);
      // Retain the final frame until enter() replaces it, avoiding a visible flash.
      return settled(animation);
    } catch (error) {
      cancelElement(element);
      return Promise.resolve();
    }
  }

  function enter(element) {
    if (!element) return Promise.resolve();
    cancelElement(element);
    if (reduced || typeof element.animate !== 'function') return Promise.resolve();
    const record = { element: element, items: [], pending: [] };
    animations.set(element, record);
    activeAnimations.add(record);
    try {
      record.items.push(element.animate([
        { opacity: 0, transform: 'translateY(18px)' },
        { opacity: 1, transform: 'none' }
      ], { duration: 420, easing: 'cubic-bezier(.16, 1, .3, 1)', fill: 'both' }));
      record.pending.push(settled(record.items[0]));
      Array.from(element.children).slice(0, 6).forEach(function (child, index) {
        if (typeof child.animate !== 'function') return;
        record.items.push(child.animate([
          { opacity: 0, transform: 'translateY(10px)' },
          { opacity: 1, transform: 'none' }
        ], {
          duration: 360,
          delay: index * 45,
          easing: 'cubic-bezier(.16, 1, .3, 1)',
          fill: 'both'
        }));
        record.pending.push(settled(record.items[record.items.length - 1]));
      });
      return Promise.all(record.pending).then(function () {
        if (animations.get(element) === record) cancelRecord(record);
      });
    } catch (error) {
      cancelRecord(record);
      return Promise.resolve();
    }
  }

  function scene(page) {
    const target = sceneElement || document.getElementById('ambient-scene');
    if (!target) return;
    const selected = scenes[page] || scenes.workspace;
    target.dataset.page = page || 'workspace';
    target.style.setProperty('--scene-x', selected.x);
    target.style.setProperty('--scene-y', selected.y);
    target.style.setProperty('--scene-scale', String(selected.scale));
    target.style.setProperty('--scene-tint', selected.tint);
  }

  function wantsPlayback() {
    return !unavailable && !userPaused && (!reduced || explicitPlayback);
  }

  function updateToggle() {
    const paused = !wantsPlayback() || autoplayBlocked || document.hidden;
    if (sceneElement) sceneElement.classList.toggle('is-video-paused', paused);
    if (!toggle) return;
    const label = unavailable ? '静态背景' : paused ? '播放背景' : '暂停背景';
    const labelElement = toggle.querySelector('[data-motion-label]');
    if (labelElement) labelElement.textContent = label;
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('aria-pressed', String(paused));
    toggle.disabled = unavailable;
  }

  function pauseVideo() {
    playAttempt += 1;
    if (video) video.pause();
    updateToggle();
  }

  function playVideo() {
    if (!video || !wantsPlayback() || document.hidden) {
      updateToggle();
      return;
    }
    if (!video.getAttribute('src')) {
      const source = video.dataset.src;
      if (!source) {
        unavailable = true;
        updateToggle();
        return;
      }
      // Reduced-motion visitors do not download video until they choose playback.
      video.src = source;
      video.load();
    }
    const attempt = ++playAttempt;
    autoplayBlocked = false;
    updateToggle();
    try {
      const result = video.play();
      if (result && typeof result.then === 'function') {
        result.then(function () {
          if (attempt !== playAttempt) return;
          if (!wantsPlayback() || document.hidden) pauseVideo();
          else updateToggle();
        }).catch(function () {
          if (attempt !== playAttempt) return;
          autoplayBlocked = true;
          updateToggle();
        });
      }
    } catch (error) {
      autoplayBlocked = true;
      updateToggle();
    }
  }

  function onPreferenceChange(event) {
    reduced = event.matches;
    explicitPlayback = false;
    activeAnimations.forEach(cancelRecord);
    if (reduced) pauseVideo();
    else if (wantsPlayback() && !autoplayBlocked) playVideo();
    updateToggle();
  }

  function initialize() {
    sceneElement = document.getElementById('ambient-scene');
    video = document.getElementById('ambient-video');
    toggle = document.getElementById('motion-toggle');
    if (!sceneElement || !video) {
      unavailable = true;
      updateToggle();
      return;
    }
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.addEventListener('loadeddata', function () {
      sceneElement.classList.add('is-video-ready');
    });
    video.addEventListener('error', function () {
      unavailable = true;
      sceneElement.classList.remove('is-video-ready');
      sceneElement.classList.add('is-video-unavailable');
      pauseVideo();
    });
    if (video.readyState >= 2) sceneElement.classList.add('is-video-ready');
    if (toggle) toggle.addEventListener('click', function () {
      if (unavailable) return;
      const paused = !wantsPlayback() || autoplayBlocked;
      if (paused) {
        userPaused = false;
        explicitPlayback = true;
        playVideo();
      } else {
        userPaused = true;
        pauseVideo();
      }
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) pauseVideo();
      else if (wantsPlayback() && !autoplayBlocked) playVideo();
      else updateToggle();
    });
    scene('auth');
    updateToggle();
    if (!reduced) playVideo();
  }

  window.AgentMotion = { scene: scene, leave: leave, enter: enter, reset: reset };
  Object.defineProperty(window.AgentMotion, 'reduced', { get: function () { return reduced; } });
  if (typeof preference.addEventListener === 'function') preference.addEventListener('change', onPreferenceChange);
  else if (typeof preference.addListener === 'function') preference.addListener(onPreferenceChange);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
  else initialize();
})();
