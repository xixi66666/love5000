'use strict';
window.showHealthArchive = async function ({view, api, escape: esc, alive, refresh, dirty, startImport}) {
  const get = selector => view.querySelector(selector);
  let reports, workspace, generation = 0;
  view.innerHTML = '<p role="status">正在读取本地健康档案…</p>';
  const mast = `<header class="health-workbench"><div><h1>健康档案</h1><p>查阅体检记录、原件依据和历次检查结果。</p></div><button type="button" id="exam-import" class="primary">导入报告</button></header>`;

  function reportOptions() {
    const years = new Map();
    for (const report of reports) {
      const year = /^\d{4}-/.test(report.date) ? report.date.slice(0,4) + ' 年' : '日期未注明';
      if (!years.has(year)) years.set(year, []);
      years.get(year).push(`<option value="${esc(report.id)}">${esc(report.title)} · ${report.ready?'有 AI 草稿':'待分析'}</option>`);
    }
    return [...years].map(([year, options])=>`<optgroup label="${esc(year)}">${options.join('')}</optgroup>`).join('');
  }

  async function load(prefer) {
    const token = ++generation;
    const data = await api('/api/exams');
    if (!alive() || token !== generation) return;
    reports = data.reports; workspace = data.workspace;
    if (startImport) {
      startImport = false;
      importView();
      return;
    }
    view.innerHTML = mast + (reports.length ? `<div class="exam-selector"><label for="exam-select">检查记录 <small>${reports.length} 份</small></label><select id="exam-select">${reportOptions()}</select></div>` :
      '<section class="exam-empty"><h2>还没有体检报告</h2><p>导入第一份报告，即可查看分页面的 PDF 文字和后续解读。</p></section>')
      + '<div id="exam-detail"></div><details class="exam-explorer" id="exam-atlas-section"><summary>按部位浏览指标</summary><div id="exam-atlas"></div></details>'
      + '<details class="exam-explorer" id="health-graph"><summary>查看健康资料图谱</summary><div id="health-insights" role="region" aria-label="健康资料图谱"></div></details>';
    const graph = get('#health-insights');
    const graphToggle = get('#health-graph');
    let graphLoaded = false;
    graphToggle.ontoggle = async () => {
      if (!graphToggle.open || graphLoaded) return;
      graphLoaded = true;
      graph.setAttribute('aria-busy','true');
      graph.textContent = '正在读取健康资料图谱…';
      try {
        const overview = await api('/api/vault/overview?domain=health');
        if (alive() && graph.isConnected) window.renderDomainInsights(graph,overview,'health',esc);
      } catch (error) {
        graphLoaded = false;
        if (alive() && graph.isConnected) graph.textContent = error.message;
      } finally { graph.removeAttribute('aria-busy'); }
    };
    get('#exam-import').onclick = importView;
    if (!reports.length) {
      window.renderBodyAtlas(get('#exam-atlas'), [], '', esc);
      return;
    }
    const select = get('#exam-select');
    if (reports.some(report => report.id === prefer)) select.value = prefer;
    select.onchange = () => showReport(select.value);
    await showReport(select.value);
  }

  function importView() {
    const previous = get('#exam-select')?.value;
    generation++;
    window.showExamImport({view, api, escape:esc, workspace, alive, dirty,
      onExit: id => load(id || previous).then(() => id && alive() ? refresh() : undefined).catch(fail)});
  }

  function locationLabel(entry, verified) {
    const page = verified && /^第 (\d+) 页$/.exec(entry.location);
    return page ? `<button type="button" class="quiet exam-page-link" data-exam-page="${page[1]}" aria-label="查看原件第 ${page[1]} 页文字">${esc(entry.location)}</button>` : esc(entry.location);
  }

  function evidenceList(entries, title, verified) {
    if (!entries?.length) return '';
    return `<section class="exam-reading-section"><h3>${title}</h3><ul class="exam-evidence-list">${entries.map(entry =>
      `<li><blockquote>${esc(entry.quote)}</blockquote><p class="exam-location">${locationLabel(entry,verified)}</p>
      ${entry.interpretation ? `<p><strong>AI 解读</strong> ${esc(entry.interpretation)}</p>` : ''}</li>`).join('')}</ul></section>`;
  }

  function setupPreview(host, endpoint, report, isCurrent, onAnalyzed) {
    const form = host.querySelector('form'), status = host.querySelector('#analysis-progress');
    const panel = host.querySelector('details'), content = panel.querySelector('div');
    const action = form?.querySelector('button');
    const original = form?.querySelector('input[type=checkbox]');
    let preview, pending;
    function updateScope() {
      const sendText = preview.mode === 'pdf_text' && !original.checked;
      host.querySelector('.exam-send-scope').textContent = sendText
        ? '确认后，提取出的报告文字（可能含个人信息）会发送给顶部所选的文本模型。'
        : preview.page_count
          ? '确认后，完整 PDF 会发送给 DeepSeek 进行版面识别。请在顶部选择 DeepSeek Flash 或使用默认原件识别模型。'
          : '确认后，将按所选模型支持的方式发送报告内容。';
      action.textContent = sendText ? '发送提取文字并解读' : '同意发送原件并解读';
    }
    function read() {
      if (!preview && !pending) pending = readPreview().finally(() => { pending = null; });
      return pending;
    }
    async function readPreview() {
      status.textContent = '正在本机读取报告…';
      try {
        preview = await api(endpoint+'/preview');
        if (!isCurrent()) return;
        status.textContent = '';
        host.querySelector('.exam-preview-summary').textContent = preview.page_count
          ? `可读取 ${preview.readable_pages} / ${preview.page_count} 页文字。 ${preview.message}` : preview.message;
        if (preview.pages.length) {
          content.innerHTML = `<label for="exam-preview-page">原件页码</label><select id="exam-preview-page">${preview.pages.map(page=>`<option value="${page.page}">第 ${page.page} 页</option>`).join('')}</select><pre tabindex="0"></pre>`;
          const select = content.querySelector('select'), raw = content.querySelector('pre');
          const display = () => { raw.textContent = preview.pages[Number(select.value)-1]?.text || '此页没有可提取的文字。'; };
          select.onchange = display;
          display();
        } else content.textContent = '请使用「下载原件」查看。';
        if (action && preview.mode !== 'unavailable') {
          original.closest('label').hidden = preview.mode !== 'pdf_text';
          updateScope();
          action.disabled = false;
        }
      } catch (error) {
        if (isCurrent()) {
          status.textContent = error.message;
          host.querySelector('.exam-preview-retry').hidden = false;
        }
      }
    }
    host.querySelector('.exam-preview-retry').onclick = event => { event.currentTarget.hidden = true; read(); };
    panel.ontoggle = () => { if (panel.open) read(); };
    if (!form) return async page => {
      panel.open = true;
      await read();
      if (!isCurrent()) return;
      const select = content.querySelector('select');
      if (select) {
        select.value = page;
        select.dispatchEvent(new Event('change'));
        select.focus();
      } else panel.querySelector('summary').focus();
    };
    original.onchange = updateScope;
    read();
    form.onsubmit = async event => {
      event.preventDefault();
      if (action.disabled || !preview) return;
      action.disabled = true;
      original.disabled = true;
      status.textContent = '正在整理体检发现并核对摘录，请稍候…';
      try {
        await api(endpoint+'/analysis','POST',{consent:true,revision:report.revision,workspace,evidence_mode:original.checked ? 'original' : preview.mode});
      } catch (error) {
        status.textContent = error.message;
        return;
      } finally { action.disabled = false; original.disabled = false; }
      if (isCurrent()) await onAnalyzed();
    };
  }

  async function showReport(key) {
    const ticket = ++generation, detail = get('#exam-detail'), atlas = get('#exam-atlas');
    window.renderBodyAtlas(atlas, [], '', esc);
    detail.innerHTML = '<p class="exam-loading" role="status">正在载入本次检查…</p>';
    try {
      const report = await api('/api/exams/'+encodeURIComponent(key));
      if (!alive() || ticket !== generation) return;
      const findings = report.findings, rows = Array.isArray(findings?.metrics) ? findings.metrics : [];
      const endpoint = '/api/exams/'+encodeURIComponent(key);
      const needsDraft = report.analysis_version < 3;
      detail.innerHTML = `<article class="exam-sheet"><header class="exam-report-head"><div><div class="exam-dateline"><time datetime="${esc(report.date)}">${esc(report.date)}</time><span>${findings?'AI 草稿 · 待核对':'已归档 · 未分析'}</span></div>
        <h2>${findings?'本次体检解读':'报告已入档'}</h2></div><a class="button" href="/api/exams/${encodeURIComponent(key)}/original" download>下载原件</a></header>
        ${needsDraft ? `<section class="exam-preview exam-consent"><h3>${findings?'更新体检解读':'查看解析结果'}</h3><p class="exam-preview-summary" role="status"></p>
          <details class="exam-local-text"><summary>查看本地提取的逐页文字</summary><div></div></details>
          <form id="exam-analyze"><label class="exam-check" hidden><input type="checkbox">表格错位或有图表时，改用完整 PDF 识别</label><p class="exam-send-scope hint"></p><button type="submit" class="primary" disabled>生成 AI 解读</button></form>
          <p id="analysis-progress" role="status"></p><button type="button" class="exam-preview-retry" hidden>重试本地解析</button></section>` : ''}
        ${findings?`<p class="exam-summary">${esc(findings.summary)}</p><p class="hint">${findings.pdfPageEvidenceVerified ? '摘录已匹配 PDF 文字层，页码按原件校验。请核对表格字段和 AI 解读。' : findings.textEvidenceVerified ? '摘录已匹配到文本原件，位置和解读仍需核对。' : '摘录和位置由 AI 识别，请对照原件核实。'} 本解读仅供查阅历史报告和就医沟通。</p>
          ${evidenceList(findings.recommendations, '原报告建议', findings.pdfPageEvidenceVerified)}${evidenceList(findings.observations, '重点发现', findings.pdfPageEvidenceVerified)}
          ${Array.isArray(findings.questions)&&findings.questions.length?`<section class="exam-questions"><h3>就医时可以问</h3><ul>${findings.questions.map(question=>`<li>${esc(question)}</li>`).join('')}</ul></section>`:''}
          ${findings.limitations?.length ? `<section class="exam-reading-section"><h3>资料局限</h3><ul>${findings.limitations.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></section>` : ''}
          <section class="exam-metrics"><h3>指标与依据 <small>${rows.length} 项</small></h3>${rows.length?`<div class="exam-metric-filters"><label for="exam-metric-search">搜索指标或单位</label><input type="search" id="exam-metric-search" placeholder="输入指标名称或单位" autocomplete="off" spellcheck="false"><p class="exam-metric-status" role="status" aria-live="polite"></p></div>${rows.map(metric=>`<details class="exam-metric"><summary><span>${esc(metric.name)}</span><strong>${esc(metric.value)} <small>${esc(metric.unit)}</small></strong><span class="exam-flag">${esc(metric.flag||'未注明')}</span></summary><dl><dt>报告参考范围</dt><dd>${esc(metric.range||'原文未注明')}</dd><dt>原件摘录</dt><dd>${esc(metric.quote)}${metric.location ? ` · ${locationLabel(metric,findings.pdfPageEvidenceVerified)}` : ''}</dd></dl></details>`).join('')}`:'<p>没有提取到可回查的数值指标。</p>'}</section>
          `:''}
        </article>
        ${needsDraft ? '' : '<section class="exam-preview exam-explorer"><details class="exam-local-text"><summary>查看本地提取的逐页文字</summary><div></div></details><p class="exam-preview-summary"></p><p id="analysis-progress" role="status"></p><button type="button" class="exam-preview-retry" hidden>重试本地解析</button></section>'}
        <details class="exam-explorer exam-evidence"><summary>打开来源与草稿笔记</summary>${report.transcript ? `<pre>${esc(report.transcript)}</pre>` : ''}<div class="actions"><button data-note="${esc(report.source_path)}">来源 Markdown</button>${report.report_path?`<button data-note="${esc(report.report_path)}">分析 Markdown</button>`:''}${report.previous_report_path?`<button data-note="${esc(report.previous_report_path)}">查看上一版草稿</button>`:''}</div></details>`;
      const candidates = reports.filter(item => item.ready && item.date < report.date);
      if (candidates.length && rows.length) {
        const section = document.createElement('section'); section.className = 'exam-compare';
        section.innerHTML = `<h3>历次原值对照</h3><p class="hint">仅并列同名、同单位的唯一指标。检测方法可能不同，请核对两次原件。</p>
          <div class="exam-compare-controls"><label for="exam-prior">较早记录</label><select id="exam-prior">${candidates.map(item=>`<option value="${esc(item.id)}">${esc(item.title)}</option>`).join('')}</select><button type="button">查看对照</button></div><div role="status"></div>`;
        get('.exam-metrics').after(section);
        const compare = section.querySelector('button'), result = section.querySelector('[role=status]'), prior = section.querySelector('select');
        prior.onchange = () => { result.replaceChildren(); };
        compare.onclick = async () => {
          compare.disabled = true; prior.disabled = true; result.textContent = '正在读取较早记录…';
          try {
            const previous = await api('/api/exams/'+encodeURIComponent(prior.value));
            if (!alive() || ticket !== generation) return;
            const previousRows = Array.isArray(previous.findings?.metrics) ? previous.findings.metrics : [];
            const pairs = rows.flatMap(metric => {
              const same = other => other.name === metric.name && other.unit === metric.unit;
              const matches = previousRows.filter(same);
              return metric.unit && matches.length === 1 && rows.filter(same).length === 1 ? [[metric,matches[0]]] : [];
            });
            const cell = metric => `<td><strong>${esc(metric.value)}</strong><small>参考 ${esc(metric.range||'未注明')}</small></td>`;
            result.innerHTML = pairs.length ? `<div class="exam-compare-scroll" role="region" aria-label="两次检查原值" tabindex="0"><table><caption>报告原值与各自参考范围</caption><thead><tr><th scope="col">项目（单位）</th><th scope="col">${esc(previous.date)}</th><th scope="col">${esc(report.date)}</th></tr></thead><tbody>${pairs.map(([current,old])=>`<tr><th scope="row">${esc(current.name)} (${esc(current.unit)})</th>${cell(old)}${cell(current)}</tr>`).join('')}</tbody></table></div>` : '两份转录中没有单位明确且唯一匹配的指标。';
          } catch (error) { if (alive() && ticket === generation) result.textContent = error.message; }
          finally { compare.disabled = false; prior.disabled = false; }
        };
      }
      const metricElements = Array.from(detail.querySelectorAll('details.exam-metric'));
      const search = get('#exam-metric-search'), metricStatus = get('.exam-metric-status');
      let flagOnly = false, toggle = null;
      const applyFilters = () => {
        const query = search ? search.value.trim().toLowerCase() : '';
        let shown = 0;
        metricElements.forEach((element,index) => {
          const metric = rows[index] || {};
          const matchesQuery = !query || String(metric.name || '').toLowerCase().includes(query) || String(metric.unit || '').toLowerCase().includes(query);
          const matchesFlag = !flagOnly || element.classList.contains('exam-marked');
          element.hidden = !(matchesQuery && matchesFlag);
          if (!element.hidden) shown++;
        });
        if (metricStatus) metricStatus.textContent = !metricElements.length ? '' : shown === metricElements.length ? `共 ${metricElements.length} 项指标` : shown ? `显示 ${shown} / ${metricElements.length} 项指标` : '没有匹配的指标。';
      };
      if (search) search.addEventListener('input', applyFilters);
      const flagged = metricElements.filter((element,index) => window.isExamMarked(rows[index]));
      if (flagged.length) {
        flagged.forEach(element => element.classList.add('exam-marked'));
        toggle = document.createElement('button'); toggle.type = 'button'; toggle.setAttribute('aria-pressed','false');
        toggle.textContent = `只看报告标记（${flagged.length}）`;
        const filterHost = get('.exam-metric-filters');
        if (metricStatus && filterHost) filterHost.insertBefore(toggle, metricStatus); else if (filterHost) filterHost.append(toggle);
        toggle.onclick = () => {
          flagOnly = !flagOnly;
          toggle.setAttribute('aria-pressed', String(flagOnly));
          toggle.textContent = flagOnly ? '显示全部指标' : `只看报告标记（${flagged.length}）`;
          applyFilters();
        };
      }
      const resetFilter = () => {
        if (search) search.value = '';
        flagOnly = false;
        if (toggle) {
          toggle.setAttribute('aria-pressed','false');
          toggle.textContent = `只看报告标记（${flagged.length}）`;
        }
        applyFilters();
      };
      applyFilters();
      window.renderBodyAtlas(atlas,rows,report.date,esc,index=>{
        const metric = metricElements[index];
        if (!metric) return;
        resetFilter();
        metric.open = true;
        metric.scrollIntoView({block:'center'});
        metric.querySelector('summary').focus({preventScroll:true});
      });
      const openPage = setupPreview(get('.exam-preview'),endpoint,report,()=>alive() && ticket === generation,async()=>{
        try {
          await load(key);
          if (alive()) await refresh();
        } catch (error) { fail(error); }
      });
      detail.querySelectorAll('[data-exam-page]').forEach(button => {
        if (openPage) button.onclick = () => openPage(button.dataset.examPage);
        else button.replaceWith(document.createTextNode(button.textContent));
      });
    } catch (error) {
      if (alive() && ticket === generation) {
        window.renderBodyAtlas(atlas, [], '', esc);
        detail.innerHTML = '<div class="exam-loading"><p role="alert"></p><button type="button">重试载入报告</button></div>';
        detail.querySelector('[role=alert]').textContent = error.message;
        detail.querySelector('button').onclick = () => showReport(key);
      }
    }
  }
  function fail(error) { if (alive()) view.textContent = error.message; }
  await load();
};
