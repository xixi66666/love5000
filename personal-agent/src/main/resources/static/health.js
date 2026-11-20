'use strict';
window.showHealthArchive = async function ({view, api, escape: esc, alive, refresh, dirty}) {
  const get = selector => view.querySelector(selector);
  let reports, workspace, generation = 0;
  view.innerHTML = '<p role="status">正在读取本地健康档案…</p>';
  const mast = `<header class="health-workbench"><div><h1>健康档案</h1><p>按身体部位查看报告指标，沿文档双链回查依据。</p></div><button type="button" id="exam-import" class="primary">＋ 导入报告</button></header>`;

  async function load(prefer) {
    const token = ++generation;
    const data = await api('/api/exams');
    if (!alive() || token !== generation) return;
    reports = data.reports; workspace = data.workspace;
    view.innerHTML = mast + (reports.length ? `<div class="exam-selector"><label for="exam-select">检查记录 · ${reports.length} 份</label><select id="exam-select">${reports.map(report => `<option value="${esc(report.id)}">${esc(report.title)} · ${report.ready?'有 AI 草稿':'待分析'}</option>`).join('')}</select></div>` : '')
      + '<div class="health-visuals"><div id="exam-atlas"></div><div id="health-insights" role="region" aria-label="健康资料图谱" aria-busy="true"></div></div>'
      + (reports.length ? '<div id="exam-detail" aria-live="polite"></div>' :
        '<section class="exam-empty"><h2>还没有体检报告</h2><p>上传报告后，可直接生成解读或仅归档。</p><button id="exam-first">选择第一份报告</button></section>');
    const graph = get('#health-insights');
    api('/api/vault/overview?domain=health').then(overview=>{
      if (alive() && graph.isConnected) window.renderDomainInsights(graph,overview,'health',esc);
    }).catch(error=>{
      if (alive() && graph.isConnected) graph.textContent=error.message;
    }).finally(()=>graph.removeAttribute('aria-busy'));
    get('#exam-import').onclick = importView;
    if (!reports.length) {
      window.renderBodyAtlas(get('#exam-atlas'),[],'',esc);
      get('#exam-first').onclick = importView;
      return;
    }
    const select = get('#exam-select');
    if (reports.some(report => report.id === prefer)) select.value = prefer;
    else if (reports.some(report => report.ready)) select.value = reports.find(report => report.ready).id;
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

  async function showReport(key) {
    const ticket = ++generation, detail = get('#exam-detail');
    get('#exam-atlas').textContent = '正在读取所选报告的部位指标…';
    detail.textContent = '正在载入本次检查…';
    try {
      const report = await api('/api/exams/'+encodeURIComponent(key));
      if (!alive() || ticket !== generation) return;
      const findings = report.findings, rows = Array.isArray(findings?.metrics) ? findings.metrics : [];
      detail.innerHTML = `<article class="exam-sheet"><div class="exam-dateline"><span>检查日期</span><time>${esc(report.date)}</time><span class="pill">${findings?'AI 草稿 · 待核对':'已归档 · 未分析'}</span></div>
        <h2>${findings?'本次体检解读':'报告已入档'}</h2><p class="exam-summary">${findings?esc(findings.summary):'原件已保存在 Vault。你可以随时用 DeepSeek 生成一份解读。'}</p>
        ${findings?`<section class="exam-metrics"><h3>指标与依据 <small>${rows.length} 项</small></h3><p class="hint">以下引文和位置由 AI 提取，请打开原件核对。</p>${rows.length?rows.map(metric=>`<details class="exam-metric"><summary><span>${esc(metric.name)}</span><strong>${esc(metric.value)} <small>${esc(metric.unit)}</small></strong><span class="exam-flag">${esc(metric.flag||'未注明')}</span></summary><dl><dt>报告参考范围</dt><dd>${esc(metric.range||'原文未注明')}</dd><dt>原件摘录</dt><dd>${esc(metric.quote)}${metric.location ? ` · ${esc(metric.location)}` : ''}</dd></dl></details>`).join(''):'<p>没有可逐字核对的结构化指标，请参阅正文。</p>'}</section>
          ${Array.isArray(findings.questions)&&findings.questions.length?`<section class="exam-questions"><h3>就医时可以问</h3><ul>${findings.questions.map(question=>`<li>${esc(question)}</li>`).join('')}</ul></section>`:''}<p class="hint">这份草稿描述检查当时的资料，不代表当前身体状况，也不能替代医生诊断。</p>`:''}
        </article><section class="exam-evidence"><h2>来源与文件</h2>${report.transcript ? `<details><summary>查看旧版核对正文</summary><pre>${esc(report.transcript)}</pre></details>` : ''}<div class="actions"><a class="button" href="/api/exams/${encodeURIComponent(key)}/original" download>下载原件</a><button data-note="${esc(report.source_path)}">来源 Markdown</button>${report.report_path?`<button data-note="${esc(report.report_path)}">分析 Markdown</button>`:''}</div></section>
        ${!findings ? `<form class="exam-consent" id="exam-analyze"><h2>生成 AI 解读</h2><p>DeepSeek 会接收完整体检原件。</p><button class="primary">同意发送原件并分析</button></form>` : ''}<p id="analysis-progress" role="status"></p>`;
      const prior = reports.find(item => item.ready && item.date < report.date);
      if (prior && rows.length) {
        const section = document.createElement('section'); section.className = 'exam-compare';
        section.innerHTML = `<h3>两次检查对照</h3><p class="hint">与 ${esc(prior.date)} 的草稿对照。只并列同名、同单位的项目，不判断好转或恶化。</p><button type="button">查看可比指标</button><div role="status"></div>`;
        get('.exam-metrics').after(section);
        const compare = section.querySelector('button'), result = section.querySelector('[role=status]');
        compare.onclick = async () => {
          compare.disabled = true; result.textContent = '正在读取上次检查…';
          try {
            const previous = await api('/api/exams/'+encodeURIComponent(prior.id));
            const previousRows = Array.isArray(previous.findings?.metrics) ? previous.findings.metrics : [];
            const pairs = rows.flatMap(metric => {
              const same = other => other.name === metric.name && other.unit === metric.unit;
              const matches = previousRows.filter(same);
              return metric.unit && matches.length === 1 && rows.filter(same).length === 1 ? [[metric,matches[0]]] : [];
            });
            result.innerHTML = pairs.length ? `<table><caption>报告原值对照</caption><thead><tr><th>项目</th><th>${esc(previous.date)}</th><th>${esc(report.date)}</th></tr></thead><tbody>${pairs.map(([current,old])=>`<tr><th>${esc(current.name)} (${esc(current.unit)})</th><td>${esc(old.value)}</td><td>${esc(current.value)}</td></tr>`).join('')}</tbody></table>` : '两份转录中没有单位明确且唯一匹配的指标。';
            compare.hidden = true;
          } catch (error) { result.textContent = error.message; compare.disabled = false; }
        };
      }
      const form = get('#exam-analyze');
      const metricElements = Array.from(detail.querySelectorAll('details.exam-metric'));
      let resetFilter = () => {};
      window.renderBodyAtlas(get('#exam-atlas'),rows,report.date,esc,index=>{
        const metric = metricElements[index];
        if (!metric) return;
        resetFilter();
        metric.open = true;
        metric.scrollIntoView({block:'center'});
        metric.querySelector('summary').focus({preventScroll:true});
      });
      const flagged = metricElements.filter((element,index) => window.isExamMarked(rows[index]));
      if (flagged.length) {
        flagged.forEach(element => element.classList.add('exam-marked'));
        const toggle = document.createElement('button'); toggle.type = 'button'; toggle.setAttribute('aria-pressed','false');
        toggle.textContent = `只看报告标记（${flagged.length}）`; get('.exam-metrics .hint').after(toggle);
        toggle.onclick = () => {
          const filter = toggle.getAttribute('aria-pressed') !== 'true'; toggle.setAttribute('aria-pressed',String(filter));
          toggle.textContent = filter ? '显示全部指标' : `只看报告标记（${flagged.length}）`;
          metricElements.forEach(element => { element.hidden = filter && !element.classList.contains('exam-marked'); });
        };
        resetFilter = () => { if (toggle.getAttribute('aria-pressed') === 'true') toggle.click(); };
      }
      if (form) form.onsubmit = async event => {
        event.preventDefault(); const button = form.querySelector('button'), progress = get('#analysis-progress');
        if (button.disabled) return;
        button.disabled = true; progress.textContent = 'DeepSeek 正在读取体检原件…';
        try {
          await api('/api/exams/'+encodeURIComponent(key)+'/analysis','POST',{consent:true,revision:report.revision,workspace});
          if (alive() && ticket === generation) { await load(key); if (alive()) await refresh(); }
        } catch (error) { progress.textContent = error.message; }
        finally { button.disabled = false; }
      };
    } catch (error) {
      if (alive() && ticket === generation) {
        get('#exam-atlas').replaceChildren();
        detail.textContent = error.message;
      }
    }
  }
  function fail(error) { if (alive()) view.textContent = error.message; }
  await load();
};
