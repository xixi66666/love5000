/* 共享模型选择器：紧凑触发按钮、可搜索面板、行内保存状态与键盘操作。 */
(() => {
  'use strict';
  if (window.Love530ModelPicker) return;
  window.Love530ModelPicker = true;

  // 同一页面可能挂多个选择器（例如个人资料库的分析页与设置页），共用一次目录请求。
  const CATALOG_TTL = 20000;
  const catalogCache = { hub: '', at: 0, data: null };
  const pending = new Map();
  const live = new Map();

  const css = `
    :host{--mp-bg:#121b1f;--mp-text:#edf2ef;--mp-muted:#a9bab5;--mp-accent:#c9e0d5;--mp-line:#ffffff26;--mp-field:color-mix(in srgb,var(--mp-text) 7%,var(--mp-bg));--mp-hover:color-mix(in srgb,var(--mp-accent) 9%,transparent);--mp-tint:color-mix(in srgb,var(--mp-accent) 14%,transparent);--mp-danger:#ffb2b6;--mp-shadow:0 26px 70px #0009,0 2px 10px #00000059;display:inline-block;color-scheme:dark;font:13px/1.5 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;text-align:left;color:var(--mp-text)}
    :host([data-theme="home"]){--mp-bg:#121d26;--mp-text:#fff;--mp-muted:#c4cdd4;--mp-accent:#d1eadc;--mp-line:#ffffff30}
    :host([data-theme="forest"]){--mp-bg:#111d18;--mp-text:#e9eee5;--mp-muted:#b5c8bc;--mp-accent:#dce7de;--mp-line:#afc3b735}
    :host([data-theme="scrapling"]){--mp-bg:#0a0d16;--mp-text:#e6edf8;--mp-muted:#a6b4cd;--mp-accent:#a2aaff;--mp-line:#94a3b833}
    :host([data-theme="stock"]){--mp-bg:var(--canvas,#f7f7f4);--mp-text:var(--ink,#26251e);--mp-muted:var(--body,#5a5852);--mp-accent:var(--cursor-orange-active,#d04200);--mp-line:var(--hairline-strong,#cfcdc4);--mp-danger:var(--error,#cf2d56);--mp-shadow:0 24px 60px rgba(38,37,30,.18),0 2px 6px rgba(38,37,30,.08);color-scheme:light}
    :host([data-theme="knowledge"]){--mp-bg:color-mix(in srgb,var(--bg,#f8faf9) 94%,var(--ink,#243832) 6%);--mp-text:var(--ink,#243832);--mp-muted:var(--muted,#576c63);--mp-accent:var(--accent,#176550);--mp-line:var(--line,#d6e1dc);--mp-danger:var(--danger,#a52e36);--mp-shadow:0 24px 60px rgba(36,56,50,.18),0 2px 6px rgba(36,56,50,.08);color-scheme:light}
    :host([data-theme="knowledge"]):host-context([data-theme="dark"]){--mp-shadow:0 26px 70px #000000a6,0 2px 8px #00000059;color-scheme:dark}
    *,*::before,*::after{box-sizing:border-box}button,input{font:inherit}button{cursor:pointer}button:disabled{cursor:progress;opacity:.55}
    button:focus-visible,input:focus-visible,.option:has(input:focus-visible){outline:2px solid var(--mp-accent);outline-offset:2px}
    .trigger{display:flex;align-items:center;gap:8px;max-width:min(280px,100%);min-height:40px;padding:8px 13px;border:1px solid var(--mp-line);border-radius:999px;color:var(--mp-text);background:color-mix(in srgb,var(--mp-bg) 72%,transparent);backdrop-filter:blur(16px);transition:background .18s,border-color .18s,transform .18s}
    .trigger:hover{background:var(--mp-bg);border-color:color-mix(in srgb,var(--mp-accent) 42%,var(--mp-line))}
    .trigger:active{transform:translateY(1px)}
    .trigger[aria-expanded="true"]{background:var(--mp-bg);border-color:color-mix(in srgb,var(--mp-accent) 55%,var(--mp-line))}
    .glyph{flex:none;color:var(--mp-accent);font-size:15px;line-height:1;transition:color .18s,opacity .18s}
    .trigger.is-native .glyph{color:var(--mp-muted);opacity:.7}
    .trigger-copy{display:flex;align-items:baseline;gap:5px;min-width:0;font-size:12px}
    .trigger-prefix{flex:none;color:var(--mp-muted)}
    .trigger-sep{flex:none;color:var(--mp-muted);opacity:.7}
    .trigger-model{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;transition:color .18s}
    .trigger.is-saved .trigger-model{color:var(--mp-accent)}
    .chevron{flex:none;opacity:.6;font-size:10px;transition:transform .18s}
    .trigger[aria-expanded="true"] .chevron{transform:rotate(180deg)}
    .panel{position:fixed;inset:auto;margin:0;width:min(392px,calc(100vw - 24px));padding:0;border:1px solid var(--mp-line);border-radius:16px;background:var(--mp-bg);color:var(--mp-text);box-shadow:var(--mp-shadow);overflow:hidden;display:none;flex-direction:column;scrollbar-width:thin}
    .panel:popover-open{display:flex;animation:mp-in .16s cubic-bezier(.2,.8,.2,1)}
    @starting-style{.panel:popover-open{opacity:0;transform:translateY(6px) scale(.985)}}
    @keyframes mp-in{from{opacity:0;transform:translateY(6px) scale(.985)}to{opacity:1;transform:none}}
    .panel::backdrop{background:transparent}
    .head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 14px 10px 18px;flex:none}
    .title{font-size:15px;font-weight:650;letter-spacing:-.01em;line-height:1.4}
    .scope{display:block;margin-top:3px;color:var(--mp-muted);font-size:11px}
    .head-actions{display:flex;gap:2px;flex:none;margin-top:-2px}
    .icon-btn{display:grid;place-items:center;width:30px;height:30px;padding:0;border:0;border-radius:8px;background:transparent;color:var(--mp-muted);font-size:14px;line-height:1;transition:background .15s,color .15s}
    .icon-btn:hover{background:var(--mp-hover);color:var(--mp-text)}
    .icon-btn.spinning{color:var(--mp-accent);animation:mp-spin 1s linear infinite}
    .search-wrap{position:relative;display:flex;align-items:center;margin:0 14px 8px;flex:none}
    .search-glyph{position:absolute;left:11px;color:var(--mp-muted);font-size:13px;pointer-events:none}
    .search{width:100%;height:36px;padding:7px 10px 7px 31px;border:1px solid var(--mp-line);border-radius:9px;background:var(--mp-field);color:var(--mp-text);font-size:12.5px}
    .search::placeholder{color:var(--mp-muted)}
    .search:focus,.search:focus-visible{outline:none;border-color:color-mix(in srgb,var(--mp-accent) 55%,var(--mp-line));box-shadow:0 0 0 3px color-mix(in srgb,var(--mp-accent) 16%,transparent)}
    .choices{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:2px 8px 8px;transition:mask-image .2s}
    .choices.has-more{-webkit-mask-image:linear-gradient(to bottom,#000 calc(100% - 20px),transparent);mask-image:linear-gradient(to bottom,#000 calc(100% - 20px),transparent)}
    .choices::-webkit-scrollbar{width:9px}
    .choices::-webkit-scrollbar-track{background:transparent}
    .choices::-webkit-scrollbar-thumb{border:2px solid transparent;border-radius:99px;background:color-mix(in srgb,var(--mp-muted) 38%,transparent);background-clip:content-box}
    .option{position:relative;display:flex;align-items:center;gap:10px;min-height:50px;padding:8px 10px;border-radius:9px;cursor:pointer;transition:background .14s}
    .option+.option{margin-top:1px}
    .option:hover{background:var(--mp-hover)}
    .option:has(input:checked){background:var(--mp-tint)}
    .option:has(input:checked)::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--mp-accent)}
    .option input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
    .dot{position:relative;flex:none;width:15px;height:15px;border:1.5px solid color-mix(in srgb,var(--mp-muted) 55%,transparent);border-radius:50%;transition:border-color .15s}
    .option:has(input:checked) .dot{border-color:var(--mp-accent)}
    .option:has(input:checked) .dot::after{content:"";position:absolute;inset:3px;border-radius:50%;background:var(--mp-accent)}
    .option-text{flex:1;min-width:0}
    .option-line{display:flex;align-items:center;gap:7px;min-width:0}
    .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.8px;font-weight:600;line-height:1.35}
    .meta{display:block;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--mp-muted);font-size:11px;line-height:1.45}
    .tag{flex:none;padding:0 6px;border:1px solid var(--mp-line);border-radius:99px;color:var(--mp-muted);font-size:10px;line-height:1.6;white-space:nowrap}
    .tag.ok{color:var(--mp-accent);border-color:color-mix(in srgb,var(--mp-accent) 40%,transparent);background:var(--mp-tint)}
    .option-state{display:grid;place-items:center;flex:none;width:14px;height:14px;color:var(--mp-accent);font-size:12px}
    .option.is-saving .option-state::after{content:"";width:11px;height:11px;border:2px solid color-mix(in srgb,var(--mp-accent) 25%,transparent);border-top-color:var(--mp-accent);border-radius:50%;animation:mp-spin .7s linear infinite}
    .option.is-saved .option-state::after{content:"✓";font-weight:700}
    @keyframes mp-spin{to{transform:rotate(360deg)}}
    .option[aria-disabled="true"]{opacity:.55;cursor:not-allowed}
    .option[aria-disabled="true"]:hover{background:transparent}
    .group{display:flex;align-items:center;gap:8px;padding:12px 10px 4px;color:var(--mp-muted);font-size:10.5px;letter-spacing:.02em}
    .group::after{content:"";flex:1;height:1px;background:var(--mp-line);opacity:.7}
    .skeleton-row{height:46px;margin:4px 2px;border-radius:9px;background:linear-gradient(90deg,var(--mp-field) 25%,color-mix(in srgb,var(--mp-field) 60%,var(--mp-text) 10%) 37%,var(--mp-field) 63%);background-size:400% 100%;animation:mp-shimmer 1.3s ease infinite}
    @keyframes mp-shimmer{from{background-position:100% 0}to{background-position:0 0}}
    .state-block{padding:18px 12px 22px;color:var(--mp-muted);font-size:12px;text-align:center}
    .state-block p{margin:0 0 10px;line-height:1.65}
    .state-block button{min-height:32px;padding:4px 12px;border:1px solid var(--mp-line);border-radius:8px;background:transparent;color:var(--mp-text);font-size:12px}
    .state-block button:hover{background:var(--mp-hover)}
    .inline-action{margin:2px 10px 6px 45px;min-height:30px;padding:4px 10px;border:1px solid var(--mp-line);border-radius:8px;background:transparent;color:var(--mp-muted);font-size:11px}
    .inline-action:hover{background:var(--mp-hover);color:var(--mp-text)}
    .feedback{flex:none;margin:0;padding:0 18px 8px;color:var(--mp-accent);font-size:11.5px;line-height:1.5}
    .feedback:empty{display:none}
    .feedback.error{color:var(--mp-danger)}
    .foot{flex:none;padding:9px 18px 11px;border-top:1px solid var(--mp-line);color:var(--mp-muted);font-size:10.5px;line-height:1.5}
    .panel.is-sheet{left:8px;right:8px;width:auto;bottom:8px;top:auto;max-height:min(78dvh,560px);border-radius:18px}
    .panel.is-sheet::backdrop{background:rgba(12,20,17,.32)}
    .panel.is-sheet .head{position:relative;padding-top:20px}
    .panel.is-sheet .head::before{content:"";position:absolute;top:8px;left:50%;transform:translateX(-50%);width:36px;height:4px;border-radius:99px;background:color-mix(in srgb,var(--mp-muted) 45%,transparent)}
    .panel.is-sheet .foot{padding-bottom:calc(11px + env(safe-area-inset-bottom,0px))}
    @media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
  `;

  function request(hub, path, method = 'GET', payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), path.includes('/local/') ? 200000 : method === 'GET' ? 50000 : 60000);
    return fetch(hub + '/api/models' + path, {
      method,
      signal: controller.signal,
      credentials: 'omit',
      headers: { 'X-Love530-Model': '1', ...(payload ? { 'Content-Type': 'application/json' } : {}) },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    }).then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) throw new Error(data.message || '操作失败，请稍后重试');
      return data;
    }).catch(error => {
      if (error instanceof TypeError || error.name === 'AbortError') throw new Error('统一模型入口暂不可用，请先启动 website 后重试');
      throw error;
    }).finally(() => clearTimeout(timer));
  }

  function fetchCatalog(hub, force) {
    if (!force && catalogCache.data && catalogCache.hub === hub && Date.now() - catalogCache.at < CATALOG_TTL) return Promise.resolve(catalogCache.data);
    const running = pending.get(hub);
    if (running) return running;
    const task = request(hub, force ? '/refresh' : '', force ? 'POST' : 'GET').then(data => {
      catalogCache.hub = hub;
      catalogCache.at = Date.now();
      catalogCache.data = data;
      return data;
    }).finally(() => pending.delete(hub));
    pending.set(hub, task);
    return task;
  }

  function init(host) {
    if (host.shadowRoot) return;
    const scope = host.dataset.modelScope || 'global';
    const hub = host.hasAttribute('data-model-hub') ? host.dataset.modelHub : scope === 'global' ? '' : `http://${location.hostname === 'localhost' ? 'localhost' : '127.0.0.1'}:8080`;
    const root = host.attachShadow({ mode: 'open' });
    host.setAttribute('data-theme', host.dataset.modelTheme || 'default');
    const scopeText = scope === 'global' ? '全局默认 · 文本模型' : `仅当前服务 · ${scope}`;
    const hintText = scope === 'global' ? '下一次请求生效；单独指定模型的服务保留自己的选择。' : '只影响此服务，也可随时恢复跟随主页。';
    root.innerHTML = `<style>${css}</style>
      <button class="trigger" type="button" aria-haspopup="dialog" aria-expanded="false" aria-label="选择${scope === 'global' ? '全局' : '当前服务'}模型">
        <span class="glyph" aria-hidden="true">✦</span>
        <span class="trigger-copy"><span class="trigger-prefix">读取中</span><span class="trigger-sep" aria-hidden="true">·</span><span class="trigger-model">…</span></span>
        <span class="chevron" aria-hidden="true">⌄</span>
      </button>
      <section class="panel" popover="auto" role="dialog" aria-label="模型选择">
        <header class="head">
          <div><div class="title">选择模型</div><div class="scope" title="${hintText}">${scopeText}</div></div>
          <div class="head-actions">
            <button class="icon-btn refresh" type="button" title="重新验证模型目录" aria-label="刷新模型目录">↻</button>
            <button class="icon-btn close" type="button" title="关闭" aria-label="关闭">✕</button>
          </div>
        </header>
        <div class="search-wrap"><span class="search-glyph" aria-hidden="true">⌕</span><input class="search" type="search" placeholder="搜索模型或提供方" aria-label="搜索模型" autocomplete="off"></div>
        <div class="choices" role="radiogroup" aria-label="可选模型"></div>
        <p class="feedback" role="status" aria-live="polite"></p>
        <footer class="foot">图片、语音与视频仍使用各自专用模型。</footer>
      </section>`;

    const trigger = root.querySelector('.trigger');
    const triggerPrefix = root.querySelector('.trigger-prefix');
    const triggerModel = root.querySelector('.trigger-model');
    const panel = root.querySelector('.panel');
    const choices = root.querySelector('.choices');
    const search = root.querySelector('.search');
    const refreshButton = root.querySelector('.refresh');
    const closeButton = root.querySelector('.close');
    const feedback = root.querySelector('.feedback');

    let catalog = null;
    let current = '';
    let global = '';
    let busy = false;
    let loading = true;
    let savingId = '';
    let savedId = '';
    let errorText = '';

    const notify = (message, error = false) => {
      feedback.textContent = message;
      feedback.classList.toggle('error', error);
    };
    const labelFor = id => catalog?.models.find(model => model.id === id)?.model || id.split(':').slice(1).join(':');
    const effectiveModel = () => {
      if (scope === 'global') return current && current !== 'native' ? current : '';
      if (current === 'native') return '';
      if (current) return current;
      return global && global !== 'native' ? global : '';
    };
    const prefixText = () => {
      if (scope === 'global') return '全局';
      if (!current) return '跟随主页';
      return '独立';
    };
    const modelText = () => {
      if (scope === 'global') return effectiveModel() ? labelFor(effectiveModel()) : '未指定';
      if (current === 'native') return '服务原配置';
      const effective = effectiveModel();
      return effective ? labelFor(effective) : '服务原配置';
    };

    function updateLabel() {
      triggerPrefix.textContent = prefixText();
      triggerModel.textContent = modelText();
      trigger.classList.toggle('is-native', !effectiveModel());
      trigger.title = `${scope === 'global' ? '全局默认模型' : '当前服务生效模型'}：${modelText()}`;
      trigger.setAttribute('aria-label', `选择${scope === 'global' ? '全局' : '当前服务'}模型，当前${prefixText()} · ${modelText()}`);
      window.dispatchEvent(new CustomEvent('love530:modelchange', { detail: { scope, active: !!effectiveModel() } }));
    }

    const element = (tag, className, text) => {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    };

    function optionRow({ id, name, meta, badge, badgeOk, enabled = true, saving = false, saved = false }) {
      const label = element('label', `option${saving ? ' is-saving' : ''}${saved ? ' is-saved' : ''}`);
      label.setAttribute('aria-disabled', String(!enabled));
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'mp-model';
      radio.value = id;
      radio.checked = current === id;
      radio.disabled = !enabled || busy;
      radio.addEventListener('change', () => choose(id));
      const dot = element('span', 'dot');
      dot.setAttribute('aria-hidden', 'true');
      const text = element('span', 'option-text');
      const line = element('span', 'option-line');
      line.append(element('span', 'name', name));
      if (badge) line.append(element('span', `tag${badgeOk ? ' ok' : ''}`, badge));
      text.append(line, element('span', 'meta', meta));
      const state = element('span', 'option-state');
      state.setAttribute('aria-hidden', 'true');
      label.append(radio, dot, text, state);
      return label;
    }

    function emptyState(query) {
      const box = element('div', 'state-block');
      box.append(element('p', '', query ? `没有匹配“${query}”的模型或提供方。` : '模型目录里暂时没有可选模型。'));
      if (query) {
        const clear = element('button', '', '清除搜索');
        clear.type = 'button';
        clear.addEventListener('click', () => { search.value = ''; render(); search.focus({ preventScroll: true }); });
        box.append(clear);
      } else {
        const retry = element('button', '', '重新读取');
        retry.type = 'button';
        retry.addEventListener('click', () => load(true));
        box.append(retry);
      }
      return box;
    }

    function startAction(model) {
      const button = element('button', 'inline-action', '启动本机 Qwen 并选择');
      button.type = 'button';
      button.disabled = busy;
      button.addEventListener('click', async () => {
        if (busy) return;
        busy = true;
        button.disabled = true;
        notify('正在启动本机服务，首次生成时加载权重…');
        try {
          const data = await request(hub, '/local/strata/start', 'POST');
          catalog = data;
          catalogCache.data = data;
          catalogCache.at = Date.now();
          const local = data.models.find(item => item.id.startsWith('strata:') && item.available);
          if (!local) throw new Error('服务已启动，但模型目录尚不可用，请检查模型管理页');
          busy = false;
          await choose(local.id);
        } catch (error) {
          notify(error.message, true);
        } finally {
          busy = false;
          render();
        }
      });
      return button;
    }

    function focusRadio(value) {
      const input = Array.from(choices.querySelectorAll('input[type="radio"]')).find(item => item.value === value && !item.disabled);
      input?.focus({ preventScroll: true });
    }

    function render() {
      const focused = root.activeElement;
      const focusValue = focused && focused.matches('input[type="radio"]') ? focused.value : null;
      const scrollTop = choices.scrollTop;
      choices.replaceChildren();
      if (!catalog) {
        if (loading) for (let index = 0; index < 3; index += 1) choices.append(element('div', 'skeleton-row'));
        else {
          const box = element('div', 'state-block');
          box.append(element('p', '', errorText || '模型目录暂不可用。'));
          const retry = element('button', '', '重试');
          retry.type = 'button';
          retry.addEventListener('click', () => load(true));
          box.append(retry);
          choices.append(box);
        }
        return;
      }
      if (scope !== 'global') {
        choices.append(optionRow({
          id: '',
          name: '跟随主页',
          meta: global && global !== 'native' ? `当前全局：${labelFor(global)}` : '主页尚未指定统一模型',
          enabled: true,
        }));
      }
      choices.append(optionRow({
        id: scope === 'global' ? '' : 'native',
        name: scope === 'global' ? '不指定统一模型' : '服务原配置',
        meta: scope === 'global' ? '各服务使用自身配置' : '使用此服务的环境变量或设置',
      }));
      const query = search.value.trim().toLowerCase();
      const models = catalog.models.filter(model => `${model.model} ${model.provider}`.toLowerCase().includes(query));
      if (!query) {
        const available = catalog.models.filter(model => model.available).length;
        const group = element('div', 'group');
        group.append(element('span', '', `${available} 个模型已验证`));
        choices.append(group);
      }
      for (const model of models) {
        choices.append(optionRow({
          id: model.id,
          name: model.model,
          meta: model.provider,
          badge: model.available ? '已验证' : '未就绪',
          badgeOk: model.available,
          enabled: model.available,
          saving: savingId === model.id,
          saved: savedId === model.id && current === model.id,
        }));
        if (model.startable && !model.available) choices.append(startAction(model));
      }
      if (!models.length) choices.append(emptyState(query));
      choices.scrollTop = scrollTop;
      updateScrollHint();
      if (focusValue !== null) focusRadio(focusValue);
    }

    function updateScrollHint() {
      const more = choices.scrollHeight - choices.clientHeight > 12;
      const atBottom = choices.scrollTop + choices.clientHeight >= choices.scrollHeight - 6;
      choices.classList.toggle('has-more', more && !atBottom);
    }

    async function load(force = false, silent = false) {
      if (busy) return;
      busy = true;
      refreshButton.disabled = true;
      refreshButton.classList.toggle('spinning', force);
      if (!catalog) {
        loading = true;
        render();
      }
      if (!silent) notify(force ? '正在重新验证模型目录…' : '');
      try {
        const data = await fetchCatalog(hub, force);
        catalog = data;
        current = data.selections[scope] || '';
        global = scope === 'global' ? '' : data.selections.global || '';
        errorText = '';
        updateLabel();
        if (force) notify('模型目录已更新。');
      } catch (error) {
        errorText = error.message;
        notify(error.message, true);
        if (!catalog) {
          triggerPrefix.textContent = '模型';
          triggerModel.textContent = '入口离线';
        }
      } finally {
        loading = false;
        busy = false;
        refreshButton.disabled = false;
        refreshButton.classList.remove('spinning');
        render();
      }
    }

    async function choose(id) {
      if (busy || id === current) return;
      const previous = current;
      busy = true;
      savingId = id;
      savedId = '';
      errorText = '';
      current = id;
      updateLabel();
      render();
      notify('正在保存模型选择…');
      try {
        await request(hub, '/selection/' + scope, 'PUT', { modelId: id });
        if (catalog?.selections) catalog.selections[scope] = id;
        if (catalogCache.data?.selections) catalogCache.data.selections[scope] = id;
        catalogCache.at = Date.now();
        savingId = '';
        savedId = id;
        updateLabel();
        notify(scope === 'global' ? '已保存，跟随主页的服务会在下次请求时使用。' : '已保存，仅对当前服务生效。');
        trigger.classList.add('is-saved');
        setTimeout(() => trigger.classList.remove('is-saved'), 1400);
        window.dispatchEvent(new CustomEvent('love530:modelselection', { detail: { scope, modelId: id } }));
        setTimeout(() => panel.hidePopover(), 260);
      } catch (error) {
        current = previous;
        savingId = '';
        updateLabel();
        notify(error.message, true);
      } finally {
        busy = false;
        render();
        focusRadio(current);
      }
    }

    function position() {
      const rect = trigger.getBoundingClientRect();
      const gutter = 12;
      const width = Math.min(392, innerWidth - gutter * 2);
      const roomBelow = innerHeight - rect.bottom - gutter - 8;
      const roomAbove = rect.top - gutter - 8;
      const room = Math.max(roomBelow, roomAbove);
      if (innerWidth <= 560 || room < 240) {
        panel.classList.add('is-sheet');
        panel.style.left = panel.style.right = panel.style.top = panel.style.bottom = panel.style.width = panel.style.maxHeight = '';
        return;
      }
      panel.classList.remove('is-sheet');
      panel.style.width = `${width}px`;
      panel.style.left = `${Math.max(gutter, Math.min(rect.left, innerWidth - width - gutter))}px`;
      const below = roomBelow >= roomAbove;
      panel.style.top = below ? `${rect.bottom + 8}px` : 'auto';
      panel.style.bottom = below ? 'auto' : `${innerHeight - rect.top + 8}px`;
      panel.style.maxHeight = `${Math.min(560, room)}px`;
    }

    function open() {
      position();
      panel.showPopover();
      load();
      requestAnimationFrame(() => {
        // 移动端底部抽屉不抢焦点，避免键盘立刻顶起面板。
        if (!panel.classList.contains('is-sheet')) search.focus({ preventScroll: true });
        choices.querySelector('input[type="radio"]:checked')?.closest('.option')?.scrollIntoView({ block: 'nearest' });
        updateScrollHint();
      });
    }

    trigger.addEventListener('click', () => {
      if (panel.matches(':popover-open')) panel.hidePopover();
      else open();
    });
    closeButton.addEventListener('click', () => { panel.hidePopover(); trigger.focus({ preventScroll: true }); });
    refreshButton.addEventListener('click', () => load(true));
    search.addEventListener('input', () => {
      if (!catalog) return;
      render();
    });
    choices.addEventListener('scroll', updateScrollHint, { passive: true });
    search.addEventListener('keydown', event => {
      if ((event.key !== 'ArrowDown' && event.key !== 'ArrowUp') || !catalog) return;
      event.preventDefault();
      const radios = Array.from(choices.querySelectorAll('input[type="radio"]:not(:disabled)'));
      (event.key === 'ArrowDown' ? radios[0] : radios[radios.length - 1])?.focus();
    });
    choices.addEventListener('keydown', event => {
      const radios = Array.from(choices.querySelectorAll('input[type="radio"]:not(:disabled)'));
      if (!radios.length) return;
      const index = radios.indexOf(root.activeElement);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const step = event.key === 'ArrowDown' ? 1 : -1;
        const next = index < 0 ? radios[0] : radios[(index + step + radios.length) % radios.length];
        next.focus();
      } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        (event.key === 'Home' ? radios[0] : radios[radios.length - 1]).focus();
      } else if (event.key === 'Enter' && index >= 0) {
        event.preventDefault();
        radios[index].click();
      }
    });
    panel.addEventListener('toggle', () => {
      const open = panel.matches(':popover-open');
      trigger.setAttribute('aria-expanded', String(open));
      if (!open && root.activeElement) trigger.focus({ preventScroll: true });
    });

    let scheduled = false;
    const reposition = event => {
      if (!panel.matches(':popover-open')) return;
      if (event && host.contains(event.target)) return;
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        if (panel.matches(':popover-open')) position();
      });
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);

    const onSelection = event => {
      const detail = event.detail || {};
      if (detail.scope === scope) {
        if (detail.modelId === current) return;
        current = detail.modelId || '';
        if (catalog?.selections) catalog.selections[scope] = current;
      } else if (detail.scope === 'global' && scope !== 'global') {
        const next = detail.modelId === 'native' ? '' : detail.modelId || '';
        if (next === global) return;
        global = next;
        if (catalog?.selections) catalog.selections.global = next;
      } else return;
      updateLabel();
      if (panel.matches(':popover-open')) render();
    };
    window.addEventListener('love530:modelselection', onSelection);

    const onFocus = () => {
      if (!host.isConnected) return;
      if (catalogCache.data && Date.now() - catalogCache.at > 60000) load(false, true);
    };
    window.addEventListener('focus', onFocus);

    updateLabel();
    load();

    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('love530:modelselection', onSelection);
      window.removeEventListener('focus', onFocus);
      if (panel.matches(':popover-open')) panel.hidePopover();
    };
  }

  function scan() {
    document.querySelectorAll('[data-model-picker]').forEach(host => {
      if (live.has(host) || host.shadowRoot) return;
      const cleanup = init(host);
      if (cleanup) live.set(host, cleanup);
    });
    for (const [host, cleanup] of live) {
      if (host.isConnected) continue;
      cleanup();
      live.delete(host);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan, { once: true });
  else scan();
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
})();
