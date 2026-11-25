'use strict';
window.showHealthArchive = async function ({view, api, escape: esc, alive, refresh, dirty}) {
  const get = selector => view.querySelector(selector);
  let reports, workspace, generation = 0;
  view.innerHTML = '<p role="status">正在读取本地健康档案…</p>';
  const mast = `<header class="health-workbench"><div><h1>健康档案</h1><p>查阅体检记录、原件依据和历次检查结果。</p></div><button type="button" id="exam-import" class="primary">导入报告</button></header>`;

  async function load(prefer) {
    const token = ++generation;
    const data = await api('/api/exams');
    if (!alive() || token !== generation) return;
    reports = data.reports; workspace = data.workspace;
    view.innerHTML = mast + (reports.length ? `<div class="exam-selector"><label for="exam-select">检查记录 <small>${reports.length} 份</small></label><select id="exam-select">${reports.map(report => `<option value="${esc(report.id)}">${esc(report.title)} · ${report.ready?'有 AI 草稿':'待分析'}</option>`).join('')}</select></div>` :
      '<section class="exam-empty"><h2>还没有体检报告</h2><p>上传报告后，可以仅归档，或确认发送原件后生成解读。</p></section>')
      + '<div id="exam-atlas"></div><div id="exam-detail"></div>'
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
    generation++;
    window.showDocumentImport({view, api, escape:esc, workspace, alive, dirty,
      onCancel:()=>load().catch(fail),
      onSaved:async saved=>{
        await load(saved.id);
        if (!alive()) return;
        if (saved.warning && get('#analysis-progress')) {
          get('#analysis-progress').textContent = '原件已归档。' + saved.warning;
        }
        await refresh();
      }});
  }

  function evidenceList(entries, title) {
    if (!entries?.length) return '';
    return `<section class="exam-reading-section"><h3>${title}</h3><ul class="exam-evidence-list">${entries.map(entry =>
      `<li><blockquote>${esc(entry.quote)}</blockquote><p class="exam-location">${esc(entry.location)}</p>
      ${entry.interpretation ? `<p><strong>AI 解读</strong> ${esc(entry.interpretation)}</p>` : ''}</li>`).join('')}</ul></section>`;
  }

  async function showReport(key) {
    const ticket = ++generation, detail = get('#exam-detail'), atlas = get('#exam-atlas');
    window.renderBodyAtlas(atlas, [], '', esc);
    detail.innerHTML = '<p class="exam-loading" role="status">正在载入本次检查…</p>';
    try {
      const report = await api('/api/exams/'+encodeURIComponent(key));
      if (!alive() || ticket !== generation) return;
      const findings = report.findings, rows = Array.isArray(findings?.metrics) ? findings.metrics : [];
      const needsDraft = report.analysis_version !== 2;
      detail.innerHTML = `<article class="exam-sheet"><header class="exam-report-head"><div><div class="exam-dateline"><time datetime="${esc(report.date)}">${esc(report.date)}</time><span>${findings?'AI 草稿 · 待核对':'已归档 · 未分析'}</span></div>
        <h2>${findings?'本次体检解读':'报告已入档'}</h2></div><a class="button" href="/api/exams/${encodeURIComponent(key)}/original" download>下载原件</a></header>
        <p class="exam-summary">${findings?esc(findings.summary):'原件已保存在 Vault。确认发送后可生成一份可回查的解读。'}</p>
        ${findings?`<p class="hint">${findings.textEvidenceVerified ? '摘录已匹配到文本原件，位置和解读仍需核对。' : '原件摘录和位置由 AI 提取，建议下载原件核对。'}</p>
          ${evidenceList(findings.observations, '重点发现')}${evidenceList(findings.recommendations, '原报告建议')}
          ${findings.limitations?.length ? `<section class="exam-reading-section"><h3>资料局限</h3><ul>${findings.limitations.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></section>` : ''}
          <section class="exam-metrics"><h3>指标与依据 <small>${rows.length} 项</small></h3>${rows.length?`<div class="exam-metric-filters"><label for="exam-metric-search">搜索指标或单位</label><input type="search" id="exam-metric-search" placeholder="输入指标名称或单位" autocomplete="off" spellcheck="false"><p class="exam-metric-status" role="status" aria-live="polite"></p></div>${rows.map(metric=>`<details class="exam-metric"><summary><span>${esc(metric.name)}</span><strong>${esc(metric.value)} <small>${esc(metric.unit)}</small></strong><span class="exam-flag">${esc(metric.flag||'未注明')}</span></summary><dl><dt>报告参考范围</dt><dd>${esc(metric.range||'原文未注明')}</dd><dt>原件摘录</dt><dd>${esc(metric.quote)}${metric.location ? ` · ${esc(metric.location)}` : ''}</dd></dl></details>`).join('')}`:'<p>没有提取到可回查的数值指标。</p>'}</section>
          ${Array.isArray(findings.questions)&&findings.questions.length?`<section class="exam-questions"><h3>就医时可以问</h3><ul>${findings.questions.map(question=>`<li>${esc(question)}</li>`).join('')}</ul></section>`:''}<p class="hint">这份草稿描述检查当时的资料，不代表当前身体状况，也不能替代医生诊断。</p>`:''}
        ${needsDraft ? `<form class="exam-consent" id="exam-analyze"><h3>${findings?'生成新版解读':'生成 AI 解读'}</h3><p>确认后，体检原件内容将发送至所选模型。${findings?'原草稿会保留。':''}</p><button class="primary">同意发送原件并分析</button></form>` : ''}
        <p id="analysis-progress" role="status"></p></article><details class="exam-explorer exam-evidence"><summary>来源 Markdown 与旧版正文</summary>${report.transcript ? `<pre>${esc(report.transcript)}</pre>` : ''}<div class="actions"><button data-note="${esc(report.source_path)}">来源 Markdown</button>${report.report_path?`<button data-note="${esc(report.report_path)}">分析 Markdown</button>`:''}</div></details>`;
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
      const form = get('#exam-analyze');
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
      if (form) form.onsubmit = async event => {
        event.preventDefault(); const button = form.querySelector('button'), progress = get('#analysis-progress');
        if (button.disabled) return;
        button.disabled = true; progress.textContent = '正在读取体检原件…';
        try {
          await api('/api/exams/'+encodeURIComponent(key)+'/analysis','POST',{consent:true,revision:report.revision,workspace});
          if (alive() && ticket === generation) { await load(key); if (alive()) await refresh(); }
        } catch (error) { progress.textContent = error.message; }
        finally { button.disabled = false; }
      };
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
