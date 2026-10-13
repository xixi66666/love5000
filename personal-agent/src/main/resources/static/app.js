(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const items = data => Array.isArray(data) ? data : (data && (data.items || data.results)) || [];
  const date = value => {
    if (!value) return '时间未知';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(parsed);
  };
  const localInput = value => {
    if (!value) return '';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '';
    return new Date(parsed.getTime() + 8 * 3600000).toISOString().slice(0, 16);
  };
  const iso = value => value ? (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value) ? `${value}:00+08:00` : value) : undefined;
  const money = value => {
    if (value == null || value === '') return '未完整估值';
    const text = String(value), [integer, fraction] = text.split('.');
    return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction ? `.${fraction}` : ''}`;
  };
  const state = {csrf:'',initialized:false, page:'workspace',settings:{},dataStatus:{},records:new Map(),ideas:[],books:[],accounts:[],assets:[],memories:[],reviews:[],conversation:null,messages:[],chatJob:null,history:[],historyCursor:null,historyFilters:{},historyBack:[],historyCurrentCursor:null,idea:null,financeTab:'overview',readingTab:'notes',importPreview:null,viewToken:0,dialogSubmit:null};
  const pageMeta = {
    workspace:['YOUR PERSONAL SPACE','个人工作台','留住值得记住的事，看清值得迈出的下一步。'],
    ideas:['IDEAS INTO EVIDENCE','想法与行动','先记下来。选中以后，再用行动寻找答案。'],
    reading:['READ, LIVE & REFLECT','阅读与生活','书中的启发，你的理解，以及每天值得留下的片刻。'],
    finance:['YOUR FINANCIAL PICTURE','我的财富','记录真实的投入与变化，看清当下的资产和选择。'],
    memories:['A CONTINUOUS UNDERSTANDING','长期记忆','看见 Agent 如何理解你，也随时纠正它。'],
    history:['A STORY OVER TIME','历史与复盘','当前结论有据可查，过去的过程也不会遗失。'],
    settings:['YOUR SPACE, YOUR CONTROL','设置与资料','管理资料位置、使用范围，以及自己的节奏。']
  };
  const statuses = {inbox:'待选',validating:'验证中',active:'推进中',needs_review:'待核对',inactive:'已停用',paused:'暂停',completed:'已完成',ended:'已结束',open:'待行动',done:'已完成',cancelled:'已取消',unverified:'待验证',inconclusive:'证据不足',succeeded:'得到支持',failed:'未得到支持',queued:'排队中',running:'正在处理',waiting_config:'等待模型配置',waiting_configuration:'等待模型配置',waiting_budget:'等待预算',pending:'待处理',published:'已同步',conflict:'待核对'};
  const kinds = {life:'生活记录',insight:'个人见解',reading:'阅读笔记',idea:'想法',action:'行动',progress:'进展',result:'结果',book:'书籍',change:'变更',conversation:'对话',review:'复盘',memory:'记忆',snapshot:'财富快照'};
  const eventTypes = {income:'收入',expense:'支出',transfer:'账户转账',buy:'买入持仓',sell:'卖出持仓',dividend:'分红',interest:'利息收入',borrow:'借款',repay:'还本付息',asset_purchase:'购买手工资产',valuation_adjustment:'更新资产估值',balance_observation:'核对账户余额',position_observation:'核对持仓数量',liability_observation:'核对负债余额'};
  const content = $('#page-content');
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="/icons.svg#${name}"></use></svg>`;
  function remember(data) { items(data).forEach(record => { if (record.id) state.records.set(record.id, record); }); while (state.records.size > 1000) state.records.delete(state.records.keys().next().value); return items(data); }
  function notice(message, error = false) { const target = $('#notice'); target.textContent = message; target.classList.toggle('error',error); target.hidden = !message; }
  const empty = (title, detail) => `<div class="empty"><strong>${esc(title)}</strong>${esc(detail)}</div>`;
  const pill = (value, warning = false) => `<span class="pill${warning ? ' warning' : ''}">${esc(statuses[value] || value)}</span>`;
  const button = (label, action, id = '', className = 'small') => { const glyph = {'new-conversation':'plus','focus-quick-idea':'plus','record-detail':'arrow','read-review':'arrow','book-detail':'arrow','refresh':'history'}[action];return `<button type="button" class="${esc(className)}" data-action="${esc(action)}"${id ? ` data-id="${esc(id)}"` : ''}>${glyph ? icon(glyph) : ''}${esc(label)}</button>`; };
  function field(name, label, value = '', options = {}) {
    const id = `${options.prefix || 'field'}-${name}`;
    const required = options.required ? ' required' : '';
    const attr = `${required}${options.maxlength ? ` maxlength="${options.maxlength}"` : ''}${options.min != null ? ` min="${options.min}"` : ''}${options.max != null ? ` max="${options.max}"` : ''}${options.placeholder ? ` placeholder="${esc(options.placeholder)}"` : ''}`;
    let input;
    if (options.type === 'textarea') input = `<textarea id="${esc(id)}" name="${esc(name)}"${attr}>${esc(value)}</textarea>`;
    else if (options.type === 'select') input = `<select id="${esc(id)}" name="${esc(name)}"${required}>${(options.choices || []).map(choice => `<option value="${esc(choice[0])}"${String(value) === String(choice[0]) ? ' selected' : ''}>${esc(choice[1])}</option>`).join('')}</select>`;
    else if (options.type === 'checkbox') return `<label class="inline-check" for="${esc(id)}"><input type="checkbox" id="${esc(id)}" name="${esc(name)}"${value ? ' checked' : ''}>${esc(label)}</label>`;
    else input = `<input id="${esc(id)}" name="${esc(name)}" type="${esc(options.type || 'text')}" value="${esc(value)}"${options.decimal ? ' inputmode="decimal"' : ''}${attr}>`;
    return `<div${options.full ? ' class="full"' : ''}><label for="${esc(id)}">${esc(label)}</label>${input}${options.hint ? `<p class="hint">${esc(options.hint)}</p>` : ''}</div>`;
  }
  function form(name, body, label, extra = '') { return `<form data-form="${esc(name)}" class="stack${name === 'chat' ? ' composer' : ''}"${extra}>${body}<p class="form-error" role="alert" hidden></p><div class="button-row"><button type="submit" class="primary">${esc(label)}${name === 'chat' ? icon('send') : ''}</button></div></form>`; }
  function recordMeta(record) { return `<div class="record-meta"><span>${esc(kinds[record.kind] || record.kind || '')}</span><time>${esc(date(record.event_at || record.occurred_at || record.recorded_at))}</time>${!record.occurred_at ? '<span>发生时间未注明 · 按录入排序</span>' : ''}${record.important ? '<span>重要记录</span>' : ''}${record.status ? pill(record.status) : ''}</div>`; }
  function recordCard(record, actions = '') { return `<article class="record">${recordMeta(record)}<h3>${esc(record.title || '记录')}</h3><div class="record-body">${esc(record.content || '')}</div>${actions ? `<div class="record-actions">${actions}</div>` : ''}</article>`; }
  function safeUrl(value) { try { const parsed = new URL(value, location.origin); return ['http:','https:','obsidian:'].includes(parsed.protocol) ? parsed.href : null; } catch (_) { return null; } }
  async function api(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {'Accept':'application/json',...options.headers};
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && state.csrf) headers['X-CSRF-Token'] = state.csrf;
    const response = await fetch(path, {credentials:'same-origin',...options,method,headers,body:options.body !== undefined ? JSON.stringify(options.body) : undefined});
    let result; try { result = await response.json(); } catch (_) { throw new Error('服务暂时没有返回可读取的结果，请稍后重试。'); }
    if (!response.ok || result.success === false) {
      if (response.status === 401 && !path.startsWith('/api/auth/')) showAuth(true);
      const error = new Error(result.message || '操作未完成，请检查输入后重试。'); error.status = response.status; throw error;
    }
    return result.data === undefined ? result : result.data;
  }
  async function attempt(target, task) {
    const buttons = target && target.matches('button') ? [target] : target ? $$('button[type="submit"]',target) : [];
    const errorBox = target && $('.form-error',target);
    if (errorBox) errorBox.hidden = true;
    buttons.forEach(item => { item.dataset.oldText = item.textContent; item.textContent = '正在处理…'; item.disabled = true; });
    try { await task(); } catch (error) {
      if (errorBox) { errorBox.textContent = error.message; errorBox.hidden = false; } else notice(error.message,true);
    } finally { buttons.forEach(item => { item.textContent = item.dataset.oldText; item.disabled = false; }); }
  }
  function values(target) {
    const output = {};
    new FormData(target).forEach((value,key) => { if (typeof value === 'string' && value.trim() !== '') output[key] = value.trim(); });
    $$('input[type="checkbox"]',target).forEach(input => { output[input.name] = input.checked; });
    ['occurred_at','due_at','as_of'].forEach(key => { if (output[key]) output[key] = iso(output[key]); });
    return output;
  }
  function showAuth(initialized) {
    state.initialized = initialized;
    $('#initial-loading').hidden = true; $('#app-shell').hidden = true; $('#auth-screen').hidden = false;
    $('#auth-title').textContent = initialized ? '回到自己的空间' : '为自己留一处空间';
    $('#auth-description').textContent = initialized ? '记下今天，理解过去，慢慢走向你想要的未来。' : '先设置一个私人空间密码。资料将保存在这台电脑，之后可以用 Obsidian 查阅。';
    $('#auth-submit').textContent = initialized ? '进入空间' : '创建个人空间';
    $('#auth-confirm').hidden = initialized; $('#auth-confirm-label').hidden = initialized;
    $('#auth-confirm').required = !initialized;
    $('#auth-password').autocomplete = initialized ? 'current-password' : 'new-password';
    $('#auth-password').type = 'password'; $('#toggle-password').setAttribute('aria-pressed','false'); $('#toggle-password').setAttribute('aria-label','显示密码');
    $('#auth-password').value = ''; $('#auth-confirm').value = '';
    $('#auth-password').focus();
  }
  async function openApp(auth) {
    state.csrf = auth.csrf_token || state.csrf;
    $('#auth-screen').hidden = true; $('#initial-loading').hidden = true; $('#app-shell').hidden = false;
    $('#today').textContent = new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(new Date());
    try { state.settings = await api('/api/settings'); updateModelStatus(); } catch (error) { notice(error.message,true); }
    await navigate(location.hash.slice(1) || 'workspace');
    updateNotifications();
  }
  function updateModelStatus() { const target = $('#model-status'); target.textContent = state.settings.model_configured ? `${state.settings.model || 'AI'} 已配置` : '模型待配置 · 可继续记录'; target.classList.toggle('warning',!state.settings.model_configured); }
  async function updateNotifications() {
    try { const data = await api('/api/notifications'); const total = data.unread_count != null ? data.unread_count : data.unread != null ? data.unread : items(data).length; $('#unread-badge').textContent = total; $('#unread-badge').hidden = !total; } catch (_) { /* The current page shows relevant failures. */ }
  }
  async function navigate(page) {
    if (!pageMeta[page]) page = 'workspace';
    const token = ++state.viewToken; state.page = page; notice('');
    document.body.dataset.page = page; document.body.classList.remove('nav-open'); $('#nav-toggle').setAttribute('aria-expanded','false'); $('#nav-toggle').setAttribute('aria-label','展开导航');
    const meta = pageMeta[page]; $('#page-eyebrow').textContent = meta[0]; $('#page-title').textContent = meta[1]; $('#page-description').textContent = meta[2];
    $$('#navigation a').forEach(link => { const active = link.dataset.page === page; link.classList.toggle('active',active); if (active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
    content.innerHTML = '<div class="loading">正在读取你的记录…</div>';
    try {
      const renderers = {workspace:loadWorkspace,ideas:loadIdeas,reading:loadReading,finance:loadFinance,memories:loadMemories,history:loadHistory,settings:loadSettings};
      await renderers[page](token);
    } catch (error) { if (token === state.viewToken) { content.innerHTML = `${empty('暂时未能读取',error.message)}<div class="button-row" style="margin-top:16px">${button('重新读取','refresh')}</div>`; notice(error.message,true); } }
  }
  const current = token => token === state.viewToken;
  async function loadWorkspace(token) {
    const results = await Promise.all([api('/api/ideas?limit=20'),api('/api/reviews?limit=5'),api('/api/conversations?limit=8'),api('/api/data/status')]);
    if (!current(token)) return;
    state.ideas = remember(results[0]); state.reviews = remember(results[1]);
    const conversations = remember(results[2]), stats = results[3];
    const advancing = state.ideas.filter(idea => !['inbox','ended','completed','paused'].includes(idea.status));
    const hero = `<section class="workspace-hero"><div class="workspace-hero-copy"><p class="eyebrow">A SPACE TO THINK, REMEMBER & GROW</p><h2>让想法，<span>逐渐成真。</span></h2><p>记下一个念头，迈出一小步。把自己的判断，留给时间验证。</p><div class="button-row">${button('记录一个想法','focus-quick-idea','','primary')}<a class="text-link" href="#memories">看看我的长期记忆 ${icon('arrow')}</a></div></div><img class="workspace-wave" src="/silver-wave.svg" alt="" width="960" height="540"></section>`;
    const overview = `<div class="overview-strip"><a class="overview-item" href="#history"><span class="overview-item-label">${icon('history')}已留存记录</span><strong>${esc(stats.records)}<small>条</small></strong></a><a class="overview-item" href="#memories"><span class="overview-item-label">${icon('memory')}长期记忆</span><strong>${esc(stats.memories)}<small>条</small></strong></a><a class="overview-item" href="#ideas"><span class="overview-item-label">${icon('idea')}近期推进</span><strong>${advancing.length}<small>个</small></strong></a></div>`;
    const chat = `<section class="panel chat-panel"><div class="section-heading"><h2 class="heading-with-icon">${icon('spark')}和你的 Agent 对话</h2>${button('新对话','new-conversation')}</div><details class="conversation-archive"><summary>回到一段以前的对话</summary><div class="input-row conversation-switch"><div>${field('conversation','最近对话',state.conversation || '',{prefix:'workspace',type:'select',choices:[['','新对话'],...conversations.map(item => [item.id,item.title || date(item.recorded_at)])]})}</div>${button('打开','open-conversation')}</div></details><div id="conversation-messages" class="conversation"></div>${form('chat',`${field('content','一个问题，一段想法，或今天的片刻','',{prefix:'chat',type:'textarea',required:true,maxlength:12000,placeholder:'从你此刻最想聊的事情开始……'})}<div class="hint">消息与引用会一起留存，方便以后回看。</div>`,'发送消息',' id="chat-form"')}<p id="chat-job-status" class="hint" role="status"></p></section>`;
    const ideas = `<section class="panel"><div class="section-heading"><h2 class="heading-with-icon">${icon('idea')}值得推进的事</h2><a class="subtle-link" href="#ideas">全部 ${icon('arrow')}</a></div>${advancing.slice(0,3).map(idea => recordCard(idea,button('继续记录','select-idea',idea.id))).join('') || empty('一个好想法，从记下来开始','先保存，再决定哪一个值得迈出第一步。')}<hr class="row-separator">${form('quick-idea',`${field('title','随手记一个想法','',{prefix:'quick-idea',required:true,maxlength:200,placeholder:'有什么一直想试试的事？'})}${field('content','为什么想到它？（可选）','',{prefix:'quick-idea',type:'textarea',placeholder:'给这个念头留一点背景。'})}`,'保存到想法收件箱')}</section>`;
    const reviews = `<section class="panel"><div class="section-heading"><h2 class="heading-with-icon">${icon('history')}最近复盘</h2><a class="subtle-link" href="#history">回看 ${icon('arrow')}</a></div>${state.reviews.slice(0,2).map(review => recordCard(review,button('阅读报告','read-review',review.id))).join('') || empty('有变化，再慢慢回看','重要记录和明显变化会在这里留下复盘。')}</section>`;
    content.innerHTML = hero + overview + `<div class="workspace-layout">${chat}<div class="stack">${ideas}${reviews}</div></div>`;
    if (state.conversation) await refreshMessages(); else renderMessages();
    if (state.chatJob) pollChat(state.chatJob);
  }

  function citationHtml(citation) {
    if (typeof citation === 'string') return `<span class="citation">${esc(citation)}</span>`;
    const label = citation.title || citation.label || citation.source_title || citation.source_id || citation.id || '来源';
    const href = citation.url || citation.href ? safeUrl(citation.url || citation.href) : null;
    return `<span class="citation">${href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : esc(label)}${citation.location ? ` · ${esc(citation.location)}` : ''}${citation.as_of ? ` · ${esc(date(citation.as_of))}` : ''}${citation.excerpt || citation.content || citation.text ? `<br>${esc(citation.excerpt || citation.content || citation.text)}` : ''}</span>`;
  }
  function renderMessages() {
    const target = $('#conversation-messages'); if (!target) return;
    target.innerHTML = state.messages.length ? state.messages.map(message => `<article class="message${message.role === 'user' ? ' user' : ''}"><div class="message-role"><span>${message.role === 'user' ? '你' : 'PERSONAL AGENT'}</span><time>${esc(date(message.recorded_at || message.created_at))}</time></div><div class="message-content">${esc(message.content || message.answer || '')}</div>${(message.citations || (message.payload || {}).citations || []).length ? `<div class="citations">使用的资料${(message.citations || message.payload.citations).map(citationHtml).join('')}</div>` : ''}</article>`).join('') : (`<div class="empty"><div class="empty-orb">${icon('spark')}</div><strong>今天，想从哪里开始？</strong><span>你的阅读、想法和近况，都可以成为对话的起点。</span><div class="prompt-suggestions">${button('梳理一个想法','prompt-chat','帮我梳理一个想法，先一起明确最小尝试和验证标准。')}${button('回看我的近况','prompt-chat','结合我的近期记录，帮我回看值得关注的变化。')}${button('讨论资产配置','prompt-chat','结合已记录的财富状态，帮我分析长期资产配置与收入来源。')}</div></div>`);
    target.scrollTop = target.scrollHeight;
  }
  async function refreshMessages() { if (!state.conversation) return; const data = await api(`/api/conversations/${encodeURIComponent(state.conversation)}/messages?limit=50`); state.messages = items(data).map(message => ({...message,role:message.role || (message.payload || {}).role,citations:message.citations || (message.payload || {}).citations})).sort((a,b) => String(a.recorded_at || a.created_at).localeCompare(String(b.recorded_at || b.created_at))); renderMessages(); }
  const delay = duration => new Promise(resolve => setTimeout(resolve,duration));
  async function pollChat(jobId) {
    if (state.pollingChat === jobId) return;
    state.pollingChat = jobId;
    try {
      for (let attemptNumber = 0; attemptNumber < 90 && state.chatJob === jobId; attemptNumber += 1) {
        const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
        const target = $('#chat-job-status'); if (target) target.textContent = statuses[job.status] || '正在整理回答…';
        if (['succeeded','completed','failed','cancelled','waiting_config','waiting_configuration','waiting_budget'].includes(job.status)) {
          state.chatJob = null;
          state.lastChatJob = jobId;
          await refreshMessages();
          if (!['succeeded','completed'].includes(job.status)) {
            notice(job.message || job.error || (['waiting_config','waiting_configuration'].includes(job.status) ? '你的消息已保存。配置模型后可以继续获得回答。' : job.status === 'waiting_budget' ? '消息已保存，本次回答等待可用预算。' : '消息已保存，回答生成未完成，可以稍后重试。'),job.status === 'failed');
            if (target && job.status !== 'waiting_budget') target.insertAdjacentHTML('beforeend',` ${button('重新尝试这次回答','retry-chat',jobId)}`);
          }
          else {
            if (!state.messages.some(message => message.role !== 'user') && job.result && job.result.answer) { state.messages.push({role:'assistant',content:job.result.answer,citations:job.result.citations,recorded_at:new Date().toISOString()}); renderMessages(); }
            if (target) target.textContent = `回答已保存${job.result && job.result.memory_count ? `，整理了 ${job.result.memory_count} 条记忆` : ''}。`;
          }
          updateNotifications(); return;
        }
        await delay(2000);
      }
      if (state.chatJob === jobId) notice('回答仍在处理。你可以继续浏览，回到对话时会再次检查。');
    } catch (error) { notice(`消息已保存；${error.message}`,true); }
    finally { state.pollingChat = null; }
  }
  async function loadIdeas(token) {
    const data = await api('/api/ideas?limit=50'); if (!current(token)) return; state.ideas = remember(data);
    content.innerHTML = `<div class="grid-two"><section class="panel"><div class="section-heading"><h2>想法收件箱</h2><span class="muted">先保存，由你决定何时推进</span></div>${form('idea',`${field('title','想法名称','',{required:true,maxlength:200,placeholder:'我想尝试……'})}${field('content','动机与原始想法','',{type:'textarea',placeholder:'想解决什么？为什么对你重要？'})}`,'保存到待选')}<hr class="row-separator"><div class="input-row"><div>${field('idea-filter','查看状态','all',{prefix:'ideas',type:'select',choices:[['all','全部'],['inbox','待选'],['validating','验证中'],['active','推进中'],['paused','暂停'],['completed','已完成'],['ended','已结束']]})}</div></div><div id="idea-list" class="record-list" style="margin-top:18px"></div>${data.next_cursor ? button('加载更多想法','more-ideas',data.next_cursor) : ''}</section><section class="panel" id="idea-detail">${empty('选择一个想法','这里会显示当前状态、下一步行动，以及从开始到现在的过程。')}</section></div>`;
    renderIdeaList(); if (state.idea) await selectIdea(state.idea.id);
  }
  function renderIdeaList() {
    const filter = $('#ideas-idea-filter'); const selected = filter ? filter.value : 'all';
    const target = $('#idea-list'); if (!target) return;
    target.innerHTML = state.ideas.filter(idea => selected === 'all' || idea.status === selected).map(idea => `<article class="record${state.idea && state.idea.id === idea.id ? ' selected' : ''}">${recordMeta(idea)}<button class="record-title-button" data-action="select-idea" data-id="${esc(idea.id)}"><h3>${esc(idea.title)}</h3></button><div class="record-body">${esc(idea.content)}</div><div class="record-actions">${button('查看过程','select-idea',idea.id)}${idea.status === 'inbox' ? button('选中 · 开始验证','activate-idea',idea.id) : ''}</div></article>`).join('') || empty('这里暂时没有想法','随手保存一个，之后再决定要不要尝试。');
  }
  async function selectIdea(id) {
    if (state.page !== 'ideas') { state.idea = {id}; location.hash = 'ideas'; return; }
    const target = $('#idea-detail'); target.innerHTML = '<div class="loading">正在读取想法的过程…</div>';
    const results = await Promise.all([api(`/api/ideas/${encodeURIComponent(id)}`),api(`/api/ideas/${encodeURIComponent(id)}/actions?limit=50`),api(`/api/timeline?entity_id=${encodeURIComponent(id)}&limit=50`)]);
    if (state.page !== 'ideas') return;
    const idea = results[0]; state.idea = idea; state.records.set(id,idea);
    const actions = remember(results[1]), events = remember(results[2]).sort((a,b) => String(a.event_at || a.recorded_at).localeCompare(String(b.event_at || b.recorded_at)));
    const payload = idea.payload || {};
    target.innerHTML = `<div class="section-heading"><h2>${esc(idea.title)}</h2>${pill(idea.status)}</div><p class="record-body full">${esc(idea.content)}</p><div class="button-row">${button('编辑想法与验证标准','edit-idea',id)}${idea.status === 'inbox' ? button('选中 · 开始验证','activate-idea',id,'primary') : ''}</div>${idea.status !== 'inbox' ? `<div class="info-box"><p><strong>期望结果</strong><br>${esc(payload.expected_result || '尚未填写')}</p><p><strong>最小尝试与验证标准</strong><br>${esc(payload.minimal_attempt || '尚未填写')}<br>${esc(payload.success_criteria || '')}</p>${payload.investment_limit ? `<p><strong>投入上限</strong><br>${esc(payload.investment_limit)}</p>` : ''}</div><div class="input-row"><div>${field('status','当前状态',idea.status,{prefix:'idea-detail',type:'select',choices:[['validating','验证中'],['active','推进中'],['paused','暂停'],['completed','已完成'],['ended','已结束']]})}</div>${button('保存状态','idea-status',id)}</div><hr class="row-separator"><h3>下一步行动</h3>${actions.map(action => `<div class="action-item">${button(action.status === 'done' ? '已完成' : '完成','complete-action',action.id)}<div><strong class="${action.status === 'done' ? 'done' : ''}">${esc(action.title)}</strong>${action.content ? `<div class="record-body">${esc(action.content)}</div>` : ''}${(action.payload || {}).due_at ? `<p class="hint">计划时间：${esc(date(action.payload.due_at))}</p>` : ''}</div></div>`).join('') || '<p class="muted">尚无行动。先设定一个可观察结果的小尝试。</p>'}<details style="margin-top:16px"><summary>添加一项行动</summary>${form('action',`${field('title','要做的事情','',{prefix:'action',required:true,maxlength:200})}${field('content','具体做法与验证方式（可选）','',{prefix:'action',type:'textarea'})}${field('due_at','计划时间（可选）','',{prefix:'action',type:'datetime-local'})}`,'保存行动',` data-id="${esc(id)}"`)}</details><details><summary>记录进展或结果</summary>${form('idea-event',`${field('event_type','这次记录的是','progress',{prefix:'event',type:'select',choices:[['progress','行动进展'],['result','结果与反馈']]})}${field('title','记录标题','',{prefix:'event',required:true,maxlength:200})}${field('content','做了什么，得到什么证据','',{prefix:'event',type:'textarea',required:true})}${field('outcome','当前证据对想法的支持程度','unverified',{prefix:'event',type:'select',choices:[['unverified','仍待验证'],['inconclusive','证据不足'],['succeeded','得到支持'],['failed','未得到支持']]})}${field('occurred_at','实际发生时间（可选）','',{prefix:'event',type:'datetime-local'})}${field('important','这是值得复盘的重要反馈',false,{prefix:'event',type:'checkbox'})}`,'保存这次记录',` data-id="${esc(id)}"`)}</details>` : '<div class="info-box">尚未选中推进。记录本身已经保存，不会自动创建行动或替你判断结果。</div>'}<hr class="row-separator"><h3>过程与结果 · 从开始往后看</h3><div class="timeline-list">${events.map(event => `<article class="timeline-event"><time>${esc(date(event.event_at || event.recorded_at))}</time><h3>${esc(event.title)}</h3><div class="record-meta">${pill(kinds[event.kind] || event.kind)}</div><div class="record-body">${esc(event.content)}</div></article>`).join('') || '<p class="muted">还没有过程记录。</p>'}</div>${results[2].next_cursor ? '<p class="hint">目前显示最近 50 条。完整历史可在“历史与复盘”按关联想法查找。</p>' : ''}`;
    renderIdeaList();
  }
  async function loadReading(token) {
    const data = await Promise.all([api('/api/notes?limit=50'),api('/api/books?limit=50')]); if (!current(token)) return;
    state.notes = remember(data[0]); state.books = remember(data[1]);
    content.innerHTML = `<div class="tabs">${[['notes','笔记与生活'],['books','我的书库'],['search','查找相关资料']].map(([id,label]) => `<button data-action="reading-tab" data-id="${id}" class="${state.readingTab === id ? 'active' : ''}">${label}</button>`).join('')}</div><div id="reading-content"></div>`;
    renderReading();
  }
  function renderReading() {
    const target = $('#reading-content'); if (!target) return;
    $$('.tabs button',content).forEach(item => item.classList.toggle('active',item.dataset.id === state.readingTab));
    if (state.readingTab === 'notes') {
      target.innerHTML = `<div class="grid-two"><section class="panel"><h2>记下值得留下的内容</h2>${form('note',`${field('kind','记录类型','insight',{prefix:'note',type:'select',choices:[['insight','个人见解'],['life','生活记录'],['reading','阅读笔记']]})}${field('title','标题','',{prefix:'note',required:true,maxlength:200})}${field('content','原始内容','',{prefix:'note',type:'textarea',required:true,placeholder:'可以是一个片段、一段自己的理解，或一件发生过的事情。'})}${field('book_id','关联书籍（可选）','',{prefix:'note',type:'select',choices:[['','不关联书籍'],...state.books.map(book => [book.id,book.title])]})}${field('occurred_at','实际发生时间（可选）','',{prefix:'note',type:'datetime-local',hint:'补录旧事时填写它。留空会明确标记时间未知。'})}${field('important','这是一条重要记录，值得适时复盘',false,{prefix:'note',type:'checkbox'})}`,'保存原始记录')}</section><section class="panel"><div class="section-heading"><h2>最近录入</h2>${button('刷新','refresh')}</div><div class="record-list">${(state.notes || []).map(note => recordCard(note,button('编辑或更正','edit-note',note.id)+button('删除','delete-note',note.id,'small danger'))).join('') || empty('记录从一个片刻开始','原文会保留，之后可以按时间、主题或相关想法找回。')}</div></section></div>`;
    } else if (state.readingTab === 'books') {
      target.innerHTML = `<div class="grid-two"><section><div class="book-grid">${state.books.map((book,index) => `<article class="book-card"><span class="book-number">BOOK ${String(index + 1).padStart(2,'0')}</span><h3>${esc(book.title)}</h3><p class="muted">${esc((book.payload || {}).author || book.author || '作者待补充')}</p><p class="hint">${esc((book.payload || {}).source_type || '已保存书籍资料')} · ${esc(date(book.recorded_at))}</p>${button('查看书籍资料','book-detail',book.id)}</article>`).join('') || empty('慢慢建立自己的书库','先接入一本现有读书 skill，或保存一本书的资料。')}</div><div id="book-detail" style="margin-top:24px"></div></section><section class="panel"><h2>补充阅读材料</h2><details open><summary>发现已有读书 skill</summary><p class="hint">只读取你选择的书籍与资料。原 skill 文件保持原状。</p>${button('查找可用 skill','discover-skills')}<div id="skill-list" class="record-list" style="margin-top:16px"></div></details><details><summary>保存书籍资料与笔记</summary>${form('book',`${field('title','书名','',{prefix:'book',required:true,maxlength:200})}${field('author','作者（可选）','',{prefix:'book'})}${field('content','这本书的资料或你的笔记','',{prefix:'book',type:'textarea',required:true})}`,'保存书籍')}</details><details><summary>导入本机书源文件</summary>${form('book-file',`${field('file_path','书源文件的完整路径','',{prefix:'source',required:true,placeholder:'已允许的书源目录下的文件'})}<p class="hint">允许的目录由本机配置决定。文件格式不受支持时会明确提示。</p>`,'读取并导入')}</details></section></div>`;
    } else {
      target.innerHTML = `<section class="panel"><h2>从过去的记录里寻找相关内容</h2>${form('search',`${field('query','想找什么','',{prefix:'search',required:true,placeholder:'一句观点、一本书、一件经历……'})}`,'查找资料')}<div id="search-results" class="record-list" style="margin-top:24px">${empty('从一个问题开始','结果会保留对应资料与时间，便于核对。')}</div></section>`;
    }
  }
  async function loadFinance(token) {
    const data = await Promise.all([api('/api/finance/summary'),api('/api/finance/accounts?limit=100'),api('/api/finance/assets?limit=100'),api('/api/finance/events?limit=50'),api('/api/finance/snapshots?limit=20')]); if (!current(token)) return;
    state.summary = data[0]; state.accounts = items(data[1]); state.assets = items(data[2]); state.financeEvents = items(data[3]); state.snapshots = items(data[4]);
    content.innerHTML = `<div class="tabs">${[['overview','财富概览'],['accounts','账户与资产'],['events','记录收支与变动'],['import','CSV 导入']].map(([id,label]) => `<button data-action="finance-tab" data-id="${id}" class="${state.financeTab === id ? 'active' : ''}">${label}</button>`).join('')}</div><div id="finance-content"></div>`;
    renderFinance();
  }
  function optionsFor(list, label = '请选择') { return [['',label],...list.map(item => [item.id,`${item.name || item.title} · ${item.currency || 'CNY'}`])]; }
  function renderFinance() {
    const target = $('#finance-content'); if (!target) return; const summary = state.summary || {};
    $$('.tabs button',content).forEach(item => item.classList.toggle('active',item.dataset.id === state.financeTab));
    if (state.financeTab === 'overview') {
      target.innerHTML = `<div class="summary-band"><div class="metric"><div class="metric-label">${summary.complete ? '当前净资产' : '已覆盖部分净资产'}</div><div class="metric-value">${esc(money(summary.complete ? summary.net_worth : summary.known_net_worth))}</div><div class="metric-note">${esc(summary.base_currency || 'CNY')} · ${summary.complete ? '估值覆盖完整' : '尚有资料未覆盖'}</div></div><div class="metric"><div class="metric-label">${summary.complete ? '资产合计' : '已覆盖资产'}</div><div class="metric-value">${esc(money(summary.complete ? summary.total_assets : summary.known_total_assets))}</div><div class="metric-note">现金、持仓与手工资产</div></div><div class="metric"><div class="metric-label">${summary.complete ? '负债合计' : '已覆盖负债'}</div><div class="metric-value">${esc(money(summary.complete ? summary.total_liabilities : summary.known_total_liabilities))}</div><div class="metric-note">贷款与其他负债</div></div></div>${!summary.complete ? `<div class="info-box warning"><strong>这份概览尚未覆盖全部资产</strong><p>缺少可靠价格、汇率或估值的项目不会按零计入。当前显示已覆盖部分，补齐资料后再比较完整总额。</p>${(summary.missing || []).map(item => `<p>${esc(item.name || item.id || '项目')}：${esc(item.reason || '资料待补充')}</p>`).join('')}</div>` : ''}<div class="refresh-line"><p class="hint">截至：${esc(date(summary.as_of || new Date().toISOString()))} · 账本版本 ${esc(summary.ledger_revision || 0)}</p><div class="button-row">${button('更新支持的市场价格','refresh-quotes')}${button('保存财富快照','save-snapshot')}</div></div><div class="grid-equal"><section class="panel"><h2>资产分布</h2>${renderCategories(summary.by_category)}<h3 style="margin-top:24px">现金流</h3><dl class="definition-list">${Object.entries({收入:(summary.cash_flow || {}).income,支出:(summary.cash_flow || {}).expense,投资现金收入:(summary.cash_flow || {}).investment_income,手续费:(summary.cash_flow || {}).fees}).map(([label,value]) => `<dt>${label}</dt><dd class="number">${esc(money(value || '0'))} ${esc(summary.base_currency || 'CNY')}</dd>`).join('')}</dl><p class="hint" style="margin-top:18px">账户转账、贷款与估值调整单独记录，不作为普通收入。</p></section><section class="panel"><h2>历史快照</h2>${state.snapshots.map(snapshot => `<article class="record"><div class="record-meta"><time>${esc(date(snapshot.as_of || snapshot.recorded_at || snapshot.created_at))}</time>${pill(snapshot.complete ? '完整估值' : '部分估值',!snapshot.complete)}</div><h3>${esc(money(snapshot.net_worth || snapshot.known_net_worth))} ${esc(snapshot.base_currency || 'CNY')}</h3></article>`).join('') || empty('给今天留一张快照','保存明确时点的财富状态，之后比较时更有依据。')}</section></div>`;
    } else if (state.financeTab === 'accounts') {
      target.innerHTML = `<div class="grid-equal"><section class="panel"><h2>账户</h2>${state.accounts.length ? `<div class="table-wrap"><table><thead><tr><th>账户</th><th>余额</th><th>截至时间</th></tr></thead><tbody>${state.accounts.map(account => `<tr><td>${esc(account.name)}<br><small>${esc(account.type)} · ${esc(account.currency)}</small><details style="padding:2px 6px"><summary style="font-size:11px">账户标识</summary><span class="code-hint">${esc(account.id)}</span></details></td><td class="number">${esc(money(account.balance))}</td><td>${esc(date(account.as_of))}</td></tr>`).join('')}</tbody></table></div>` : empty('从一个账户开始','只需一个自定义名称，不需要真实银行卡号。')}<details><summary>添加账户</summary>${form('finance-account',`<div class="form-grid">${field('name','账户名称','',{prefix:'account',required:true,maxlength:100,placeholder:'例如：日常银行卡'})}${field('type','账户类型','bank',{prefix:'account',type:'select',choices:[['bank','银行账户'],['cash','现金'],['brokerage','证券账户']]})}${field('currency','币种','CNY',{prefix:'account',required:true,maxlength:3})}${field('balance','当前余额','0',{prefix:'account',decimal:true,required:true})}${field('as_of','余额截至时间',localInput(new Date().toISOString()),{prefix:'account',type:'datetime-local',required:true})}${field('basis','余额依据','observation',{prefix:'account',type:'select',choices:[['observation','当前余额观测'],['opening','期初余额']]})}</div>`,'保存账户')}</details></section><section class="panel"><h2>持仓、资产与负债</h2>${state.assets.length ? `<div class="record-list">${state.assets.map(asset => `<article class="record"><div class="record-meta"><span>${esc(({position:'金融持仓',manual:'手工资产',liability:'负债'})[asset.kind] || asset.kind)}</span><span>${esc(asset.category || '')}</span><span>${esc(asset.currency)}</span></div><h3>${esc(asset.name)}</h3><p class="number">${asset.kind === 'position' ? `数量 ${esc(asset.quantity)} · 价格 ${esc(asset.price || '待更新')}` : esc(money(asset.value != null ? asset.value : asset.balance))}</p>${asset.symbol ? `<p class="hint">代码：${esc(asset.symbol)}</p>` : ''}<p class="hint">截至 ${esc(date(asset.as_of))}</p><details style="padding:4px 9px"><summary class="hint">查看资产标识</summary><span class="code-hint">${esc(asset.id)}</span></details></article>`).join('')}</div>` : empty('建立完整的财富图景','持仓、房产等手工资产与负债在这里各自记录。')}<details style="margin-top:16px"><summary>添加资产或负债</summary>${form('finance-asset',`<div class="form-grid">${field('name','名称','',{prefix:'asset',required:true,maxlength:100})}${field('kind','资产类型','position',{prefix:'asset',type:'select',choices:[['position','金融持仓'],['manual','手工资产'],['liability','负债']]})}${field('category','类别','stock',{prefix:'asset',type:'select',choices:[['stock','股票'],['etf','ETF'],['fund','其他基金'],['property','房产'],['gold','黄金'],['business','个人项目或股权'],['loan','贷款'],['other','其他']]})}${field('account_id','关联账户（持仓必选）','',{prefix:'asset',type:'select',choices:optionsFor(state.accounts,'未关联账户')})}${field('currency','币种','CNY',{prefix:'asset',required:true,maxlength:3})}${field('as_of','截至时间',localInput(new Date().toISOString()),{prefix:'asset',type:'datetime-local',required:true})}</div><div id="asset-specific-fields">${assetSpecificFields('position')}</div>${field('basis','数据依据','observation',{prefix:'asset',type:'select',choices:[['observation','当前余额或持仓观测'],['opening','期初记录']]})}`,'保存资产记录')}</details></section></div>`;
    } else if (state.financeTab === 'events') {
      target.innerHTML = `<div class="grid-two"><section class="panel"><h2>记录真实发生的变化</h2>${form('finance-event',`${field('type','变动类型','expense',{prefix:'finance-event',type:'select',choices:Object.entries(eventTypes)})}${field('occurred_at','发生时间',localInput(new Date().toISOString()),{prefix:'finance-event',type:'datetime-local',required:true})}<div id="finance-event-fields">${financeEventFields('expense')}</div>${field('note','说明（可选）','',{prefix:'finance-event',type:'textarea',maxlength:2000})}`,'核对并提交账本')}<p class="hint" style="margin-top:16px">提交后将影响正式账本。金额按原币种记录，转账需要相同币种账户。</p></section><section class="panel"><h2>最近账本记录</h2>${state.financeEvents.map(event => `<article class="record"><div class="record-meta"><span>${esc(eventTypes[event.type] || event.type)}</span><time>${esc(date(event.occurred_at))}</time>${event.reverted ? pill('已撤销',true) : ''}</div><h3 class="number">${esc(event.amount != null ? money(event.amount) : `${event.quantity || ''} 份`)}</h3><p class="record-body">${esc(event.note || '')}</p></article>`).join('') || empty('还没有财务变动记录','先建立账户和资产，再记录收支、交易或估值变化。')}</section></div>`;
    } else {
      target.innerHTML = `<section class="panel"><h2>先预览，再提交</h2><p class="muted">上传或粘贴 CSV 后，先检查重复、错误与冲突。只有你明确提交才会写入账本。</p><details><summary>CSV 格式与标识</summary><p class="code-hint">type,occurred_at,account_id,to_account_id,asset_id,liability_id,amount,quantity,price,fee,interest,external_id</p><p class="hint">使用本页账户与资产的稳定标识。金额填写原币种的小数文本；日期建议包含时区。可先保存一条正式记录理解对应字段。</p><div class="table-wrap"><table><thead><tr><th>名称</th><th>稳定标识</th></tr></thead><tbody>${[...state.accounts,...state.assets].map(item => `<tr><td>${esc(item.name)}</td><td class="code-hint">${esc(item.id)}</td></tr>`).join('')}</tbody></table></div></details>${form('finance-import',`<div><label for="csv-file">读取本机 CSV（可选）</label><input id="csv-file" type="file" accept=".csv,text/csv"></div>${field('csv_text','CSV 内容','',{prefix:'csv',type:'textarea',required:true,placeholder:'粘贴包含表头的 CSV 内容'})}`,'生成导入预览')}<div id="import-preview" style="margin-top:24px"></div></section>`;
      if (state.importPreview) renderImportPreview();
    }
  }
  function renderCategories(value) {
    if (!value || !(Array.isArray(value) ? value.length : Object.keys(value).length)) return empty('还没有资产分布','保存账户、持仓和手工资产以后会显示。');
    const entries = Array.isArray(value) ? value.map(item => [item.category || item.name,item.value || item.amount]) : Object.entries(value);
    return `<dl class="definition-list">${entries.map(([label,amount]) => `<dt>${esc(label)}</dt><dd class="number">${esc(money(typeof amount === 'object' ? amount.value || amount.amount : amount))}</dd>`).join('')}</dl>`;
  }
  function assetSpecificFields(kind) {
    return kind === 'position' ? `<div class="form-grid">${field('symbol','市场代码（可选）','',{prefix:'asset',placeholder:'例如 sh600519 或 sz159915'})}${field('quantity','持仓数量','',{prefix:'asset',required:true,decimal:true})}${field('price','单价（可选）','',{prefix:'asset',decimal:true,hint:'没有可靠单价时会标记估值未覆盖。'})}</div>` : field(kind === 'manual' ? 'value' : 'balance',kind === 'manual' ? '当前估值' : '未偿还余额','',{prefix:'asset',required:true,decimal:true});
  }
  function financeEventFields(type) {
    const parts = [];
    if (type !== 'valuation_adjustment') parts.push(field('account_id','账户','',{prefix:'evt',type:'select',required:type !== 'liability_observation' && type !== 'position_observation',choices:optionsFor(state.accounts)}));
    if (type === 'transfer') parts.push(field('to_account_id','转入账户','',{prefix:'evt',type:'select',required:true,choices:optionsFor(state.accounts)}));
    if (['buy','sell','position_observation','asset_purchase','valuation_adjustment'].includes(type)) parts.push(field('asset_id','关联资产','',{prefix:'evt',type:'select',required:true,choices:optionsFor(state.assets.filter(asset => type === 'asset_purchase' ? asset.kind === 'manual' : ['buy','sell','position_observation'].includes(type) ? asset.kind === 'position' : asset.kind !== 'liability'))}));
    if (['borrow','repay','liability_observation','asset_purchase'].includes(type)) parts.push(field('liability_id',type === 'asset_purchase' ? '关联贷款（可选）' : '关联负债','',{prefix:'evt',type:'select',required:type !== 'asset_purchase',choices:optionsFor(state.assets.filter(asset => asset.kind === 'liability'))}));
    if (['buy','sell','position_observation'].includes(type)) parts.push(field('quantity',type === 'position_observation' ? '核对后的持仓数量' : '交易数量','',{prefix:'evt',required:true,decimal:true}));
    if (['buy','sell'].includes(type)) parts.push(field('price','成交单价','',{prefix:'evt',required:true,decimal:true}),field('fee','手续费（可选）','',{prefix:'evt',decimal:true}));
    else if (type !== 'position_observation') parts.push(field('amount',type === 'valuation_adjustment' ? '更新后的资产估值' : type === 'balance_observation' ? '核对后的账户余额' : type === 'liability_observation' ? '核对后的未偿还余额' : '金额','',{prefix:'evt',required:true,decimal:true}));
    if (type === 'repay') parts.push(field('interest','本次利息（可选）','',{prefix:'evt',decimal:true,hint:'本金填在金额栏，利息在这里单独记录。'}));
    if (type === 'asset_purchase') parts.push(field('loan_amount','其中借款金额（可选）','',{prefix:'evt',decimal:true}));
    return `<div class="form-grid">${parts.join('')}</div>`;
  }
  function renderImportPreview() {
    const preview = state.importPreview, target = $('#import-preview'); if (!target) return;
    target.innerHTML = `<h3>导入预览</h3><div class="info-box${preview.valid ? '' : ' warning'}">${preview.valid ? '校验完成。核对明细后可正式提交；重复记录不会重复记账。' : '发现无效或冲突记录，请先修改 CSV 后重新预览。'}</div><div class="table-wrap"><table><thead><tr><th>行</th><th>状态</th><th>内容</th><th>说明</th></tr></thead><tbody>${(preview.rows || []).map(row => `<tr><td>${esc(row.line)}</td><td class="status-${esc(row.status)}">${esc(({new:'待导入',duplicate:'重复',conflict:'冲突',error:'错误'})[row.status] || row.status)}</td><td>${esc(eventTypes[(row.event || {}).type] || (row.event || {}).type || '')}<br>${esc((row.event || {}).amount || (row.event || {}).quantity || '')}</td><td>${esc(row.message || '')}</td></tr>`).join('')}</tbody></table></div><div class="button-row">${preview.valid && !preview.committed ? button('确认 · 提交入库','commit-import',preview.id,'primary') : ''}${preview.committed ? button('撤销这批导入','revert-import',preview.id,'danger') : ''}</div>`;
  }
  async function loadMemories(token) {
    const data = await api('/api/memories?limit=50'); if (!current(token)) return; state.memories = remember(data);
    content.innerHTML = `<div class="info-box">这里只整理你明确提供的内容。你可以纠正、停用或删除记忆；历史来源与当前有效内容分开处理。</div><section class="panel"><div class="section-heading"><h2>Agent 当前记住的内容</h2>${button('刷新','refresh')}</div><div class="record-list">${state.memories.map(memory => `<article class="record"><div class="record-meta"><span>${esc(({fact:'事实',preference:'偏好',goal:'目标',opinion:'观点'})[memory.kind] || kinds[memory.kind] || memory.kind || '记忆')}</span><time>${esc(date(memory.updated_at || memory.recorded_at))}</time>${pill(memory.status || 'active')}</div><h3>${esc(memory.title || '关于你的记忆')}</h3><div class="record-body full">${esc(memory.content || memory.assertion || '')}</div>${memory.source_id || memory.source_ids || (memory.payload || {}).source_id ? `<p class="hint">来源：${esc(memory.source_id || (memory.source_ids || []).join(' · ') || memory.payload.source_id)}</p>` : ''}${memory.valid_from || memory.valid_to ? `<p class="hint">适用时间：${esc(date(memory.valid_from))} 至 ${esc(memory.valid_to ? date(memory.valid_to) : '现在')}</p>` : ''}<div class="record-actions">${button('纠正内容','edit-memory',memory.id)}${button(memory.status === 'inactive' ? '恢复使用' : '停用','toggle-memory',memory.id)}${button('删除记忆','delete-memory',memory.id,'small danger')}</div></article>`).join('') || empty('记忆会在交流中逐渐积累','保存你的明确事实、偏好与见解后，Agent 可以在以后按需使用。未配置模型时原始记录仍然会保存。')}</div>${data.next_cursor ? button('加载更多记忆','more-memories',data.next_cursor) : ''}</section>`;
  }
  async function loadHistory(token, append = false) {
    const query = new URLSearchParams({limit:'50',...state.historyFilters});
    if (append && state.historyCursor) { state.historyBack.push(state.historyCurrentCursor); state.historyCurrentCursor = state.historyCursor; }
    if (state.historyCurrentCursor) query.set('cursor',state.historyCurrentCursor);
    const data = await Promise.all([api(`/api/timeline?${query}`),api('/api/reviews?limit=30')]); if (!current(token)) return;
    const newHistory = remember(data[0]); state.history = newHistory; state.historyCursor = data[0].next_cursor || null; state.reviews = remember(data[1]);
    content.innerHTML = `<div class="grid-two"><section class="panel"><h2>按时间找回记录</h2>${form('history-filter',`<div class="form-grid">${field('q','关键词',state.historyFilters.q || '',{prefix:'history',placeholder:'标题或原文中的内容'})}${field('kind','记录类型',state.historyFilters.kind || '',{prefix:'history',type:'select',choices:[['','全部类型'],...Object.entries(kinds)]})}${field('entity_id','关联想法或记录标识（可选）',state.historyFilters.entity_id || '',{prefix:'history',placeholder:'使用记录的稳定标识'})}</div>`,'应用筛选')}<div class="refresh-line" style="margin-top:24px"><p class="hint">按实际发生时间倒序；未知时按首次录入时间。更正时间不会改变记录身份。</p>${button('回到最新','latest-history')}</div><div class="record-list">${state.history.map(record => recordCard(record,button('查看详情','record-detail',record.id))).join('') || empty('没有符合条件的记录','可以修改关键词或记录类型，重新查找。')}</div>${state.historyCursor ? `<div class="button-row" style="margin-top:18px">${button('加载更早的记录','more-history')}</div>` : ''}</section><section class="panel"><div class="section-heading"><h2>复盘报告</h2>${button('申请一次复盘','request-review')}</div><p class="hint">只在重要记录或明显变化时生成；没有变化时保持安静。你也可以主动请求一次。</p><div class="record-list">${state.reviews.map(review => recordCard(review,pill((review.payload || {}).read || review.read_at ? '已读' : '未读')+button('阅读报告','read-review',review.id))).join('') || empty('还没有复盘报告','先积累记录，或主动选择一次值得回看的变化。')}</div></section></div>`;
    const historyToolbar = $('.refresh-line',content);
    if (historyToolbar) historyToolbar.insertAdjacentHTML('beforeend',`${state.historyBack.length ? button('返回上一页','previous-history') : ''}<span class="hint">第 ${state.historyBack.length + 1} 页 · 每页最多 50 条</span>`);
    updateNotifications();
  }
  async function loadSettings(token) {
    const data = await Promise.all([api('/api/settings'),api('/api/data/status')]); if (!current(token)) return;
    state.settings = data[0]; state.dataStatus = data[1]; updateModelStatus(); const settings = state.settings.settings || {};
    content.innerHTML = `<div class="grid-equal"><section class="panel"><h2>资料一直留在你这里</h2><p class="muted">用 Obsidian 桌面端“打开文件夹作为仓库”，选择下面的专属资料库即可查阅长期记录。</p><dl class="definition-list"><dt>本机资料目录</dt><dd class="path">${esc(state.settings.data_dir || state.dataStatus.data_dir || '尚未读取')}</dd><dt>Obsidian 专属库</dt><dd class="path">${esc(state.settings.vault_dir || state.dataStatus.vault_dir || '尚未读取')}</dd><dt>模型状态</dt><dd>${esc(state.settings.model_configured ? '已配置，可按需分析' : '待配置；记录、检索和财务功能可以继续使用')}</dd></dl><div class="info-box"><p>网页管理结构化记录。Obsidian 中“原始笔记”和“人工心得”用于自由编辑；生成页面的外部修改会进入待核对，不静默覆盖。</p><p>模型密钥由本机环境配置管理，这里不会显示或保存密钥。</p></div><hr class="row-separator"><h3>资料状态</h3><dl class="definition-list">${Object.entries({记录数量:state.dataStatus.records,记忆数量:state.dataStatus.memories,等待处理:state.dataStatus.pending_jobs,等待同步:state.dataStatus.publish_pending,待核对:state.dataStatus.conflicts,缺失书源:state.dataStatus.source_missing}).map(([label,value]) => `<dt>${esc(label)}</dt><dd>${esc(value == null ? '未知' : Array.isArray(value) ? value.length : value)}</dd>`).join('')}<dt>上次备份</dt><dd>${esc(state.dataStatus.last_backup ? date(typeof state.dataStatus.last_backup === 'object' ? state.dataStatus.last_backup.created_at : state.dataStatus.last_backup) : '尚无备份')}</dd></dl><div class="button-row" style="margin-top:22px">${button('重新整理资料索引','reindex')}${button('创建本机备份','backup')}${button('查看与恢复备份','show-backups')}${button('刷新状态','refresh')}</div><div id="data-job-status" class="hint" style="margin-top:15px" role="status"></div></section><section class="panel"><h2>以你的节奏工作</h2>${form('settings',`${field('model','模型名称',settings.model || state.settings.model || 'deepseek-chat',{prefix:'settings',required:true,maxlength:100})}${field('api_base','模型服务地址',settings.api_base || state.settings.api_base || 'https://api.deepseek.com',{prefix:'settings',type:'url',required:true,hint:'修改服务地址时，请同步检查本机环境中的对应密钥。'})}<hr class="row-separator"><h3>分析范围</h3>${field('auto_memory','自动整理我明确提供的事实、偏好和观点',settings.auto_memory !== false,{prefix:'settings',type:'checkbox'})}${field('public_search','允许查询公开资料（私人内容不作为公开搜索词）',!!settings.public_search,{prefix:'settings',type:'checkbox'})}<hr class="row-separator"><h3>复盘与调用预算</h3><div class="form-grid">${field('review_daily_budget','每日最多自动复盘次数',settings.review_daily_budget || 6,{prefix:'settings',type:'number',min:1,max:1440,required:true})}${field('review_cooldown_hours','同类复盘间隔（小时）',settings.review_cooldown_hours || 24,{prefix:'settings',type:'number',min:1,max:1440,required:true})}${field('review_merge_minutes','合并近期变化（分钟）',settings.review_merge_minutes || 5,{prefix:'settings',type:'number',min:1,max:1440,required:true})}${field('quote_refresh_minutes','行情刷新间隔（分钟）',settings.quote_refresh_minutes || 5,{prefix:'settings',type:'number',min:1,max:1440,required:true})}${field('investment_change_percent','投资估值变化阈值（%）',settings.investment_change_percent || '5',{prefix:'settings',decimal:true,required:true})}${field('net_worth_change_amount','净资产变化金额阈值',settings.net_worth_change_amount || '10000',{prefix:'settings',decimal:true,required:true})}</div><p class="hint">触发条件满足后仍会合并变化、检查间隔与预算，避免反复提醒。服务关闭时不会发送通知。</p>`,'保存设置')}</section></div>`;
    if (state.page === 'settings' && Array.isArray(state.dataStatus.conflicts) && state.dataStatus.conflicts.length) { const target = $('#data-job-status'); target.insertAdjacentHTML('afterend', `<section class="panel"><h3>手工修改待核对</h3>${state.dataStatus.conflicts.map(entry => `<p class="path">${esc(entry.path)} ${button('保留手工副本并发布网页版本','resolve-conflict',entry.record_id)}</p>`).join('')}</section>`); }
  }
  function openEditor(title, body, handler) {
    $('#dialog-title').textContent = title; $('#editor-fields').innerHTML = `<div class="dialog-fields">${body}</div>`; $('#editor-error').hidden = true; state.dialogSubmit = handler;
    $('#editor-dialog').showModal(); const input = $('input,textarea,select',$('#editor-fields')); if (input) input.focus();
  }
  async function editRecord(id, memory = false) {
    const record = state.records.get(id); if (!record) throw new Error('请先刷新记录再编辑。');
    const isIdea = record.kind === 'idea'; const payload = record.payload || {};
    openEditor(memory ? '纠正 Agent 对你的记忆' : isIdea ? '编辑想法与验证标准' : '编辑原始记录',`${!memory ? field('title','标题',record.title,{prefix:'editor',required:true,maxlength:200}) : ''}${field('content',memory ? '准确的内容' : '内容',record.content || record.assertion || '',{prefix:'editor',type:'textarea',required:true})}${!memory ? field('occurred_at','实际发生时间（可选）',localInput(record.occurred_at),{prefix:'editor',type:'datetime-local'}) : ''}${isIdea ? `${field('expected_result','期望结果',payload.expected_result || '',{prefix:'editor',type:'textarea'})}${field('minimal_attempt','最小尝试',payload.minimal_attempt || '',{prefix:'editor',type:'textarea'})}${field('success_criteria','怎样判断验证结果',payload.success_criteria || '',{prefix:'editor',type:'textarea'})}${field('investment_limit','时间或资金投入上限（可选）',payload.investment_limit || '',{prefix:'editor'})}` : ''}${field('erroneous','这次是纠正旧记录中的错误（与真实变化区分）',false,{prefix:'editor',type:'checkbox'})}`, async values => {
      values.expected_revision = record.revision;
      if (isIdea) { values.payload = {expected_result:values.expected_result || '',minimal_attempt:values.minimal_attempt || '',success_criteria:values.success_criteria || '',investment_limit:values.investment_limit || ''}; }
      if (!memory && !values.occurred_at) values.occurred_at = null;
      await api(`/api/${memory ? 'memories' : isIdea ? 'ideas' : 'notes'}/${encodeURIComponent(id)}`,{method:'PATCH',body:values});
      $('#editor-dialog').close(); await navigate(state.page); notice('修改已保存，原有版本保持可追溯。');
    });
  }
  async function pollDataJob(jobId, label) {
    for (let number = 0; number < 60; number += 1) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`); const target = $('#data-job-status'); if (target) target.textContent = `${label}：${statuses[job.status] || job.status}`;
      if (['succeeded','completed'].includes(job.status)) { notice(`${label}已完成。`); return; }
      if (['failed','waiting_config','waiting_configuration','waiting_budget'].includes(job.status)) throw new Error(job.message || `${label}暂未完成，请稍后重试。`);
      await delay(2000);
    }
    notice(`${label}仍在处理，稍后刷新资料状态查看。`);
  }
  const actions = {
    'focus-quick-idea':async () => { const input = $('[data-form="quick-idea"] input[name="title"]');if(input){ input.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});input.focus({preventScroll:true}); } },
    'prompt-chat':async prompt => { const input = $('[data-form="chat"] textarea[name="content"]');if(input){ input.value = prompt; input.focus(); } },
    'resolve-conflict':async id => { await api(`/api/data/conflicts/${encodeURIComponent(id)}/resolve`,{method:'POST',body:{keep_manual:true}}); await navigate('settings'); notice('手工修改已另存为人工心得，网页记录已重新发布。'); },
    'show-backups':async () => { const data=await api('/api/data/backups'); openEditor('选择本机备份',`<p class="hint">恢复前会先保存当前状态。已删除的来源和记忆不会因恢复旧备份重新出现。</p>${items(data).map(entry=>`<article class="record"><p>${esc(entry.filename)} · ${esc(date(entry.created_at))}</p>${button('恢复此备份','restore-backup',entry.filename)}</article>`).join('')||empty('还没有备份','先创建一次本机备份。')}`,async()=>$('#editor-dialog').close()); },
    'restore-backup':async filename => { if(!confirm('恢复此备份的业务状态与文件？当前状态会先另存为备份。'))return; await api('/api/data/restore',{method:'POST',body:{filename}}); $('#editor-dialog').close();state.records.clear();state.conversation=null;state.messages=[];await navigate('settings');notice('备份已恢复，当前状态另存备份，历史删除记录已重新应用。'); },
    refresh:async () => navigate(state.page),
    'new-conversation':async () => { state.conversation = null; state.messages = []; renderMessages(); const selector = $('#workspace-conversation'); if (selector) selector.value = ''; notice('已开始新对话。'); },
    'retry-chat':async id => { await api(`/api/jobs/${encodeURIComponent(id)}/retry`,{method:'POST',body:{}}); state.chatJob = id; notice('已重新排队，原始消息保持不变。'); pollChat(id); },
    'open-conversation':async () => { state.conversation = $('#workspace-conversation').value || null; state.messages = []; if (state.conversation) await refreshMessages(); else renderMessages(); },
    'select-idea':async id => selectIdea(id),
    'activate-idea':async id => { await api(`/api/ideas/${encodeURIComponent(id)}/activate`,{method:'POST',body:{}}); state.idea = {id}; if (state.page !== 'ideas') location.hash = 'ideas'; else await navigate('ideas'); notice('这个想法已选中。补充验证标准，再安排最小尝试。'); },
    'edit-idea':async id => editRecord(id),
    'idea-status':async id => { await api(`/api/ideas/${encodeURIComponent(id)}`,{method:'PATCH',body:{status:$('#idea-detail-status').value,expected_revision:state.idea.revision}}); await selectIdea(id); notice('当前状态已保存。'); },
    'complete-action':async id => { const action = state.records.get(id); if (action.status === 'done') return; await api(`/api/actions/${encodeURIComponent(id)}`,{method:'PATCH',body:{status:'done',expected_revision:action.revision}}); await selectIdea(state.idea.id); notice('行动已完成。是否验证成功仍以反馈与证据为准。'); },
    'more-ideas':async cursor => { const data = await api(`/api/ideas?limit=50&cursor=${encodeURIComponent(cursor)}`); state.ideas = remember(data); renderIdeaList(); const target = $('[data-action="more-ideas"]'); if (target) { if (data.next_cursor) target.dataset.id = data.next_cursor; else target.remove(); } notice('已显示下一页想法；刷新可回到最新。'); },
    'reading-tab':async tab => { state.readingTab = tab; renderReading(); },
    'finance-tab':async tab => { state.financeTab = tab; renderFinance(); },
    'edit-note':async id => editRecord(id),
    'delete-note':async id => { if (!confirm('删除这条原始记录？关联记忆将停止使用，历史引用也会标记来源已删除。')) return; await api(`/api/notes/${encodeURIComponent(id)}`,{method:'DELETE'}); await navigate('reading'); notice('记录已删除。'); },
    'discover-skills':async () => { const data = await api('/api/books/skills'); const target = $('#skill-list'); target.innerHTML = items(data).map(skill => `<article class="record"><h3>${esc(skill.title || skill.name || '读书 skill')}</h3><p class="record-body">${esc(skill.description || '')}</p>${button('导入这本书','import-skill',skill.path || skill.skill_path)}</article>`).join('') || empty('暂未发现可用读书 skill','检查本机允许的 skill 目录后再试。'); },
    'import-skill':async path => { const data = await api('/api/books',{method:'POST',body:{skill_path:path}}); if (data.job_id) { notice('书源已提交导入，请稍后刷新书库。'); } else { await navigate('reading'); notice('书籍资料已导入。'); } },
    'book-detail':async id => { const book = await api(`/api/books/${encodeURIComponent(id)}`); const target = $('#book-detail'); target.innerHTML = `<section class="panel"><h2>${esc(book.title)}</h2><div class="record-body full">${esc(book.content || '')}</div><dl class="definition-list"><dt>稳定标识</dt><dd class="code-hint">${esc(book.id)}</dd><dt>来源</dt><dd>${esc((book.payload || {}).source_path || book.source_path || '手动保存')}</dd></dl></section>`; },
    'refresh-quotes':async () => { const data = await api('/api/finance/quotes/refresh',{method:'POST',body:{}}); await navigate('finance'); notice(`价格更新完成：已更新 ${Array.isArray(data.updated) ? data.updated.length : data.updated || 0} 项，失败 ${Array.isArray(data.failed) ? data.failed.length : data.failed || 0} 项。未支持项目保持手工估值。`); },
    'save-snapshot':async () => { await api('/api/finance/snapshots',{method:'POST',body:{}}); await navigate('finance'); notice('当前财富快照已保存，未覆盖资料也一并标明。'); },
    'commit-import':async id => { await api(`/api/finance/imports/${encodeURIComponent(id)}/commit`,{method:'POST',body:{}}); state.importPreview.committed = true; renderImportPreview(); notice('这批记录已提交账本。'); },
    'revert-import':async id => { if (!confirm('撤销这批导入的有效记录？后续独立录入的真实变动会保留并重新计算。')) return; await api(`/api/finance/imports/${encodeURIComponent(id)}/revert`,{method:'POST',body:{}}); state.importPreview = null; await navigate('finance'); notice('导入批次已撤销，保留可追溯记录。'); },
    'edit-memory':async id => editRecord(id,true),
    'toggle-memory':async id => { const memory = state.records.get(id); await api(`/api/memories/${encodeURIComponent(id)}`,{method:'PATCH',body:{content:memory.content || memory.assertion,status:memory.status === 'inactive' ? 'active' : 'inactive',expected_revision:memory.revision}}); await navigate('memories'); notice('记忆使用状态已保存。'); },
    'delete-memory':async id => { if (!confirm('删除这条记忆？原始记录保留，同一来源不会再次自动提炼出已删除的记忆。')) return; await api(`/api/memories/${encodeURIComponent(id)}`,{method:'DELETE'}); await navigate('memories'); notice('记忆已删除。'); },
    'more-memories':async cursor => { const data = await api(`/api/memories?limit=50&cursor=${encodeURIComponent(cursor)}`); state.memories = remember(data); const target = $('[data-action="more-memories"]'); const list = $('.record-list',content); list.innerHTML = items(data).map(memory => recordCard(memory,button('纠正内容','edit-memory',memory.id)+button('删除记忆','delete-memory',memory.id,'small danger'))).join(''); if (target) { if (data.next_cursor) target.dataset.id = data.next_cursor; else target.remove(); } notice('已显示下一页记忆；刷新可回到最新。'); },
    'latest-history':async () => { state.historyCursor = null; state.historyCurrentCursor = null; state.historyBack = []; await loadHistory(state.viewToken); },
    'previous-history':async () => { state.historyCurrentCursor = state.historyBack.pop() || null; await loadHistory(state.viewToken); },
    'more-history':async () => { try { await loadHistory(state.viewToken,true); } catch (error) { if (error.status === 409) { state.historyCursor = null; state.historyCurrentCursor = null; state.historyBack = []; await loadHistory(state.viewToken); notice('历史记录发生变化，已重新从最新记录开始。'); } else throw error; } },
    'record-detail':async id => { const record = state.records.get(id); openEditor(record.title || '记录详情',`${recordMeta(record)}<div class="record-body full">${esc(record.content || '')}</div><dl class="definition-list"><dt>稳定标识</dt><dd class="code-hint">${esc(id)}</dd><dt>发生时间</dt><dd>${esc(date(record.occurred_at))}</dd><dt>首次录入</dt><dd>${esc(date(record.recorded_at))}</dd><dt>最后修改</dt><dd>${esc(date(record.updated_at))}</dd></dl>`,async () => $('#editor-dialog').close()); },
    'read-review':async id => { const review = state.records.get(id); await api(`/api/reviews/${encodeURIComponent(id)}/read`,{method:'POST',body:{}}); openEditor(review.title || '复盘报告',`<p class="hint">${esc(date(review.recorded_at))} · Agent 生成</p><div class="record-body full">${esc(review.content || '')}</div>${(review.citations || (review.payload || {}).citations || []).length ? `<div class="citations">使用的资料${(review.citations || review.payload.citations).map(citationHtml).join('')}</div>` : ''}`,async () => $('#editor-dialog').close()); updateNotifications(); },
    'request-review':async () => { openEditor('主动回看一次',`${field('content','你希望回看的问题或变化','',{prefix:'review',type:'textarea',required:true})}${field('source_ids','相关记录标识（可选，用逗号分隔）','',{prefix:'review'})}`,async data => { if (data.source_ids) data.source_ids = data.source_ids.split(',').map(value => value.trim()).filter(Boolean); await api('/api/reviews/request',{method:'POST',body:data}); $('#editor-dialog').close(); notice('复盘请求已保存，完成后会出现在报告列表。'); }); },
    reindex:async () => { const data = await api('/api/data/reindex',{method:'POST',body:{}}); notice('开始整理资料索引。原始记录会保留。'); if (data.job_id) await pollDataJob(data.job_id,'资料索引整理'); else { await navigate('settings'); notice('资料索引已整理。'); } },
    backup:async () => { const data = await api('/api/data/backup',{method:'POST',body:{}}); if (data.job_id) { notice('正在创建本机备份。'); await pollDataJob(data.job_id,'本机备份'); } else { await navigate('settings'); notice(`本机备份已创建${data.path ? `：${data.path}` : '。'}`); } }
  };
  const forms = {
    chat:async (data, target) => {
      if (state.chatJob) throw new Error('上一条回答还在处理中。可以先浏览或记录其他内容。');
      if (state.conversation) data.conversation_id = state.conversation;
      const result = await api('/api/chat/messages',{method:'POST',body:data}); state.conversation = result.conversation_id; state.chatJob = result.job_id;
      target.reset(); await refreshMessages(); notice('原始消息已保存，正在整理回答。'); if (state.chatJob) pollChat(state.chatJob);
    },
    idea:async data => { await api('/api/ideas',{method:'POST',body:data}); await navigate('ideas'); notice('想法已保存到待选。'); },
    'quick-idea':async data => { await api('/api/ideas',{method:'POST',body:data}); await navigate('workspace'); notice('想法已保存，之后可以选择是否推进。'); },
    action:async (data,target) => { await api(`/api/ideas/${encodeURIComponent(target.dataset.id)}/actions`,{method:'POST',body:data}); await selectIdea(target.dataset.id); notice('行动已保存。'); },
    'idea-event':async (data,target) => { await api(`/api/ideas/${encodeURIComponent(target.dataset.id)}/events`,{method:'POST',body:data}); await selectIdea(target.dataset.id); notice('这次进展与证据已保存。'); updateNotifications(); },
    note:async data => { await api('/api/notes',{method:'POST',body:data}); await navigate('reading'); notice('原始记录已保存。'); updateNotifications(); },
    book:async data => { await api('/api/books',{method:'POST',body:data}); await navigate('reading'); notice('书籍资料已保存。'); },
    'book-file':async data => { const result = await api('/api/books',{method:'POST',body:data}); await navigate('reading'); notice(result.job_id ? '书源已提交读取，完成后请刷新书库。' : '书源已导入。'); },
    search:async data => { const result = await api('/api/search',{method:'POST',body:data}); const found = remember(result); $('#search-results').innerHTML = found.map(entry => `<article class="record"><div class="record-meta"><span>${esc(entry.source_title || entry.title || '相关资料')}</span>${entry.recorded_at ? `<time>${esc(date(entry.recorded_at))}</time>` : ''}</div><h3>${esc(entry.title || entry.source_title || '相关内容')}</h3><div class="record-body">${esc(entry.excerpt || entry.snippet || entry.text || entry.content || '')}</div>${entry.location ? `<p class="hint">出处：${esc(entry.location)}</p>` : ''}</article>`).join('') || empty('暂未找到相关资料','换一个关键词，或先补充对应的书源与原始记录。'); },
    'finance-account':async data => { await api('/api/finance/accounts',{method:'POST',body:data}); await navigate('finance'); notice('账户已保存。'); },
    'finance-asset':async data => { await api('/api/finance/assets',{method:'POST',body:data}); await navigate('finance'); notice('资产记录已保存。'); },
    'finance-event':async data => { await api('/api/finance/events',{method:'POST',body:data}); await navigate('finance'); notice('这次变动已正式写入账本。'); updateNotifications(); },
    'finance-import':async data => { data.source = 'manual-csv'; state.importPreview = await api('/api/finance/imports/preview',{method:'POST',body:data}); renderImportPreview(); notice('预览已生成，请核对后再提交。'); },
    'history-filter':async data => { state.historyFilters = data; state.historyCursor = null; state.historyCurrentCursor = null; state.historyBack = []; await loadHistory(state.viewToken); },
    settings:async data => { ['review_daily_budget','review_cooldown_hours','review_merge_minutes','quote_refresh_minutes'].forEach(key => { data[key] = Number(data[key]); }); await api('/api/settings',{method:'PATCH',body:{settings:data}}); await navigate('settings'); notice('设置已保存。'); }
  };
  document.addEventListener('click',event => { const target = event.target.closest('button[data-action]'); if (!target || !actions[target.dataset.action]) return; attempt(target,() => actions[target.dataset.action](target.dataset.id,target)); });
  content.addEventListener('submit',event => { const target = event.target.closest('form[data-form]'); if (!target) return; event.preventDefault(); if (!target.reportValidity()) return; const handler = forms[target.dataset.form]; if (handler) attempt(target,() => handler(values(target),target)); });
  content.addEventListener('change',event => {
    const target = event.target;
    if (target.id === 'ideas-idea-filter') renderIdeaList();
    if (target.id === 'asset-kind') $('#asset-specific-fields').innerHTML = assetSpecificFields(target.value);
    if (target.id === 'finance-event-type') $('#finance-event-fields').innerHTML = financeEventFields(target.value);
    if (target.id === 'csv-file' && target.files[0]) {
      const file = target.files[0];
      if (file.size > 5 * 1024 * 1024) { notice('CSV 文件超过 5 MB，请分成较小批次。',true); target.value = ''; return; }
      file.text().then(text => { $('#csv-csv_text').value = text; notice('文件内容已读取，点击预览后核对。'); }).catch(() => notice('未能读取这个文件，请重新选择或直接粘贴内容。',true));
    }
  });
  $('#auth-form').addEventListener('submit',event => {
    event.preventDefault(); const target = event.currentTarget;
    if (!target.reportValidity()) return;
    attempt(target,async () => {
      const password = $('#auth-password').value;
      if (!state.initialized && password !== $('#auth-confirm').value) throw new Error('两次密码不一致，请重新核对。');
      const auth = await api(state.initialized ? '/api/auth/login' : '/api/auth/setup',{method:'POST',body:{password}});
      $('#auth-password').value = ''; $('#auth-confirm').value = '';
      await openApp(auth);
    });
  });
  $('#toggle-password').addEventListener('click',() => { const input = $('#auth-password');const show = input.type === 'password';input.type = show ? 'text' : 'password';$('#toggle-password').setAttribute('aria-pressed',String(show));$('#toggle-password').setAttribute('aria-label',show ? '隐藏密码' : '显示密码'); });
  $('#nav-toggle').addEventListener('click',() => { const expanded = document.body.classList.toggle('nav-open');$('#nav-toggle').setAttribute('aria-expanded',String(expanded));$('#nav-toggle').setAttribute('aria-label',expanded ? '收起导航' : '展开导航'); });
  document.addEventListener('keydown',event => { if(event.key === 'Escape' && document.body.classList.contains('nav-open')){document.body.classList.remove('nav-open');$('#nav-toggle').setAttribute('aria-expanded','false');$('#nav-toggle').setAttribute('aria-label','展开导航');$('#nav-toggle').focus();} });
  $('#logout-button').addEventListener('click',event => attempt(event.currentTarget,async () => { await api('/api/auth/logout',{method:'POST',body:{}}); state.csrf = ''; state.conversation = null; state.messages = []; state.chatJob = null; state.records.clear(); content.innerHTML = ''; showAuth(true); }));
  $('#editor-form').addEventListener('submit',event => { event.preventDefault(); if (!event.currentTarget.reportValidity() || !state.dialogSubmit) return; const target = event.currentTarget; attempt(target,() => state.dialogSubmit(values(target))); });
  $$('[data-close-dialog]').forEach(target => target.addEventListener('click',() => $('#editor-dialog').close()));
  window.addEventListener('hashchange',() => { if (!$('#app-shell').hidden) navigate(location.hash.slice(1) || 'workspace'); });
  async function initialize() {
    try { const auth = await api('/api/auth/status'); if (auth.authenticated) await openApp(auth); else showAuth(!!auth.initialized); }
    catch (error) { $('#initial-loading').innerHTML = `${empty('暂时无法打开空间',error.message)}<button id="retry-initialize" type="button">重新连接</button>`; $('#retry-initialize').addEventListener('click',initialize); }
  }
  initialize();
})();
