/* 资料以 Vault 为准；页面只保存当前选择和未提交的编辑，不持久化私人正文。 */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const escape = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const areas = window.personalAreas;
  const names = {...Object.fromEntries(Object.entries(areas).map(([key,[title]])=>[key,title])),analysis:'AI 报告'};
  const statusNames = {current:'当前记录',historical:'历史记录',archived:'已归档',corrected:'已更正',draft:'待核对'};
  const jobNames = {queued:'排队中',running:'正在分析',completed:'分析已完成',waiting_configuration:'等待模型配置',failed:'分析失败',interrupted:'分析已中断'};
  let csrf = '', initialized = false, vault, domain = '', query = '', offset = 0, epoch = 0, editing = false;
  let selected = [], previewQuestion = '', previewDomain = '', polling;
  let suggestedAnalysis = null, importDomain = '', noteReturn = '#notes';
  const theme = localStorage.getItem('knowledge-theme');
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;

  async function api(path, method = 'GET', data) {
    const multipart = data instanceof FormData;
    const response = await fetch(path, {method, credentials:'same-origin', headers:{...(!multipart ? {'Content-Type':'application/json'} : {}), ...(csrf ? {'X-CSRF-Token':csrf} : {})}, body:data === undefined || multipart ? data : JSON.stringify(data)});
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
    clearInterval(polling);epoch++;selected=[];suggestedAnalysis=null;vault=null;$('#view').replaceChildren();$('#app').hidden=true;$('#auth').hidden=false;
    $('#auth-title').textContent=initialized?'打开个人空间':'设置资料库密码';
    $('#auth-hint').textContent=initialized?'仅本机可访问；输入密码以打开你的长期资料库。':'为新的资料库设置8–128位空间密码。旧服务的私人数据保留在原目录。';
    $('#password').autocomplete=initialized?'current-password':'new-password';
  }
  async function enter(afterLogin = false) {
    if (afterLogin || !location.hash) {
      window.history.replaceState(null, '', '#overview');
      domain = '';
      query = '';
      offset = 0;
      importDomain = '';
      noteReturn = '#notes';
    }
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
    const token=++epoch;editing=false;
    const routeValue = location.hash.slice(1);
    const noteQuery = routeValue.startsWith('note=') ? new URLSearchParams(routeValue) : null;
    const tab = noteQuery ? 'notes' : routeValue || 'overview';
    $('#app').dataset.view = noteQuery ? 'note' : tab;
    $('#vault-context').hidden = tab !== 'overview';
    document.querySelectorAll('[data-tab]').forEach(link=>{
      const active=link.dataset.tab===tab;
      link.classList.toggle('active',active);
      if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    });
    $('#breadcrumb').textContent=({overview:'资料总览',notes:'资料目录',import:'导入资料',health:'健康档案',analysis:'AI 分析',settings:'仓库与设置'})[tab]||'资料目录';notice('');
    if(noteQuery)await openNote(noteQuery.get('note'), noteQuery.get('heading'));
    else if(tab==='overview'){
      $('#view').innerHTML='<p role="status">正在读取笔记和双链…</p>';
      const data = await api('/api/vault/overview');
      if(token!==epoch)return;
      window.renderPersonalOverview($('#view'),vault,data,escape,value=>{
        domain='';query=value;offset=0;domainButtons();location.hash='notes';
      });
    }
    else if(tab==='import') {
      const initialDomain = importDomain; importDomain = '';
      window.showDocumentImport({view:$('#view'),api,escape,areas,domain:initialDomain,workspace:vault.path,alive:()=>token===epoch,
        dirty:value=>{if(token===epoch)editing=value;},onSaved:async(saved,savedDomain)=>{
          domain=savedDomain; query=''; offset=0;
          await refresh();
          if(token!==epoch)return;
          noteReturn='#notes';
          window.history.replaceState(null,'',window.noteHash(saved.path));
          await route();notice('原件和 Markdown 已保存到 Vault。');
        }});
    }
    else if(tab==='health')await window.showHealthArchive({view:$('#view'),api,escape,refresh,alive:()=>token===epoch,dirty:value=>{if(token===epoch)editing=value;}});
    else if(tab==='analysis')analysisView();else if(tab==='settings')await settingsView(token);else await notesView(token);
  }
  async function notesView(token=++epoch) {
    const scope = domain;
    const data=await api(`/api/notes?domain=${encodeURIComponent(scope)}&q=${encodeURIComponent(query)}&offset=${offset}`);
    if(token!==epoch)return;
    $('#view').innerHTML=`<div class="area-intro"><div><h1>${escape(names[domain]||'你的长期资料')}</h1><p>${escape(areas[domain]?.[1]||'检索你保存在 Vault 的笔记与导入资料。')}</p></div><button type="button" data-import-domain="${escape(domain === 'analysis' ? '' : domain)}" class="primary">＋ 导入资料</button></div>
      ${areas[domain] ? `<div class="actions"><button type="button" data-ask-area="${escape(domain)}">分析这个领域 →</button></div>` : ''}
      ${scope && !query && !offset ? '<div id="domain-insights" role="region" aria-label="资料图谱" aria-busy="true"></div>' : ''}
      ${(!domain||domain==='health')&&!query?'<a class="health-entry" href="#health"><span><strong>健康档案</strong><small>导入体检报告，按检查日期回看指标与原文。</small></span><b aria-hidden="true">↗</b></a>':''}
      <form id="search" class="toolbar"><input id="query" aria-label="搜索资料" placeholder="搜索标题或正文…" value="${escape(query)}"><button type="submit">搜索</button></form>
      <div class="result-count">${data.total} 条资料 · 文件来自当前 Obsidian Vault</div>
      ${data.items.length?data.items.map(n=>`<button class="note-row" data-note="${escape(n.path)}"><div class="row-title">${escape(n.title)}</div><div class="row-meta"><span class="pill">${escape(names[n.domain]||n.domain)}</span><span>${escape(statusNames[n.properties.status]||'未标注状态')}</span><span>事实时间 ${escape(n.properties.observed_at||'未注明')}</span></div><div class="row-preview">${escape(n.preview)}</div></button>`).join(''):`<div class="empty"><h2>${query?'没有匹配的资料':'从一条真实记录开始'}</h2><p>${query?'尝试其他关键词或切换资料领域。':'你可以记录一次资产快照、一份体检结果或一段工作反馈。初始化会添加目录、说明和模板，不会填入虚构的个人信息。'}</p>${!query?'<button id="initialize">初始化目录与模板</button>':''}</div>`}
      <div class="pagination"><button id="previous" ${offset===0?'disabled':''}>上一页</button><span class="hint">${data.total?offset+1:0}–${Math.min(offset+40,data.total)} / ${data.total}</span><button id="next" ${offset+40>=data.total?'disabled':''}>下一页</button></div>`;
    $('#search').onsubmit=e=>{e.preventDefault();query=$('#query').value.trim();offset=0;notesView().catch(e=>notice(e.message,true));};
    const insights = $('#domain-insights');
    if (insights) {
      api('/api/vault/overview?domain='+encodeURIComponent(scope)).then(overview=>{
        if(token===epoch)window.renderDomainInsights(insights,overview,scope,escape);
      }).catch(error=>{
        if(token===epoch)insights.textContent=error.message;
      }).finally(()=>insights.removeAttribute('aria-busy'));
    }
    $('#previous').onclick=()=>{offset=Math.max(0,offset-40);notesView().catch(e=>notice(e.message,true));};
    $('#next').onclick=()=>{offset+=40;notesView().catch(e=>notice(e.message,true));};
    if($('#initialize'))$('#initialize').onclick=e=>busy(e.currentTarget,async()=>{await api('/api/vault/initialize','POST',{});await refresh();await notesView();notice('目录与模板已就绪，可以在 Obsidian 中打开此仓库。');});
  }
  async function openNote(path, heading) {
    const token=++epoch;editing=false;
    $('#view').innerHTML='<p role="status">正在打开笔记…</p>';
    const n=await api('/api/note?path='+encodeURIComponent(path));if(token!==epoch)return;
    $('#breadcrumb').textContent='笔记阅读';
    const related = (items, empty) => items?.length ? `<ul>${items.map(item=>`<li><a href="${window.noteHash(item.path)}">${escape(item.title)}</a></li>`).join('')} </ul>` : `<p class="hint">${empty}</p>`;
    const links = `<section><h2>反向链接 <small>${n.incoming?.length || 0}</small></h2>${related(n.incoming,'还没有笔记引用此文。')}</section>
      <section><h2>链接到 <small>${n.outgoing?.length || 0}</small></h2>${related(n.outgoing,'此文没有可打开的笔记链接。')}</section>`;
    $('#view').innerHTML=`<article class="reading-page">
      <a class="quiet reading-back" href="${noteReturn}">← 返回上一视图</a>
      <div class="reading-location">${escape(n.path.split('/').slice(0,-1).join(' / ') || 'Vault')}</div>
      <h1>${escape(n.title)}</h1>
      <p class="reading-meta">${escape(names[n.domain]||n.domain)} ${n.modified_at?' · 编辑于 '+escape(n.modified_at.slice(0,10)):''} ${n.properties.status?' · '+escape(statusNames[n.properties.status]||n.properties.status):''}</p>
      <div class="actions reading-actions"><a class="button primary" href="${escape(n.obsidian_url)}">在 Obsidian 中打开 ↗</a><button id="edit">编辑原文</button>${n.properties.record_type==='imported_document'?`<a class="button" href="/api/documents/original?path=${encodeURIComponent(n.path)}" download>下载原件</a>`:''}</div>
      ${Object.keys(n.properties).length ? `<details class="reading-properties"><summary>笔记属性</summary><table class="meta-table"><tbody>${Object.entries(n.properties).map(([key,value])=>`<tr><th>${escape(key)}</th><td>${escape(typeof value==='object'?JSON.stringify(value):value)}</td></tr>`).join('')}</tbody></table></details>` : ''}
      <div class="reading-switch" role="group" aria-label="阅读模式"><button class="quiet" type="button" data-reading-mode="preview" aria-pressed="true">阅读</button><button class="quiet" type="button" data-reading-mode="raw" aria-pressed="false">Markdown</button></div>
      <details class="reading-details"><summary>本文目录</summary><ul class="reading-outline"></ul></details>
      <div id="reading-preview" class="reading-markdown"></div><pre id="reading-raw" class="raw-note" hidden>${escape(n.content)}</pre>
      ${n.reading_truncated ? '<p class="hint">此页展示前 120,000 字符，可切换 Markdown 查看全文。</p>' : ''}
      <details class="reading-details"><summary>相关笔记 · ${(n.incoming?.length || 0)+(n.outgoing?.length || 0)}</summary>${links}</details>
    </article>`;
    $('#reading-preview').innerHTML=n.reading_html || '<p>这篇笔记暂无正文。</p>';
    window.scrollTo(0,0);
    window.renderNoteReading(heading);
    $('.reading-switch').onclick=event=>{
      const button=event.target.closest('[data-reading-mode]');
      if(!button)return;
      const raw=button.dataset.readingMode==='raw';
      $('#reading-preview').hidden=raw;$('#reading-raw').hidden=!raw;
      $('.reading-switch').querySelectorAll('button').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
    };
    $('#edit').onclick=()=>editor(n);
    if (n.properties.record_type === 'imported_document' && n.ai_eligible) {
      const analyze = document.createElement('button');
      analyze.type = 'button'; analyze.textContent = '分析这份资料';
      analyze.onclick = () => {
        suggestedAnalysis = {domain:n.domain,path:n.path,question:'请整理这份资料中的主要事实、原文明确记载的日期和待核对事项，逐项注明来源。'};
        if(location.hash==='#analysis')route().catch(error=>notice(error.message,true));else location.hash='analysis';
      };
      $('#view .actions').append(analyze);
    }
  }
  function editor(note) {
    epoch++;editing=true;const creating=!note;const d=domain&&domain!=='analysis'?domain:'life';
    $('#app').dataset.view='editor';
    $('#vault-context').hidden=true;
    $('#view').innerHTML=`<h1>${creating?'记录一条资料':'编辑 Markdown 原文'}</h1><p class="lead">${creating?'把时间、来源和事实放在一起。记录会直接保存为 Vault 中的 Markdown。':'保存前会核对版本；原文件变化时，请先合并修改。'}</p>
      <form id="note-form">${creating?`<div class="form-grid"><div class="full"><label for="note-title">标题</label><input id="note-title" required maxlength="150" placeholder="例如：本月财务快照 / 年度体检 / 项目复盘"></div><div><label for="note-domain">资料领域</label><select id="note-domain">${Object.entries(names).filter(([k])=>k!=='analysis').map(([k,v])=>`<option value="${k}" ${k===d?'selected':''}>${v}</option>`).join('')}</select></div><div><label for="note-date">事实发生 / 截至日期</label><input id="note-date" type="date"></div><div><label for="note-source">资料来源</label><input id="note-source" value="本人记录" maxlength="200"></div><div><label for="note-status">资料状态</label><select id="note-status"><option value="current">当前记录</option><option value="historical">历史记录</option><option value="draft">待核对</option></select></div></div>`:`<p class="path">${escape(note.path)}</p>`}
      <label for="note-content">${creating?'正文（支持 Markdown 与 [[双链]]）':'完整文件，包含顶部 YAML 属性'}</label><textarea id="note-content" class="editor" required>${creating?'':escape(note.content)}</textarea>
      ${creating?'<p class="hint">财务金额注明币种与截至时间，健康指标保留单位和参考范围。尚不确定的资料保持待核对。</p><div class="check"><input type="checkbox" id="ai-exclude"><label for="ai-exclude">这条资料不提供给 AI 分析</label></div>':''}
      <div class="actions"><button type="submit" class="primary">保存到 Vault</button><button type="button" id="cancel-edit">取消</button></div><p id="save-error" class="error" role="alert"></p></form>`;
    $('#cancel-edit').onclick=()=>{editing=false;route().catch(e=>notice(e.message,true));};
    $('#note-form').onsubmit=e=>{e.preventDefault();const button=e.submitter;busy(button,async()=>{
      let content=$('#note-content').value,ndomain=note?.domain||$('#note-domain').value;
      if(creating){const title=$('#note-title').value.trim();content=`---\ntitle: ${JSON.stringify(title)}\ndomain: ${ndomain}\nrecord_type: observation\nobserved_at: ${JSON.stringify($('#note-date').value)}\nrecorded_at: ${JSON.stringify(new Date().toISOString())}\nstatus: ${$('#note-status').value}\nsource: ${JSON.stringify($('#note-source').value)}\nai_exclude: ${$('#ai-exclude').checked}\n---\n\n${content}\n`;}
      const saved=await api('/api/notes','POST',{path:note?.path||'',domain:ndomain,content,expected_revision:note?.revision||''});editing=false;await refresh();
      if(creating)noteReturn=location.hash||'#overview';
      window.history.replaceState(null,'',window.noteHash(saved.path));await route();notice('已保存到 Vault。');
    });};
  }
  function analysisView() {
    selected=[];previewQuestion='';
    const suggestion = suggestedAnalysis; suggestedAnalysis = null;
    const analysisEpoch = epoch;
    $('#view').innerHTML=`<h1>让建议有据可循</h1><p class="lead">选择一个问题，检查相关资料，再交给当前模型。每份分析会保存为带来源的 Markdown 草稿。</p>
      <div class="model-row"><span class="model-label">分析模型</span><div data-model-picker data-model-scope="personal-agent" data-model-theme="knowledge"></div></div>
      <form id="analysis-form"><div class="form-grid"><div class="full"><label for="question">你想了解什么？</label><textarea id="question" maxlength="3000" required placeholder="例如：结合近期的工作反馈和生活记录，我接下来应该优先调整什么？"></textarea></div><div class="full"><label for="analysis-domain">资料范围</label><select id="analysis-domain"><option value="">跨领域综合分析</option>${Object.entries(names).filter(([k])=>k!=='analysis').map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div></div><button type="submit">检索并预览来源</button></form>
      <section id="sources"></section><h2 class="section-heading">分析记录</h2><div id="history">正在读取…</div>`;
    if(suggestion){$('#question').value=suggestion.question;$('#analysis-domain').value=suggestion.domain;}
    let sourcePath = suggestion?.path || '';
    if (sourcePath) {
      const scope = document.createElement('p'); scope.className = 'hint'; scope.textContent = '本次只检索刚选中的资料。切换资料范围可重新检索其他笔记。';
      $('#analysis-domain').after(scope);
      $('#analysis-domain').onchange=()=>{sourcePath='';scope.remove();};
    }
    $('#analysis-form').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{
      previewQuestion=$('#question').value.trim();previewDomain=$('#analysis-domain').value;
      const result=await api('/api/analyses/preview','POST',{question:previewQuestion,domain:previewDomain,source_path:sourcePath});if(epoch!==analysisEpoch)return;selected=result.sources;
      $('#sources').innerHTML=`<h2 class="section-heading">确认将使用的资料</h2><p class="hint">${escape(result.method)}。仅以下选中条目的属性和正文片段会发送给当前模型。</p>${selected.length?selected.map((s,i)=>`<div class="source"><div class="source-title"><input type="checkbox" checked data-source="${i}" id="source-${i}"><label for="source-${i}"><strong>${escape(s.title)}</strong><span class="source-meta">${escape(s.path)} · 事实时间 ${escape(s.properties.observed_at||'未注明')} ${s.truncated?'· 正文仅取前2800字':''}</span></label></div><details><summary>将发送的属性</summary><pre>${escape(JSON.stringify(s.properties,null,2))}</pre></details><pre>${escape(s.excerpt)}</pre></div>`).join(''):'<p>没有可用于分析的资料。请先记录事实，并检查领域、状态和 ai_exclude 属性。</p>'}
      ${selected.length?'<div class="check actions"><input id="consent" type="checkbox"><label for="consent">我已检查所选来源，同意将这些片段发送给当前模型进行本次分析。</label></div><button id="analyze" class="primary">生成分析草稿</button>':''}`;
      if($('#analyze'))$('#analyze').onclick=e=>busy(e.currentTarget,async()=>{
        if($('#question').value.trim()!==previewQuestion||$('#analysis-domain').value!==previewDomain)throw new Error('问题或范围已变化，请重新检索来源。');
        if(!$('#consent').checked)throw new Error('请先检查来源并勾选发送确认。');
        const sources=[...document.querySelectorAll('[data-source]:checked')].map(c=>selected[Number(c.dataset.source)]).map(s=>({path:s.path,revision:s.revision}));
        await api('/api/analyses','POST',{question:previewQuestion,domain:previewDomain,sources,consent:true});if(epoch!==analysisEpoch)return;$('#consent').checked=false;notice('分析已加入队列。完成后报告会保存到 Vault 的 80-AI分析。');await history();
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
      <section class="settings-section"><h2>文本模型</h2><div data-model-picker data-model-scope="personal-agent" data-model-theme="knowledge"></div><p class="hint">跟随主页或独立选择模型。服务原配置：${escape(s.model)}；地址：${escape(s.api_base)}。密钥只在本机 model.properties 中配置，不在网页保存。</p></section>
      <section class="settings-section"><h2>长期记录的属性</h2><p>建议保留 domain、observed_at、recorded_at、status、source。以历史记录保存过去的快照；用 ai_exclude: true 将单篇资料排除在分析之外。</p><p class="hint">AI 生成的报告默认 status: draft、origin: ai_generated，不会再次作为个人事实被自动检索。</p></section><section class="settings-section"><h2>空间</h2><button id="settings-theme">切换深浅主题</button> <button id="settings-logout">锁定空间</button></section>`;
    $('#connect').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{await api('/api/vault/connect','POST',{path:$('#vault-input').value});selected=[];await refresh();notice('已连接此 Vault，请重新生成 Quartz 浏览页。');});};
    $('#settings-theme').onclick=toggleTheme;$('#settings-logout').onclick=logout;
  }
  function toggleTheme(){const value=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=value;localStorage.setItem('knowledge-theme',value);}
  async function logout(){try{await api('/api/auth/logout','POST',{});}finally{csrf='';showAuth();}}
  $('#auth-form').onsubmit=async e=>{e.preventDefault();$('#auth-error').textContent='';const b=$('#auth-submit');b.disabled=true;try{const s=await api(initialized?'/api/auth/login':'/api/auth/setup','POST',{password:$('#password').value});initialized=s.initialized;csrf=s.csrf_token;$('#password').value='';await enter(true);}catch(e){$('#auth-error').textContent=e.message;}finally{b.disabled=false;}};
  $('#new-note').onclick=()=>{if(!editing||confirm('放弃未保存的内容并记录新资料？'))editor();};$('#theme').onclick=toggleTheme;$('#logout').onclick=()=>logout().catch(e=>notice(e.message,true));
  $('#refresh').onclick=e=>busy(e.currentTarget,async()=>{if(editing)throw new Error('请先保存或取消当前编辑，再刷新资料。');await refresh();await route();});
  $('#build').onclick=e=>busy(e.currentTarget,async()=>{await api('/api/quartz/build','POST',{});notice('Quartz 正在生成。完成后右侧会出现浏览入口。');});
  document.addEventListener('click',event=>{
    const area=event.target.closest('[data-domain]'),note=event.target.closest('[data-note]');
    const importer=event.target.closest('[data-import-domain]'),ask=event.target.closest('[data-ask-area]');
    if(!area&&!note&&!importer&&!ask)return;
    if(editing&&!confirm('放弃未保存的内容并离开当前页面？'))return;
    editing=false;
    if(note){
      const href=window.noteHash(note.dataset.note);
      if(location.hash===href)route().catch(error=>notice(error.message,true));else location.hash=href;
      return;
    }
    let tab;
    if(area){domain=area.dataset.domain;offset=0;query='';domainButtons();tab='notes';}
    if(importer){importDomain=importer.dataset.importDomain;tab='import';}
    if(ask){
      const key=ask.dataset.askArea;
      suggestedAnalysis={domain:key,question:areas[key]?.[2]||'综合我近期的工作、生活和目标记录，整理已承诺的事项、时间冲突和下一步优先事项。逐项注明资料来源。'};
      tab='analysis';
    }
    if(location.hash==='#'+tab)route().catch(error=>notice(error.message,true));else location.hash=tab;
  });
  window.addEventListener('hashchange',event=>{
    if(editing&&!confirm('放弃未保存的编辑并切换页面？')){window.history.replaceState(null,'',event.oldURL);return;}
    const prior = new URL(event.oldURL).hash;
    if(location.hash.startsWith('#note=') && !prior.startsWith('#note=')) {
      noteReturn=['#overview','#notes','#health','#analysis'].includes(prior) ? prior : prior ? '#notes' : '#overview';
    }
    route().catch(error=>notice(error.message,true));
  });
  window.addEventListener('beforeunload',e=>{if(editing){e.preventDefault();e.returnValue='';}});
  api('/api/auth/status').then(s=>{initialized=s.initialized;csrf=s.csrf_token||'';return s.authenticated?enter():showAuth();}).catch(e=>{$('#auth').hidden=false;$('#auth-error').textContent=e.message;});
})();
