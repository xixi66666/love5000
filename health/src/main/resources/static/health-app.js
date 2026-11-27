'use strict';

const view = document.querySelector('#view');
const labels = {abnormal:'异常',normal:'正常',unknown:'待核对'};
const icons = {overview:'档案总览',reports:'体检报告',import:'导入报告',settings:'档案设置'};
const metricRegions = [
  ['头面与五官',/眼底|视力|眼压|听力|口腔|牙周|鼻窦/i],['甲状腺',/甲状腺|\b(?:TSH|FT3|FT4|TPOAb)\b/i],
  ['肺与呼吸',/肺|支气管|呼吸|\b(?:FEV1|FVC)\b/i],['心血管',/心电|心脏|心率|血压|冠状动脉|心肌|颈动脉|\bECG\b/i],
  ['肝胆',/肝|胆囊|胆管|胆红素|转氨酶|\b(?:ALT|AST|GGT)\b/i],['胃肠',/胃|肠|幽门螺杆菌|粪便|大便/i],
  ['肾与泌尿',/肾|肌酐|膀胱|尿蛋白|尿潜血|尿比重|尿常规|尿素氮|\beGFR\b/i],['骨骼与关节',/骨密度|骨骼|骨质|关节|腰椎|脊柱/i],
  ['代谢与血液',/血糖|糖化|葡萄糖|甘油三酯|胆固醇|脂蛋白|尿酸|血红蛋白|血小板|血细胞|白细胞|\b(?:HbA1c|LDL|HDL|WBC|RBC|Hemoglobin)\b/i]
];
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const dateText = value => /^\d{4}-\d\d-\d\d$/.test(value || '') ? value.replaceAll('-','.') : String(value || '日期待核对');
const statusOf = item => Object.hasOwn(labels,item.status) ? item.status : 'unknown';
const reportHref = (key,page) => '#report/' + encodeURIComponent(key) + (page ? '?page='+encodeURIComponent(page) : '');
const pageNumber = location => /^第 (\d+) 页$/.exec(location || '')?.[1];
let csrf = '', reports = [], workspace = '', generation = 0, importBusy = false;

async function api(path, method='GET', body) {
  const headers = csrf && method !== 'GET' ? {'X-CSRF-Token':csrf} : {};
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  const response = await fetch(path,{method,body,headers,cache:'no-store'});
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.success) {
    const error = new Error(payload?.message || '请求失败，请重试。');
    error.status = response.status;
    throw error;
  }
  return payload.data;
}

async function refreshReports() {
  const data = await api('/api/exams');
  reports = data.reports;
  workspace = data.workspace;
}

function navigate(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

function heading(title, description, actions='') {
  return `<header class="page-head"><div><h1>${title}</h1><p>${description}</p></div>${actions}</header>`;
}

function reportList(items, selected='', groupYears=false) {
  let lastYear = null;
  return items.map(item => {
    const year = /^\d{4}/.exec(item.date || '')?.[0] || '日期待核对';
    const group = groupYears && lastYear !== year ? `<div class="report-year">${year}${year.length === 4 ? ' 年' : ''}</div>` : '';
    lastYear = year;
    return `${group}<a class="report-link" href="${reportHref(item.id)}"${item.id === selected ? ' aria-current="page"' : ''}>
      <span><time datetime="${escape(item.date)}">${escape(dateText(item.date))}</time><small>${item.ready ? '已有解析' : '已归档 · 待解析'}</small></span><span aria-hidden="true">↗</span></a>`;
  }).join('') || '<p class="empty">暂无已归档的体检报告。</p>';
}

function statusSwitches(items, active) {
  return Object.entries(labels).map(([status,label]) => `<button type="button" data-status="${status}" aria-pressed="${active === status}"><span>${label}</span><b>${items.filter(item=>statusOf(item) === status).length}</b></button>`).join('');
}

function range(point) {
  if (point.range) return `${escape(point.range)}${point.range_recovered ? ' <small>从原件恢复</small>' : ''}`;
  const ref = point.external_reference;
  if (ref && /^https:\/\//i.test(ref.source_url || '')) return `${escape(ref.display_range || ref.statement)} <a href="${escape(ref.source_url)}" target="_blank" rel="noopener noreferrer" title="${escape(ref.applies_to)}">外部参考 ↗</a>`;
  return '未收录';
}

function chart(item) {
  const points = item.points.map(point => {
    const source = item.converted ? point.comparison_number : point.number;
    return {point,value:source == null ? NaN : Number(source),date:Date.parse(point.date)};
  });
  if (points.length < 2 || points.some(point => !Number.isFinite(point.value) || !Number.isFinite(point.date))) return '';
  const bounds = points.reduce((all,next)=>({low:Math.min(all.low,next.value),high:Math.max(all.high,next.value),
    first:Math.min(all.first,next.date),last:Math.max(all.last,next.date)}),{low:Infinity,high:-Infinity,first:Infinity,last:-Infinity});
  if (bounds.first === bounds.last) return '';
  const plot = points.map(point => ({...point,x:18+(point.date-bounds.first)*564/(bounds.last-bounds.first),
    y:bounds.high === bounds.low ? 48 : 80-(point.value-bounds.low)*64/(bounds.high-bounds.low)}));
  return `<svg class="chart" viewBox="0 0 600 96" preserveAspectRatio="none" role="img" aria-label="${escape(item.label)}历年结果，共 ${plot.length} 个点"><path class="chart-line" pathLength="1" d="${plot.map(({x,y},i)=>`${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')}"/>${plot.map(({x,y,point})=>`<circle class="${statusOf(point)}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3"><title>${escape(dateText(point.date))} ${escape(point.value)} ${escape(point.unit)}</title></circle>`).join('')}</svg>`;
}

function track(item) {
  const last = item.points.at(-1);
  if (!last) return '';
  return `<details class="record ${statusOf(item)}"><summary><span class="record-title"><strong>${escape(item.label)}</strong><small>${item.points.length === 1 ? escape(dateText(last.date)) : `${item.points.length} 次检查 · ${escape(dateText(last.date))}`} ${item.loinc ? `· LOINC ${escape(item.loinc)}` : ''}</small></span><span class="record-value">${escape(last.value)} <small>${escape(last.unit)}</small></span></summary>
    <div class="record-body">${chart(item)}${item.change != null ? `<p class="muted">${item.converted ? '换算后首末差' : '首末差'} ${Number(item.change)>0?'+':''}${escape(item.change)} ${escape(item.unit === '%' ? '个百分点' : item.unit)}</p>` : ''}
    <ol class="chronology">${item.points.map(point=>`<li><a href="${reportHref(point.exam_id,point.page_verified ? pageNumber(point.location) : null)}">${escape(dateText(point.date))}<small>${escape(point.location || '查看报告')}</small></a><span>${escape(point.value)} ${escape(point.unit)}<small>${labels[statusOf(point)]}${point.flag ? ` · ${escape(point.flag)}` : ''}</small></span><span>参考<small>${range(point)}</small></span></li>`).join('')}</ol></div></details>`;
}

const regionOf = name => metricRegions.find(([,matches])=>matches.test(name || ''))?.[0] || '其他与待归类';

function mountResults(container, items, emptyMessage, render, search, region) {
  const switches = container.querySelector('.switches');
  const content = container.querySelector('.track-list');
  let active = Object.keys(labels).find(status=>items.some(item=>statusOf(item) === status)) || 'abnormal';
  const refresh = () => {
    const query = search?.value.trim().toLowerCase() || '';
    const shown = items.filter(item=>(!region?.value || regionOf(item.name) === region.value) &&
      (!query || [item.name,item.label,item.unit,item.loinc,item.standardization?.loinc].some(value=>String(value || '').toLowerCase().includes(query))));
    switches.innerHTML = statusSwitches(shown,active);
    const filtered = shown.filter(item=>statusOf(item) === active);
    content.innerHTML = filtered.length ? filtered.map(render).join('') : `<p class="empty">${query ? '当前分组没有匹配的指标。' : emptyMessage}</p>`;
    content.classList.remove('track-list');
    requestAnimationFrame(()=>content.classList.add('track-list'));
  };
  switches.onclick = event => {
    const button = event.target.closest('[data-status]');
    if (!button) return;
    active = button.dataset.status;
    refresh();
    switches.querySelector(`[data-status="${active}"]`)?.focus();
  };
  search?.addEventListener('input',refresh);
  region?.addEventListener('change',refresh);
  refresh();
}

async function overview(ticket) {
  const latest = reports[0];
  view.innerHTML = `<section class="cover" aria-labelledby="cover-title"><div class="cover-art" aria-hidden="true"></div><div class="cover-copy"><span class="cover-kicker">Obsidian 本机档案</span><h1 id="cover-title">体检健康档案</h1><p>按次归档体检报告，沿时间回看指标变化与原件。</p><div class="actions"><a class="button primary" href="#import">导入报告 <span aria-hidden="true">＋</span></a><a class="button" href="#reports">全部报告 <span aria-hidden="true">↗</span></a></div></div>
    ${latest ? `<div class="cover-aside"><small>最近一次检查</small><time datetime="${escape(latest.date)}">${escape(dateText(latest.date))}</time><a href="${reportHref(latest.id)}">打开报告 ↗</a></div>` : ''}</section>
    <div class="workspace-grid"><section class="surface" id="trends"><div class="section-top"><div><h2>历年指标</h2><p id="evidence-count">正在读取历年检查…</p></div></div><div class="switches" aria-label="指标状态"></div><div class="track-list" aria-live="polite"></div></section>
    <section class="surface"><header class="section-top"><div><h2>体检报告</h2><p>共 ${reports.length} 份</p></div>${reports.length ? '<a class="link" href="#reports">查看全部 ↗</a>' : ''}</header><div class="report-list">${reportList(reports.slice(0,5))}</div></section></div>`;
  const cover = view.querySelector('.cover');
  if (matchMedia('(pointer:fine) and (prefers-reduced-motion:no-preference)').matches) {
    cover.onpointermove = event => {
      const area = cover.getBoundingClientRect();
      cover.style.setProperty('--art-x',`${(event.clientX-area.left-area.width/2)/70}px`);
      cover.style.setProperty('--art-y',`${(event.clientY-area.top-area.height/2)/45}px`);
    };
    cover.onpointerleave = () => { cover.style.removeProperty('--art-x'); cover.style.removeProperty('--art-y'); };
  }
  const timeline = await api('/api/exams/timeline');
  if (ticket !== generation) return;
  const items = [...timeline.metrics,...timeline.individual_metrics.map(point=>({...point,points:[point]}))];
  items.sort((a,b)=>String(b.points.at(-1)?.date).localeCompare(String(a.points.at(-1)?.date)) || a.label.localeCompare(b.label,'zh-CN'));
  view.querySelector('#evidence-count').textContent = `${timeline.verified_report_count} 份报告有已核对摘录`;
  mountResults(view.querySelector('#trends'),items,'该分组暂无已核对指标。',track);
  if (timeline.topics.length) {
    const section = document.createElement('section');
    section.className = 'surface';
    section.style.marginTop = '20px';
    section.innerHTML = `<header class="section-top"><h2>历年检查发现</h2></header>${timeline.topics.map(topic=>`<details class="record"><summary><span class="record-title"><strong>${escape(topic.label)}</strong><small>${topic.points.length} 条原文</small></span><span></span></summary><div class="record-body">${topic.points.map(point=>`<div class="evidence"><a href="${reportHref(point.exam_id,point.page_verified ? pageNumber(point.location) : null)}">${escape(dateText(point.date))} ↗</a><blockquote>${escape(point.quote)}</blockquote></div>`).join('')}</div></details>`).join('')}`;
    view.appendChild(section);
  }
}

function metricCard(row,pageVerified) {
  const page = pageVerified ? pageNumber(row.location) : null;
  return `<details class="record ${statusOf(row)}"><summary><span class="record-title"><strong>${escape(row.name)}</strong><small>${row.standardization?.loinc ? `LOINC ${escape(row.standardization.loinc)}` : escape(row.location || '原件摘录')}</small></span><span class="record-value">${escape(row.value)} <small>${escape(row.unit)}</small></span></summary>
    <div class="record-body"><dl><dt>参考范围</dt><dd>${range(row)}</dd><dt>报告标记</dt><dd>${escape(row.flag || '未收录')}</dd><dt>原件摘录</dt><dd>${escape(row.quote)}</dd></dl>${page ? `<button class="button quiet" type="button" data-page="${page}">查看原件第 ${page} 页 ↗</button>` : ''}</div></details>`;
}

function obsidian(path) {
  const name = workspace.split(/[\\/]/).filter(Boolean).at(-1) || '';
  return 'obsidian://open?vault='+encodeURIComponent(name)+'&file='+encodeURIComponent(path);
}

function evidenceList(rows,title,verified) {
  if (!rows?.length) return '';
  return `<section class="surface"><header class="section-top"><h2>${title}</h2></header>${rows.map(row=>{
    const page = verified ? pageNumber(row.location) : null;
    return `<div class="evidence">${row.category ? `<small class="muted">${escape(({imaging:'影像所见',lab:'化验',exam:'体格与专科检查'})[row.category]||'其他检查')}</small>` : ''}<blockquote>${escape(row.quote)}</blockquote>${row.interpretation ? `<p>${escape(row.interpretation)}</p>` : ''}${row.uncertainty ? `<p class="muted">${escape(row.uncertainty)}</p>` : ''}${page ? `<button class="button quiet" type="button" data-page="${page}">${escape(row.location)} ↗</button>` : `<small class="muted">${escape(row.location)}</small>`}</div>`;
  }).join('')}</section>`;
}

function metricKey(metric) {
  const code = metric.standardization;
  if (code) return code.loinc && code.comparison_unit ? JSON.stringify([code.loinc,code.comparison_unit]) : '';
  return metric.unit ? JSON.stringify([metric.name,metric.unit]) : '';
}

function openComparison(host,current,metrics,ticket) {
  const previous = reports.filter(item=>item.ready && item.date < current.date);
  if (!previous.length || !metrics.length) return;
  host.innerHTML = `<header class="section-top"><div><h2>两次报告对照</h2><p>并列可匹配的原值与参考范围。</p></div></header><form><label for="previous-report">选择较早报告</label><div class="actions"><select id="previous-report">${previous.map(item=>`<option value="${escape(item.id)}">${escape(dateText(item.date))}</option>`).join('')}</select><button class="button" type="submit">查看对照</button></div></form><div role="status" class="comparison-result"></div>`;
  host.hidden = false;
  host.querySelector('form').onsubmit = async event => {
    event.preventDefault();
    const result = host.querySelector('.comparison-result');
    const select = host.querySelector('select');
    const button = host.querySelector('button');
    select.disabled = button.disabled = true;
    result.textContent = '正在读取较早报告…';
    try {
      const old = await api('/api/exams/'+encodeURIComponent(select.value));
      if (ticket !== generation) return;
      const oldRows = old.findings?.metrics || [];
      const pairs = metrics.flatMap(metric=>{
        const key = metricKey(metric);
        if (!key || metrics.filter(row=>metricKey(row)===key).length !== 1) return [];
        const matches = oldRows.filter(row=>metricKey(row)===key);
        return matches.length === 1 ? [[metric,matches[0]]] : [];
      });
      const cell = row => `<span>${escape(row.value)} ${escape(row.unit)}<small>参考 ${range(row)}</small></span>`;
      result.innerHTML = pairs.length ? `<ol class="chronology"><li><strong>指标</strong><b>${escape(dateText(old.date))}</b><b>${escape(dateText(current.date))}</b></li>${pairs.map(([now,past])=>`<li><strong>${escape(now.name)}</strong>${cell(past)}${cell(now)}</li>`).join('')}</ol>` : '<p class="empty">两份报告中暂无可对照的指标。</p>';
    } catch (error) { if (ticket === generation) result.textContent = error.message; }
    finally { select.disabled = button.disabled = false; }
  };
}

function activatePreview(host, endpoint, report, ticket) {
  const details = host.querySelector('.preview');
  const message = host.querySelector('.preview-status');
  const parse = host.querySelector('.parse-actions');
  const output = details.querySelector('.page-text');
  let pending;
  let result;
  let busy = false;
  const legacyModes = data => data.mode === 'pdf_text'
    ? `<div><p>发送带页行号的本机提取文字给当前文本模型。</p><button class="button" data-mode="pdf_text">发送文字并生成 AI 解读</button></div><div><p>表格错位或图表需要单独识别时，可以授权上传整份文件。</p><button class="button quiet" data-mode="original">同意发送完整 PDF</button></div>`
    : '<div><p>原件将按所选模型支持的方式发送。完整 PDF 使用 DeepSeek 原件识别。</p><button class="button" data-mode="original">同意发送原件并解读</button></div>';
  async function inspect() {
    if (result) return result;
    if (pending) return pending;
    pending = api(endpoint+'/preview').then(data=>{
      result = data;
      if (ticket !== generation) return data;
      message.textContent = data.message;
      if (data.pages.length) {
        output.innerHTML = `<label for="preview-page">原件页码</label><select id="preview-page">${data.pages.map(page=>`<option value="${page.page}">第 ${page.page} 页</option>`).join('')}</select><pre tabindex="0"></pre>`;
        const select = output.querySelector('select');
        const update = () => { output.querySelector('pre').textContent = data.pages.find(page=>String(page.page) === select.value)?.text || '此页没有文字层。'; };
        select.onchange = update;
        update();
      } else output.textContent = '请下载原件查看此文件。';
      if (data.mode !== 'unavailable' && report.analysis_version < (report.latest_analysis_version || 4)) {
        parse.innerHTML = `${data.local_document && report.analysis_version < 5 ? '<div><p>在本机提取表格和原文证据。</p><button class="button primary" data-mode="mirobody_local">本机解析表格</button></div>' : ''}
          ${data.page_ocr && report.analysis_version < 6 ? '<div><p>将扫描件的分页图片或上传的照片发送给已配置的视觉模型。</p><button class="button" data-mode="mirobody_ocr">同意发送图片并识别</button></div>' : ''}${legacyModes(data)}`;
      }
      return data;
    }).catch(error=>{
      if (ticket === generation) message.textContent = error.message;
      return null;
    }).finally(()=>{pending=null;});
    return pending;
  }
  details.ontoggle = () => { if (details.open) inspect(); };
  parse.onclick = async event => {
    const button = event.target.closest('[data-mode]');
    if (!button || busy) return;
    const mode = button.dataset.mode;
    busy = true;
    parse.querySelectorAll('button').forEach(item=>{item.disabled=true;});
    message.textContent = mode === 'mirobody_local' ? '正在本机解析表格…' : '正在处理报告，完成后会刷新草稿…';
    try {
      await api(endpoint+'/analysis','POST',{workspace,revision:report.revision,evidence_mode:mode,consent:mode !== 'mirobody_local'});
      if (ticket !== generation) return;
      await refreshReports();
      if (ticket === generation) route();
    } catch (error) {
      if (ticket === generation) message.textContent = error.message;
    } finally {
      busy = false;
      parse.querySelectorAll('button').forEach(item=>{item.disabled=false;});
    }
  };
  message.textContent = '正在读取原件信息…';
  inspect();
  return async page => {
    details.open = true;
    await inspect();
    if (ticket !== generation) return;
    const select = output.querySelector('select');
    if (select && [...select.options].some(option=>option.value === page)) {
      select.value = page;
      select.dispatchEvent(new Event('change'));
      select.focus();
    } else details.querySelector('summary').focus();
  };
}

async function reportView(key,page,ticket) {
  if (!key) key = reports[0]?.id;
  if (!key) {
    view.innerHTML = heading('体检报告','从第一份报告建立你的体检档案。','<a class="button primary" href="#import">导入报告 ＋</a>');
    return;
  }
  const endpoint = '/api/exams/'+encodeURIComponent(key);
  const report = await api(endpoint);
  if (ticket !== generation) return;
  const findings = report.findings;
  const rows = findings?.metrics || [];
  const method = findings?.documentMethod;
  const draftLabel = method === 'mirobody_local' ? '本机解析草稿' : method === 'mirobody_ocr' ? '视觉转录 · 待核对' : findings ? 'AI 解读草稿' : '原件已归档';
  view.innerHTML = heading('体检报告','从报告日期查看每一次检查的记录和证据。','<a class="button primary" href="#import">导入报告 ＋</a>') + `
    <div class="report-layout"><aside class="surface report-index"><header class="section-top"><h2>报告索引</h2></header><nav class="report-list" aria-label="按年查看报告">${reportList(reports,key,true)}</nav></aside>
    <div class="report-main"><article class="surface" id="report-info"><header class="section-top"><div><h2>${escape(dateText(report.date))}</h2><p>${draftLabel}</p></div><a class="button" href="${endpoint}/original" download>下载原件 ↗</a></header>${findings?.summary ? `<p>${escape(findings.summary)}</p>` : ''}
      <div class="actions">${[ ['来源笔记',report.source_path], ['当前草稿',report.report_path], ['上一版草稿',report.previous_report_path] ].filter(([,path])=>path).map(([title,path])=>`<a class="quiet-link" href="${obsidian(path)}">${title} ↗</a>`).join('')}</div>
      <details class="preview"><summary>查看本机提取的逐页文字</summary><div class="page-text"></div></details><div class="parse-actions"></div><p class="preview-status notice" role="status"></p></article>
    ${rows.length ? `<section class="surface" id="report-metrics"><header class="section-top"><h2>指标与依据</h2><div class="actions"><input class="metric-search" type="search" aria-label="搜索指标或编码" placeholder="搜索指标或编码"><select class="metric-region" aria-label="按身体部位或系统筛选"><option value="">全部部位</option>${[...new Set(rows.map(row=>regionOf(row.name)))].map(area=>`<option>${area}</option>`).join('')}</select></div></header><div class="switches" aria-label="指标状态"></div><div class="track-list" aria-live="polite"></div></section><section class="surface" id="report-compare" hidden></section>` : ''}
    ${evidenceList(findings?.recommendations,'原报告建议',findings?.pdfPageEvidenceVerified)}${evidenceList(findings?.observations,'重点发现',findings?.pdfPageEvidenceVerified)}
    ${findings?.questions?.length || findings?.limitations?.length || findings?.omittedEvidence ? `<section class="surface"><header class="section-top"><h2>沟通与核对</h2></header><ul>${[...(findings.questions||[]),...(findings.limitations||[])].map(item=>`<li>${escape(item)}</li>`).join('')}</ul>${findings.omittedEvidence ? `<p class="muted">${escape(findings.omittedEvidence)} 条候选记录未收录。</p>` : ''}</section>` : ''}</div></div>`;
  const host = view.querySelector('#report-metrics');
  if (host) {
    mountResults(host,rows,'该分组暂无指标。',row=>metricCard(row,findings.pdfPageEvidenceVerified),host.querySelector('input'),host.querySelector('select'));
    openComparison(view.querySelector('#report-compare'),report,rows,ticket);
  }
  const openPage = activatePreview(view.querySelector('#report-info'),endpoint,report,ticket);
  view.onclick = event => {
    const button = event.target.closest('[data-page]');
    if (button) openPage(button.dataset.page);
  };
  if (page) await openPage(page);
}

function guessDate(name) {
  const found = new Set();
  for (const match of name.matchAll(/(?<!\d)(\d{4})[-_.年]?(\d\d)[-_.月]?(\d\d)(?!\d)/g)) {
    const day = `${match[1]}-${match[2]}-${match[3]}`;
    const instant = new Date(`${day}T00:00:00Z`);
    if (!Number.isNaN(+instant) && instant.toISOString().startsWith(day)) found.add(day);
  }
  return found.size === 1 ? [...found][0] : '';
}

function importView() {
  const entries = [];
  view.innerHTML = heading('导入体检报告','选择一份或多份报告，逐份确认检查日期。') + `<form class="surface import-form"><label for="files">选择体检文件</label><input id="files" type="file" multiple accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.gif,.txt,.md,.doc,.ppt,.pptx,.xls,.csv"><p class="muted">单份最多 12 MB。归档会把原件保存到本机 Vault。</p><div class="upload-rows"></div><div class="actions"><button type="submit" class="button primary" disabled>归档报告</button><a href="#reports" class="button quiet">返回报告索引</a></div><p class="notice" role="status"></p></form>`;
  const form = view.querySelector('form');
  const picker = form.querySelector('input');
  const uploadRows = form.querySelector('.upload-rows');
  const send = form.querySelector('button');
  const notice = form.querySelector('.notice');
  picker.onchange = () => {
    for (const file of picker.files) {
      if (!entries.some(entry=>entry.file.name === file.name && entry.file.size === file.size && entry.file.lastModified === file.lastModified)) {
        entries.push({file,id:crypto.randomUUID(),date:guessDate(file.name),saved:null});
      }
    }
    picker.value = '';
    render();
  };
  function render() {
    uploadRows.innerHTML = entries.map((entry,index)=>`<div class="upload-row"><div><strong>${escape(entry.file.name)}</strong><small>${entry.saved ? '已归档' : entry.error ? escape(entry.error) : `${(entry.file.size/1048576).toFixed(2)} MB`}</small>${entry.saved ? `<a class="quiet-link" href="${reportHref(entry.saved.id)}">打开报告 ↗</a>` : `<button type="button" class="button quiet" data-remove="${index}"${importBusy ? ' disabled' : ''}>移除</button>`}</div><label for="check-date-${index}">检查日期<input id="check-date-${index}" data-date="${index}" type="date" value="${escape(entry.date)}" ${entry.saved || importBusy ? 'disabled' : 'required'}></label></div>`).join('');
    send.disabled = importBusy || !entries.some(entry=>!entry.saved);
    picker.disabled = importBusy;
  }
  uploadRows.oninput = event => {
    if (event.target.matches('[data-date]')) entries[Number(event.target.dataset.date)].date = event.target.value;
  };
  uploadRows.onclick = event => {
    const button = event.target.closest('[data-remove]');
    if (button && !importBusy) { entries.splice(Number(button.dataset.remove),1); render(); }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (importBusy || !form.reportValidity()) return;
    importBusy = true;
    render();
    try {
      for (const entry of entries.filter(item=>!item.saved)) {
        notice.textContent = `正在归档 ${entry.file.name}…`;
        const data = new FormData();
        for (const [name,value] of Object.entries({file:entry.file,date:entry.date,workspace,mode:'archive',import_id:entry.id})) data.append(name,value);
        try { entry.saved = await api('/api/exams','POST',data); entry.error = ''; }
        catch (error) { entry.error = error.message; }
        render();
      }
      if (entries.some(item=>item.saved)) await refreshReports();
      notice.textContent = entries.some(item=>!item.saved) ? '可重新提交失败的文件。' : `已归档 ${entries.length} 份报告。`;
    } catch (error) { notice.textContent = error.message; }
    finally { importBusy = false; if (location.hash === '#import') render(); else route(); }
  };
}

function settingsView() {
  view.innerHTML = heading('档案设置','健康管理直接读取你连接的 Obsidian Vault。') + `<form class="surface settings-form"><label for="vault-path">Obsidian Vault 完整路径</label><input id="vault-path" name="path" value="${escape(workspace)}" required><div class="actions"><button class="button primary" type="submit">连接仓库</button></div><p class="notice" role="status"></p></form>`;
  const form = view.querySelector('form');
  form.onsubmit = async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    const status = form.querySelector('.notice');
    button.disabled = true;
    try {
      await api('/api/vault/connect','POST',{path:form.elements.path.value.trim()});
      await refreshReports();
      form.elements.path.value = workspace;
      status.textContent = '仓库已连接。';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  };
}

async function route() {
  if (!csrf || importBusy) return;
  const ticket = ++generation;
  const [target,query] = location.hash.slice(1).split('?');
  const reportId = /^report\/([a-f0-9-]{36})$/.exec(target)?.[1];
  const tab = reportId ? 'reports' : Object.hasOwn(icons,target) ? target : 'overview';
  document.querySelector('#breadcrumb').textContent = icons[tab];
  document.querySelectorAll('[data-nav]').forEach(link=>{
    if (link.dataset.nav === tab) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });
  view.onclick = null;
  view.innerHTML = '<p class="surface muted" role="status">正在读取健康档案…</p>';
  try {
    if (tab === 'overview') await overview(ticket);
    if (tab === 'reports') await reportView(reportId,new URLSearchParams(query).get('page'),ticket);
    if (tab === 'import') importView();
    if (tab === 'settings') settingsView();
  } catch (error) {
    if (ticket !== generation) return;
    if (error.status === 401) { await boot(); return; }
    view.innerHTML = `<div class="surface"><p role="alert">${escape(error.message)}</p><div class="actions"><button class="button" id="retry">重试</button><a class="quiet-link" href="#settings">档案设置 ↗</a></div></div>`;
    view.querySelector('#retry').onclick = route;
  }
}

async function boot() {
  const welcome = document.querySelector('#welcome');
  const shell = document.querySelector('#shell');
  const form = document.querySelector('#auth-form');
  const status = document.querySelector('#auth-status');
  const description = document.querySelector('#welcome-description');
  const retry = document.querySelector('#auth-retry');
  retry.hidden = true;
  status.textContent = '';
  try {
    const account = await api('/api/auth/status');
    if (account.authenticated) {
      csrf = account.csrf_token;
      welcome.hidden = true;
      shell.hidden = false;
      try { await refreshReports(); }
      catch (error) { reports = []; if (!location.hash) location.hash = '#settings'; }
      await route();
      return;
    }
    csrf = '';
    generation++;
    view.replaceChildren();
    shell.hidden = true;
    welcome.hidden = false;
    form.hidden = false;
    description.textContent = account.initialized ? '解锁本机档案，回看体检报告与历年指标。' : '为本机健康档案设置 8 到 128 个字符的密码。';
    const input = form.elements.password;
    input.autocomplete = account.initialized ? 'current-password' : 'new-password';
    input.minLength = account.initialized ? 0 : 8;
    input.maxLength = 128;
    const button = form.querySelector('button');
    button.textContent = account.initialized ? '登录 ↗' : '创建档案密码 ↗';
    form.onsubmit = async event => {
      event.preventDefault();
      button.disabled = true;
      try { await api('/api/auth/'+(account.initialized ? 'login' : 'setup'),'POST',{password:input.value}); form.reset(); await boot(); }
      catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    };
  } catch (error) {
    status.textContent = error.message;
    retry.hidden = false;
  }
}

document.querySelector('#auth-retry').onclick = boot;
document.querySelector('#logout').onclick = async () => {
  if (importBusy) return;
  try { await api('/api/auth/logout','POST',{}); }
  catch (error) { if (error.status !== 401) console.warn('健康档案退出请求未完成'); }
  finally { await boot(); }
};
window.addEventListener('hashchange',()=>{if (!importBusy) route();});
boot();
