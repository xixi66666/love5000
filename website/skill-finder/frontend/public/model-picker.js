/* 沿用所在页面的色彩与材质；一个紧凑按钮展开模型目录，作用范围始终可见。 */
(() => {
  'use strict';
  if (window.Love530ModelPicker) return;
  window.Love530ModelPicker = true;
  const css = `
    :host{--mp-bg:var(--color-bg,#121b1f);--mp-text:var(--color-text-primary,#edf2ef);--mp-muted:var(--color-text-secondary,#b1c1bd);--mp-accent:var(--color-accent,#c9e0d5);--mp-line:var(--color-border,#ffffff24);display:inline-block;font:13px/1.5 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;text-align:left;color:var(--mp-text)}
    :host([data-theme="home"]){--mp-bg:#121d26;--mp-text:#fff;--mp-muted:#c4cdd4;--mp-accent:#d1eadc;--mp-line:#ffffff30}
    :host([data-theme="forest"]){--mp-bg:#111d18;--mp-text:#e9eee5;--mp-muted:#b5c8bc;--mp-accent:#dce7de;--mp-line:#afc3b735}
    :host([data-theme="scrapling"]){--mp-bg:#0a0d16;--mp-text:#e6edf8;--mp-muted:#a6b4cd;--mp-accent:#a2aaff;--mp-line:#94a3b833}
    :host([data-theme="stock"]){--mp-bg:var(--canvas,#f7f7f4);--mp-text:var(--ink,#26251e);--mp-muted:var(--body,#5a5852);--mp-accent:var(--cursor-orange-active,#d04200);--mp-line:var(--hairline-strong,#cfcdc4)}
    :host{color-scheme:dark}:host([data-theme="stock"]){color-scheme:light;--mp-error:#ad2843}:host-context([data-theme="light"]){color-scheme:light}
    *,*::before,*::after{box-sizing:border-box}button,input{font:inherit}button{cursor:pointer}button:disabled{cursor:wait;opacity:.6}button:focus-visible,input:focus-visible{outline:2px solid var(--mp-accent);outline-offset:4px}
    .trigger{display:flex;align-items:center;gap:9px;max-width:min(260px,100%);min-height:40px;padding:8px 14px;border:1px solid var(--mp-line);border-radius:99px;color:var(--mp-text);background:color-mix(in srgb,var(--mp-bg) 60%,transparent);backdrop-filter:blur(18px);transition:background .18s}
    .trigger:hover{background:var(--mp-bg)}.glyph{color:var(--mp-accent);font-size:17px;line-height:1}.trigger-copy{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.chevron{margin-left:2px;opacity:.65;font-size:10px}
    .panel{position:fixed;inset:auto;margin:0;width:min(380px,calc(100vw - 24px));max-height:min(560px,calc(100dvh - 32px));overflow:hidden;padding:0;border:1px solid var(--mp-line);border-radius:16px;background:var(--mp-bg);color:var(--mp-text);box-shadow:0 20px 60px #0005;scrollbar-width:thin}.panel:popover-open{display:flex;flex-direction:column}.head,.intro,.search,.foot,.feedback{flex-shrink:0}.choices{min-height:80px;flex:1}.feedback:empty{display:none}
    .panel::backdrop{background:transparent}.head{display:flex;justify-content:space-between;align-items:center;padding:20px 20px 8px}.title{font-size:17px;font-weight:650;letter-spacing:-.02em}.scope{color:var(--mp-accent);font-size:11px;margin-top:4px}.refresh{border:1px solid var(--mp-line);border-radius:8px;background:transparent;color:var(--mp-muted);padding:6px 10px;min-height:32px}.intro{margin:0;padding:0 20px 15px;color:var(--mp-muted);font-size:12px}.search{display:block;margin:0 16px 10px;width:calc(100% - 32px);min-height:38px;border:1px solid var(--mp-line);border-radius:8px;padding:8px 11px;background:transparent;color:var(--mp-text)}.search::placeholder{color:var(--mp-muted)}
    .choices{padding:0 10px 8px;max-height:310px;overflow:auto}.option{display:flex;align-items:center;gap:11px;padding:10px;border-radius:9px;cursor:pointer;min-height:58px}.option:hover{background:color-mix(in srgb,var(--mp-accent) 8%,transparent)}.option:has(input:checked){background:color-mix(in srgb,var(--mp-accent) 12%,transparent)}.option input{width:15px;height:15px;flex:0 0 15px;margin:0;accent-color:var(--mp-accent)}.option:has(input:disabled){opacity:.58;cursor:default}.name{display:block;overflow-wrap:anywhere;font-size:13px;font-weight:600}.meta{display:block;color:var(--mp-muted);font-size:11px;margin-top:2px}.option-text{min-width:0}.group{padding:12px 10px 4px;color:var(--mp-muted);font-size:11px}.foot{padding:13px 20px 16px;border-top:1px solid var(--mp-line);color:var(--mp-muted);font-size:11px;line-height:1.7}.feedback{padding:0 20px 12px;margin:0;font-size:12px;color:var(--mp-accent)}.feedback.error{color:var(--mp-error,#ffb2b6)}.empty{padding:12px;color:var(--mp-muted)}
    @media(prefers-reduced-motion:reduce){*{transition:none!important}}
  `;
  function init(host) {
    if (host.shadowRoot) return;
    const scope = host.dataset.modelScope || 'global';
    const hub = host.hasAttribute('data-model-hub') ? host.dataset.modelHub : scope === 'global' ? '' : `http://${location.hostname === 'localhost' ? 'localhost' : '127.0.0.1'}:8080`;
    const root = host.attachShadow({ mode: 'open' });
    host.setAttribute('data-theme', host.dataset.modelTheme || 'default');
    root.innerHTML = `<style>${css}</style><button class="trigger" type="button" aria-label="选择${scope === 'global' ? '全局' : '当前服务'}模型" aria-expanded="false"><span class="glyph" aria-hidden="true">✦</span><span class="trigger-copy">${scope === 'global' ? '全局模型' : '模型'} · 读取中</span><span class="chevron" aria-hidden="true">⌄</span></button><section class="panel" popover="auto" aria-label="模型选择"><div class="head"><div><div class="title">选择模型</div><div class="scope">${scope === 'global' ? '全局默认 · 文本模型' : '仅当前服务 · ' + scope}</div></div><button class="refresh" type="button">刷新目录</button></div><p class="intro">${scope === 'global' ? '下一次请求生效。单独指定模型的服务保留自己的选择。' : '选择只影响此服务，也可随时恢复跟随主页。'}</p><input class="search" type="search" placeholder="搜索模型或提供方" aria-label="搜索模型"><div class="choices" role="radiogroup" aria-label="可选模型"></div><p class="feedback" role="status" aria-live="polite"></p><div class="foot">图片生成、截图识别、语音与视频继续使用各自专用模型。<br>“目录已验证”表示接口可访问并列出了该模型，实际生成以提供方响应为准。</div></section>`;
    const trigger = root.querySelector('.trigger');
    const panel = root.querySelector('.panel');
    const choices = root.querySelector('.choices');
    const search = root.querySelector('.search');
    const refresh = root.querySelector('.refresh');
    const feedback = root.querySelector('.feedback');
    let catalog = null;
    let busy = false;
    let current = '';
    let global = '';
    const notify = (message, error = false) => { feedback.textContent = message; feedback.classList.toggle('error', error); };
    const labelFor = id => catalog?.models.find(m => m.id === id)?.model || id.split(':').slice(1).join(':');
    function updateLabel() {
      const effective = current || global;
      const name = !effective || effective === 'native' ? '服务原配置' : labelFor(effective);
      root.querySelector('.trigger-copy').textContent = `${scope === 'global' ? '全局' : current ? '独立' : '跟随主页'} · ${name}`;
      trigger.title = `${scope === 'global' ? '全局默认模型' : '当前服务生效模型'}：${name}`;
      window.dispatchEvent(new CustomEvent('love530:modelchange', { detail: { scope, active: !!effective && effective !== 'native' } }));
    }
    async function api(path, method = 'GET', payload) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), path.includes('/local/') ? 200000 : method === 'GET' ? 50000 : 60000);
      try {
        const response = await fetch(hub + '/api/models' + path, { method, signal: controller.signal, credentials: 'omit', headers: { 'X-Love530-Model': '1', ...(payload ? { 'Content-Type': 'application/json' } : {}) }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || '操作失败，请稍后重试');
        return data;
      } catch (error) {
        if (error instanceof TypeError || error.name === 'AbortError') throw new Error('统一模型入口暂不可用，请先启动 website 后重试');
        throw error;
      } finally { clearTimeout(timer); }
    }
    function row(id, name, meta, enabled = true) {
      const label = document.createElement('label'); label.className = 'option';
      const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'model'; radio.value = id; radio.checked = current === id; radio.disabled = !enabled || busy;
      const text = document.createElement('span'); text.className = 'option-text';
      const title = document.createElement('span'); title.className = 'name'; title.textContent = name;
      const subtitle = document.createElement('span'); subtitle.className = 'meta'; subtitle.textContent = meta;
      text.append(title, subtitle); label.append(radio, text);
      radio.addEventListener('change', () => save(id)); return label;
    }
    function render() {
      const focused = root.activeElement;
      const focusValue = focused?.matches('input[type="radio"]') ? focused.value : null;
      const scrollTop = choices.scrollTop;
      choices.replaceChildren();
      if (scope !== 'global') choices.append(row('', '跟随主页', global && global !== 'native' ? labelFor(global) : '全局尚未指定统一模型'));
      choices.append(row(scope === 'global' ? '' : 'native', '服务原配置', scope === 'global' ? '各服务使用原有配置' : '此服务使用原有环境变量或设置'));
      if (!catalog) return;
      const filtered = catalog.models.filter(m => `${m.model} ${m.provider}`.toLowerCase().includes(search.value.trim().toLowerCase()));
      const group = document.createElement('div'); group.className = 'group'; group.textContent = `${catalog.models.filter(m => m.available).length} 个模型目录已验证`; choices.append(group);
      for (const model of filtered) {
        choices.append(row(model.id, model.model, `${model.provider} · ${model.status}`, model.available));
        if (model.startable && !model.available) {
          const start = document.createElement('button'); start.className = 'refresh'; start.textContent = '启动本机 Qwen 并选择'; start.disabled = busy;
          start.addEventListener('click', async () => {
            if (busy) return; busy = true; start.disabled = true; notify('正在启动本机服务，首次生成时加载权重…');
            try {
              catalog = await api('/local/strata/start', 'POST');
              const local = catalog.models.find(m => m.id.startsWith('strata:') && m.available);
              if (!local) throw new Error('服务已启动，但模型目录尚不可用，请检查模型管理页');
              busy = false; await save(local.id);
            } catch (error) { notify(error.message, true); }
            finally { busy = false; render(); }
          });
          choices.append(start);
        }
      }
      if (!filtered.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '没有匹配的模型'; choices.append(empty); }
      choices.scrollTop = scrollTop;
      if (focusValue !== null) Array.from(choices.querySelectorAll('input[type="radio"]')).find(input => input.value === focusValue && !input.disabled)?.focus({ preventScroll: true });
    }
    async function load(force = false) {
      if (busy) return;
      busy = true; refresh.disabled = true; notify(force ? '正在验证模型目录…' : '正在读取模型配置…');
      try {
        catalog = await api(force ? '/refresh' : '', force ? 'POST' : 'GET');
        current = catalog.selections[scope] || ''; global = scope === 'global' ? '' : catalog.selections.global || '';
        updateLabel(); notify('');
      } catch (error) { notify(error.message, true); if (!catalog) root.querySelector('.trigger-copy').textContent = '模型 · 入口离线'; }
      finally { busy = false; refresh.disabled = false; render(); }
    }
    async function save(id) {
      if (busy) return;
      const restoreFocus = root.activeElement?.matches('input[type="radio"]');
      busy = true; refresh.disabled = true; render(); notify('正在保存模型选择…');
      try { await api('/selection/' + scope, 'PUT', { modelId: id }); current = id; updateLabel(); notify(scope === 'global' ? '已保存，跟随主页的服务将在下次请求时使用此模型。' : '已保存，仅对当前服务生效。'); }
      catch (error) { notify(error.message, true); }
      finally {
        busy = false; refresh.disabled = false; render();
        if (restoreFocus) Array.from(choices.querySelectorAll('input[type="radio"]')).find(input => input.value === current)?.focus({ preventScroll: true });
      }
    }
    function position() {
      const rect = trigger.getBoundingClientRect(); const width = Math.min(380, innerWidth - 24);
      panel.style.left = Math.max(12, Math.min(rect.left, innerWidth - width - 12)) + 'px';
      const roomBelow = innerHeight - rect.bottom - 20;
      const roomAbove = rect.top - 20;
      const below = roomBelow >= roomAbove;
      const room = Math.max(roomBelow, roomAbove);
      // 横屏高度不足时面板贴近视口，标题与关闭操作仍可访问。
      const compact = room < 260;
      panel.style.top = compact ? '12px' : below ? rect.bottom + 8 + 'px' : 'auto';
      panel.style.bottom = compact || below ? 'auto' : innerHeight - rect.top + 8 + 'px';
      panel.style.maxHeight = Math.max(0, Math.min(560, compact ? innerHeight - 24 : room)) + 'px';
    }
    trigger.addEventListener('click', () => {
      if (panel.matches(':popover-open')) panel.hidePopover();
      else { position(); panel.showPopover(); load(); }
    });
    panel.addEventListener('toggle', () => trigger.setAttribute('aria-expanded', String(panel.matches(':popover-open'))));
    refresh.addEventListener('click', () => load(true)); search.addEventListener('input', render);
    window.addEventListener('resize', () => { if (panel.matches(':popover-open')) position(); });
    window.addEventListener('focus', () => { if (host.isConnected) load(); });
    load();
  }
  function scan() { document.querySelectorAll('[data-model-picker]').forEach(init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan); else scan();
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
})();
