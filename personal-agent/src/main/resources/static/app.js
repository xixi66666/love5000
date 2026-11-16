/* 资料以 Vault 为准；页面只保存当前选择和未提交的编辑，不持久化私人正文。 */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const escape = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {profile:'个人档案',finance:'财务',health:'健康',work:'工作',life:'生活',goals:'目标与复盘',analysis:'AI 报告'};
  const statusNames = {current:'当前记录',historical:'历史记录',archived:'已归档',corrected:'已更正',draft:'待核对'};
  const jobNames = {queued:'排队中',running:'正在分析',completed:'分析已完成',waiting_configuration:'等待模型配置',failed:'分析失败',interrupted:'分析已中断'};
  let csrf = '', initialized = false, vault, domain = '', query = '', offset = 0, epoch = 0, editing = false;
  let selected = [], previewQuestion = '', previewDomain = '', polling;
  const theme = localStorage.getItem('knowledge-theme');
  if (theme === 'dark') document.documentElement.dataset.theme = theme;

  async function api(path, method = 'GET', data) {
    const response = await fetch(path, {method, credentials:'same-origin', headers:{'Content-Type':'application/json', ...(csrf ? {'X-CSRF-Token':csrf} : {})}, body:data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json().catch(() => ({message:'响应格式无效，请刷新后重试'}));
    if (response.status === 401) { csrf = ''; showAuth(); }
    if (!response.ok || result.success !== true) throw new Error(result.message || '操作未完成，请重试');
    return result.data;
  }
  function notice(message, error = false) { const el=$('#notice');el.textContent=message;el.hidden=!message;el.classList.toggle('error',error); }
  function busy(button, task) {
    if (button?.disabled) return;
    if(button)button.disabled=true;
    return Promise.resolve().then(task).catch(e=>notice(e.message,true)).finally(()=>{if(button)button.disabled=false;});
  }
  function showAuth() {
    clearInterval(polling);epoch++;selected=[];vault=null;$('#view').replaceChildren();$('#app').hidden=true;$('#auth').hidden=false;
    $('#auth-title').textContent=initialized?'打开个人空间':'设置资料库密码';
    $('#auth-hint').textContent=initialized?'仅本机可访问；输入密码以打开你的长期资料库。':'为新的资料库设置8–128位空间密码。旧服务的私人数据保留在原目录。';
    $('#password').autocomplete=initialized?'current-password':'new-password';
  }
  async function enter() {
    $('#auth').hidden=true;$('#app').hidden=false;await refresh();await route();
    clearInterval(polling);polling=setInterval(tick,2500);
  }
  function domainButtons() {
    const counts=vault?.domains || {};
    $('#domains').innerHTML=[['','全部资料'],...Object.entries(names)].map(([d,n])=>`<button class="domain ${domain===d?'active':''}" data-domain="${d}">${n}<span>${d?counts[d]||0:vault?.notes||0}</span></button>`).join('');
  }
  async function refresh() {
    vault=await api('/api/vault');
    $('#vault-name').textContent=vault.name;$('#vault-path').textContent=vault.path;$('#open-vault').href=vault.obsidian_url;
    domainButtons();await quartzState();
  }
  async function quartzState() {
    const s=await api('/api/quartz');$('#library').hidden=!s.ready;$('#build').disabled=s.status==='building';
    $('#build-state').textContent=s.status==='building'?'正在生成，请稍候…':s.status==='failed'?s.message:s.ready?'已与当前 Vault 同步':'资料浏览页尚未生成，或资料已经变化。';
  }
  async function tick() {
    if (!csrf || document.hidden) return;
    try {await quartzState();if(location.hash==='#analysis' && $('#history'))await history();} catch(e) { if(csrf)notice(e.message,true); }
  }
  async function route() {
    if(!csrf)return;
    const token=++epoch;editing=false;const tab=location.hash.slice(1)||'notes';
    document.querySelectorAll('[data-tab]').forEach(a=>a.classList.toggle('active',a.dataset.tab===tab));
    $('#breadcrumb').textContent=({notes:'资料目录',analysis:'AI 分析',settings:'仓库与设置'})[tab]||'资料目录';notice('');
    if(tab==='analysis')analysisView();else if(tab==='settings')await settingsView(token);else await notesView(token);
  }
  async function notesView(token=++epoch) {
    const data=await api(`/api/notes?domain=${encodeURIComponent(domain)}&q=${encodeURIComponent(query)}&offset=${offset}`);
    if(token!==epoch)return;
    $('#view').innerHTML=`<h1>${escape(names[domain]||'你的长期资料')}</h1><p class="lead">记录事实、保留背景，让每一次变化都有迹可循。</p>
      <form id="search" class="toolbar"><input id="query" aria-label="搜索资料" placeholder="搜索标题或正文…" value="${escape(query)}"><button type="submit">搜索</button></form>
      <div class="result-count">${data.total} 条资料 · 文件来自当前 Obsidian Vault</div>
      ${data.items.length?data.items.map(n=>`<button class="note-row" data-note="${escape(n.path)}"><div class="row-title">${escape(n.title)}</div><div class="row-meta"><span class="pill">${escape(names[n.domain]||n.domain)}</span><span>${escape(statusNames[n.properties.status]||'未标注状态')}</span><span>事实时间 ${escape(n.properties.observed_at||'未注明')}</span></div><div class="row-preview">${escape(n.preview)}</div></button>`).join(''):`<div class="empty"><h2>${query?'没有匹配的资料':'从一条真实记录开始'}</h2><p>${query?'尝试其他关键词或切换资料领域。':'你可以记录一次资产快照、一份体检结果或一段工作反馈。初始化会添加目录、说明和模板，不会填入虚构的个人信息。'}</p>${!query?'<button id="initialize">初始化目录与模板</button>':''}</div>`}
      <div class="pagination"><button id="previous" ${offset===0?'disabled':''}>上一页</button><span class="hint">${data.total?offset+1:0}–${Math.min(offset+40,data.total)} / ${data.total}</span><button id="next" ${offset+40>=data.total?'disabled':''}>下一页</button></div>`;
    $('#search').onsubmit=e=>{e.preventDefault();query=$('#query').value.trim();offset=0;notesView().catch(e=>notice(e.message,true));};
    $('#previous').onclick=()=>{offset=Math.max(0,offset-40);notesView().catch(e=>notice(e.message,true));};
    $('#next').onclick=()=>{offset+=40;notesView().catch(e=>notice(e.message,true));};
    if($('#initialize'))$('#initialize').onclick=e=>busy(e.currentTarget,async()=>{await api('/api/vault/initialize','POST',{});await refresh();await notesView();notice('目录与模板已就绪，可以在 Obsidian 中打开此仓库。');});
  }
  async function openNote(path) {
    const token=++epoch;editing=false;const n=await api('/api/note?path='+encodeURIComponent(path));if(token!==epoch)return;
    $('#view').innerHTML=`<button class="quiet back" id="back">← 返回资料目录</button><h1>${escape(n.title)}</h1><div class="source-meta">${escape(n.path)}</div>
      <div class="actions"><a class="button primary" href="${escape(n.obsidian_url)}">在 Obsidian 中打开 ↗</a><button id="edit">编辑原文</button><a class="button" href="/library/" target="_blank" rel="noopener">在 Quartz 中阅读</a></div>
      <table class="meta-table"><tbody>${Object.entries(n.properties).map(([k,v])=>`<tr><th>${escape(k)}</th><td>${escape(typeof v==='object'?JSON.stringify(v):v)}</td></tr>`).join('')}</tbody></table>
      <h2>Markdown 原文预览</h2><p class="hint">完整排版、嵌入与关系图请打开 Quartz 浏览页。</p><pre class="raw-note">${escape(n.body)}</pre>
      <h2 class="section-heading">反向链接</h2>${n.backlinks.length?n.backlinks.map(p=>`<button class="quiet" data-note="${escape(p)}">${escape(p)}</button>`).join(''):'<p class="muted">暂无其他笔记链接到这里。</p>'}`;
    $('#back').onclick=()=>notesView().catch(e=>notice(e.message,true));$('#edit').onclick=()=>editor(n);
  }
  function editor(note) {
    epoch++;editing=true;const creating=!note;const d=domain&&domain!=='analysis'?domain:'life';
    $('#view').innerHTML=`<h1>${creating?'记录一条资料':'编辑 Markdown 原文'}</h1><p class="lead">${creating?'把时间、来源和事实放在一起。记录会直接保存为 Vault 中的 Markdown。':'保存前会核对版本；原文件变化时，请先合并修改。'}</p>
      <form id="note-form">${creating?`<div class="form-grid"><div class="full"><label for="note-title">标题</label><input id="note-title" required maxlength="150" placeholder="例如：本月财务快照 / 年度体检 / 项目复盘"></div><div><label for="note-domain">资料领域</label><select id="note-domain">${Object.entries(names).filter(([k])=>k!=='analysis').map(([k,v])=>`<option value="${k}" ${k===d?'selected':''}>${v}</option>`).join('')}</select></div><div><label for="note-date">事实发生 / 截至日期</label><input id="note-date" type="date"></div><div><label for="note-source">资料来源</label><input id="note-source" value="本人记录" maxlength="200"></div><div><label for="note-status">资料状态</label><select id="note-status"><option value="current">当前记录</option><option value="historical">历史记录</option><option value="draft">待核对</option></select></div></div>`:`<p class="path">${escape(note.path)}</p>`}
      <label for="note-content">${creating?'正文（支持 Markdown 与 [[双链]]）':'完整文件，包含顶部 YAML 属性'}</label><textarea id="note-content" class="editor" required>${creating?'':escape(note.content)}</textarea>
      ${creating?'<p class="hint">财务金额注明币种与截至时间，健康指标保留单位和参考范围。尚不确定的资料保持待核对。</p><div class="check"><input type="checkbox" id="ai-exclude"><label for="ai-exclude">这条资料不提供给 AI 分析</label></div>':''}
      <div class="actions"><button type="submit" class="primary">保存到 Vault</button><button type="button" id="cancel-edit">取消</button></div><p id="save-error" class="error" role="alert"></p></form>`;
    $('#cancel-edit').onclick=()=>{editing=false;note?openNote(note.path).catch(e=>notice(e.message,true)):route().catch(e=>notice(e.message,true));};
    $('#note-form').onsubmit=e=>{e.preventDefault();const button=e.submitter;busy(button,async()=>{
      let content=$('#note-content').value,ndomain=note?.domain||$('#note-domain').value;
      if(creating){const title=$('#note-title').value.trim();content=`---\ntitle: ${JSON.stringify(title)}\ndomain: ${ndomain}\nrecord_type: observation\nobserved_at: ${JSON.stringify($('#note-date').value)}\nrecorded_at: ${JSON.stringify(new Date().toISOString())}\nstatus: ${$('#note-status').value}\nsource: ${JSON.stringify($('#note-source').value)}\nai_exclude: ${$('#ai-exclude').checked}\n---\n\n${content}\n`;}
      const saved=await api('/api/notes','POST',{path:note?.path||'',domain:ndomain,content,expected_revision:note?.revision||''});editing=false;await refresh();await openNote(saved.path);notice('已保存到真实 Vault；Quartz 浏览页需要更新。');
    });};
  }
  function analysisView() {
    selected=[];previewQuestion='';
    $('#view').innerHTML=`<h1>让建议有据可循</h1><p class="lead">选择一个问题，检查相关资料，再交给当前模型。每份分析会保存为带来源的 Markdown 草稿。</p>
      <div data-model-picker data-model-scope="personal-agent" data-model-theme="stock"></div>
      <form id="analysis-form"><div class="form-grid"><div class="full"><label for="question">你想了解什么？</label><textarea id="question" maxlength="3000" required placeholder="例如：结合近期的工作反馈和生活记录，我接下来应该优先调整什么？"></textarea></div><div class="full"><label for="analysis-domain">资料范围</label><select id="analysis-domain"><option value="">跨领域综合分析</option>${Object.entries(names).filter(([k])=>k!=='analysis').map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div></div><button type="submit">检索并预览来源</button></form>
      <section id="sources"></section><h2 class="section-heading">分析记录</h2><div id="history">正在读取…</div>`;
    $('#analysis-form').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{
      previewQuestion=$('#question').value.trim();previewDomain=$('#analysis-domain').value;
      const result=await api('/api/analyses/preview','POST',{question:previewQuestion,domain:previewDomain});selected=result.sources;
      $('#sources').innerHTML=`<h2 class="section-heading">确认将使用的资料</h2><p class="hint">${escape(result.method)}。仅以下选中条目的属性和正文片段会发送给当前模型。</p>${selected.length?selected.map((s,i)=>`<div class="source"><div class="source-title"><input type="checkbox" checked data-source="${i}" id="source-${i}"><label for="source-${i}"><strong>${escape(s.title)}</strong><span class="source-meta">${escape(s.path)} · 事实时间 ${escape(s.properties.observed_at||'未注明')} ${s.truncated?'· 正文仅取前2800字':''}</span></label></div><details><summary>将发送的属性</summary><pre>${escape(JSON.stringify(s.properties,null,2))}</pre></details><pre>${escape(s.excerpt)}</pre></div>`).join(''):'<p>没有可用于分析的资料。请先记录事实，并检查领域、状态和 ai_exclude 属性。</p>'}
      ${selected.length?'<div class="check actions"><input id="consent" type="checkbox"><label for="consent">我已检查所选来源，同意将这些片段发送给当前模型进行本次分析。</label></div><button id="analyze" class="primary">生成分析草稿</button>':''}`;
      if($('#analyze'))$('#analyze').onclick=e=>busy(e.currentTarget,async()=>{
        if($('#question').value.trim()!==previewQuestion||$('#analysis-domain').value!==previewDomain)throw new Error('问题或范围已变化，请重新检索来源。');
        if(!$('#consent').checked)throw new Error('请先检查来源并勾选发送确认。');
        const sources=[...document.querySelectorAll('[data-source]:checked')].map(c=>selected[Number(c.dataset.source)]).map(s=>({path:s.path,revision:s.revision}));
        await api('/api/analyses','POST',{question:previewQuestion,domain:previewDomain,sources,consent:true});$('#consent').checked=false;notice('分析已加入队列。完成后报告会保存到 Vault 的 80-AI分析。');await history();
      });
    });};
    history().catch(e=>notice(e.message,true));
  }
  async function history() {
    const values=await api('/api/analyses');if(!$('#history'))return;
    $('#history').innerHTML=values.length?values.map(j=>`<div class="report-row"><h3>${escape(j.question)}</h3><p><span class="pill">${escape(jobNames[j.status]||j.status)}</span> <span class="muted">${escape(j.created_at?.replace('T',' ').slice(0,19))}</span></p>${j.message?`<p class="error">${escape(j.message)}</p>`:''}${j.report_path?`<button class="quiet" data-note="${escape(j.report_path)}">查看分析草稿 →</button>`:''}</div>`).join(''):'<p class="muted">还没有分析记录。你的资料不会被后台自动发送。</p>';
  }
  async function settingsView(token) {
    const s=await api('/api/settings');if(token!==epoch)return;
    $('#view').innerHTML=`<h1>仓库与设置</h1><p class="lead">资料是本地文件。Obsidian 负责组织与编辑，网页和 AI 使用同一个 Vault。</p>
      <section class="settings-section"><h2>连接 Obsidian Vault</h2><p class="hint">先在 Obsidian 中打开目标文件夹。切换仅改变读取位置，不复制、合并或删除资料。</p><form id="connect"><label for="vault-input">仓库完整路径</label><input id="vault-input" required value="${escape(s.vault_dir)}"><div class="actions"><button type="submit">连接此仓库</button></div></form><p class="path">服务状态与笔记备份：${escape(s.data_dir)}</p></section>
      <section class="settings-section"><h2>文本模型</h2><div data-model-picker data-model-scope="personal-agent" data-model-theme="stock"></div><p class="hint">跟随主页或独立选择模型。服务原配置：${escape(s.model)}；地址：${escape(s.api_base)}。密钥通过环境变量配置，不在网页保存。</p></section>
      <section class="settings-section"><h2>长期记录的属性</h2><p>建议保留 domain、observed_at、recorded_at、status、source。以历史记录保存过去的快照；用 ai_exclude: true 将单篇资料排除在分析之外。</p><p class="hint">AI 生成的报告默认 status: draft、origin: ai_generated，不会再次作为个人事实被自动检索。</p></section><section class="settings-section"><h2>空间</h2><button id="settings-theme">切换深浅主题</button> <button id="settings-logout">锁定空间</button></section>`;
    $('#connect').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{await api('/api/vault/connect','POST',{path:$('#vault-input').value});selected=[];await refresh();notice('已连接此 Vault，请重新生成 Quartz 浏览页。');});};
    $('#settings-theme').onclick=toggleTheme;$('#settings-logout').onclick=logout;
  }
  function toggleTheme(){const value=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=value;localStorage.setItem('knowledge-theme',value);}
  async function logout(){try{await api('/api/auth/logout','POST',{});}finally{csrf='';showAuth();}}
  $('#auth-form').onsubmit=async e=>{e.preventDefault();$('#auth-error').textContent='';const b=$('#auth-submit');b.disabled=true;try{const s=await api(initialized?'/api/auth/login':'/api/auth/setup','POST',{password:$('#password').value});initialized=s.initialized;csrf=s.csrf_token;$('#password').value='';await enter();}catch(e){$('#auth-error').textContent=e.message;}finally{b.disabled=false;}};
  $('#new-note').onclick=()=>editor();$('#theme').onclick=toggleTheme;$('#logout').onclick=()=>logout().catch(e=>notice(e.message,true));
  $('#refresh').onclick=e=>busy(e.currentTarget,async()=>{if(editing)throw new Error('请先保存或取消当前编辑，再刷新资料。');await refresh();await route();});
  $('#build').onclick=e=>busy(e.currentTarget,async()=>{await api('/api/quartz/build','POST',{});notice('Quartz 正在生成。完成后右侧会出现浏览入口。');});
  document.addEventListener('click',e=>{const d=e.target.closest('[data-domain]'),n=e.target.closest('[data-note]');if(d){if(editing&&!confirm('放弃未保存的编辑并切换领域？'))return;domain=d.dataset.domain;offset=0;query='';domainButtons();if(location.hash==='#notes')route().catch(e=>notice(e.message,true));else location.hash='notes';}if(n)openNote(n.dataset.note).catch(e=>notice(e.message,true));});
  window.addEventListener('hashchange',()=>{if(editing&&!confirm('放弃未保存的编辑并切换页面？')){window.history.replaceState(null,'','#notes');return;}route().catch(e=>notice(e.message,true));});
  window.addEventListener('beforeunload',e=>{if(editing){e.preventDefault();e.returnValue='';}});
  api('/api/auth/status').then(s=>{initialized=s.initialized;csrf=s.csrf_token||'';return s.authenticated?enter():showAuth();}).catch(e=>{$('#auth').hidden=false;$('#auth-error').textContent=e.message;});
})();
