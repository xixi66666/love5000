'use strict';

(() => {
  const bodyRegions = [
    {id:'head', label:'头面与五官', x:49, y:10, pattern:/眼底|视力|眼压|听力|口腔|牙周|鼻窦/iu},
    {id:'neck', label:'甲状腺', x:50, y:17, pattern:/甲状腺|促甲状腺素|\b(?:TSH|FT3|FT4|TPOAb)\b/iu},
    {id:'lung', label:'肺与呼吸', x:42, y:23, pattern:/肺|支气管|通气功能|呼吸功能|\b(?:FEV1|FVC)\b/iu},
    {id:'heart', label:'心血管', x:55, y:27, pattern:/心电|心脏|心率|血压|冠状动脉|心肌|颈动脉|\bECG\b/iu},
    {id:'liver', label:'肝胆', x:43, y:33, pattern:/肝|胆囊|胆管|胆红素|转氨酶|\b(?:ALT|AST|GGT)\b/iu},
    {id:'digest', label:'胃肠', x:53, y:40, pattern:/胃|肠|幽门螺杆菌|粪便|大便/iu},
    {id:'kidney', label:'肾与泌尿', x:60, y:37, pattern:/肾|肌酐|膀胱|尿蛋白|尿潜血|尿比重|尿常规|尿素氮|\beGFR\b/iu},
    {id:'bone', label:'骨骼与关节', x:58, y:66, pattern:/骨密度|骨骼|骨质|关节|腰椎|脊柱/iu}
  ];
  const extraRegions = [
    {id:'metabolic', label:'代谢与血液', pattern:/血糖|糖化|葡萄糖|甘油三酯|胆固醇|脂蛋白|尿酸|血红蛋白|血小板|血细胞|白细胞|\b(?:HbA1c|LDL|HDL|WBC|RBC)\b/iu},
    {id:'other', label:'其他与待归类'}
  ];
  function classify(metric) {
    const name = String(metric.name || '').trim();
    return [...bodyRegions,...extraRegions].find(region=>region.pattern?.test(name))?.id || 'other';
  }

  window.isExamMarked = metric => /^(↑+|↓+|H|L|偏高|偏低|高于参考范围|低于参考范围|异常)$/iu.test(String(metric?.flag || '').trim());

  window.renderBodyAtlas = function (container, metrics, date, escape, onMetric) {
    const sections = [...bodyRegions,...extraRegions];
    const grouped = new Map(sections.map(region=>[region.id, []]));
    metrics.forEach((metric,index)=>grouped.get(classify(metric)).push({metric,index}));
    const counted = sections.filter(region=>grouped.get(region.id).length > 0);
    const active = counted.find(region=>grouped.get(region.id).some(item=>window.isExamMarked(item.metric))) || counted[0] || bodyRegions[0];
    const state = region => {
      const items = grouped.get(region.id);
      if (items.some(item=>window.isExamMarked(item.metric))) return 'marked';
      return items.length ? 'recorded' : 'unknown';
    };
    const stateText = {marked:'有报告标记', recorded:'有记录', unknown:'未见记录'};
    container.innerHTML = `<section class="body-atlas" aria-labelledby="body-atlas-title">
      <header class="insight-heading"><div><h2 id="body-atlas-title">身体部位</h2><p>${date ? escape(date) + ' · 所选报告' : '导入并解读体检报告后，指标会显示在对应部位。'}</p></div></header>
      <div class="body-atlas-grid">
        <div class="atlas-scene">
          <div class="atlas-figure"><img src="/health-atlas.png" width="1024" height="1536" alt="人体正面部位示意">
            ${bodyRegions.map(region=>`<button type="button" class="atlas-pin" data-region="${region.id}" data-state="${state(region)}" style="--pin-x:${region.x}%;--pin-y:${region.y}%" aria-label="${region.label}：${stateText[state(region)]}"><span aria-hidden="true"></span></button>`).join('')}
          </div>
          <div class="atlas-legend"><span data-state="recorded">有记录</span><span data-state="marked">有报告标记</span><span data-state="unknown">未见记录</span></div>
        </div>
        <div class="atlas-inspector">
          <div class="atlas-select" aria-label="按部位筛选指标">
            ${sections.map(region=>`<button type="button" data-region="${region.id}" data-state="${state(region)}">${region.label}<small>${grouped.get(region.id).length || ''}</small></button>`).join('')}
          </div>
          <section class="atlas-values" aria-live="polite"></section>
        </div>
      </div>
    </section>`;
    const values = container.querySelector('.atlas-values');
    function select(id) {
      const region = sections.find(item=>item.id===id);
      if (!region) return;
      container.querySelectorAll('[data-region]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.region===id)));
      const items = grouped.get(id);
      values.innerHTML = `<h3>${region.label} <small>${stateText[state(region)]}</small></h3>${items.length ? `<ul>${items.map(({metric,index})=>`<li><button type="button" data-metric-index="${index}"><span>${escape(metric.name)} <small>${escape(metric.flag || '')}</small></span><strong>${escape(metric.value)} <small>${escape(metric.unit)}</small></strong><span aria-hidden="true">↗</span></button></li>`).join('')}</ul>` : '<p>本次资料中未找到对应指标。可选择其他日期或查看报告原件。</p>'}`;
    }
    select(active.id);
    container.onclick = event => {
      const region = event.target.closest('[data-region]');
      const metric = event.target.closest('[data-metric-index]');
      if (region) select(region.dataset.region);
      if (metric && onMetric) onMetric(Number(metric.dataset.metricIndex));
    };
  };

  const overviewLabels = {
    profile:'档案脉络', finance:'资产与账单档案', work:'项目与成果脉络', learning:'学习轨迹',
    life:'生活记录图谱', relationships:'共同事项脉络', goals:'目标与复盘轨迹', home:'物品与维保脉络',
    documents:'证件与合同关系', analysis:'分析与来源', health:'健康文档图谱'
  };

  window.renderDomainInsights = function (container, data, domain, escape) {
    const history = Object.entries(data.edits || {});
    const most = Math.max(...history.map(([,total])=>total),1);
    const graphName = overviewLabels[domain] || '资料图谱';
    container.innerHTML = `<section class="domain-insights" aria-label="${graphName}">
      <div class="domain-graph">
        <header class="insight-heading"><div><h2>${graphName}</h2><p>${data.nodes.length} 篇入图 · ${data.edges.length} 条 Obsidian 双链</p></div></header>
        <div class="graph-stage insight-graph"><canvas aria-hidden="true"></canvas>${data.nodes.length ? '' : '<div class="graph-empty"><p>导入资料后，笔记会出现在这里。<br>已解析的双链会显示为连线。</p></div>'}</div>
        ${domain==='health' ? '<p class="graph-caption"><i></i> 资料笔记 <i class="legend-draft"></i> 体检解读草稿</p>' : '<p class="graph-caption">点击节点打开笔记</p>'}
      </div>
      <div class="domain-activity">
        <header class="insight-heading"><div><h2>资料动向</h2><p>按笔记最后编辑月份统计</p></div></header>
        <div class="activity-bars" aria-label="近六个月最后编辑的笔记">${history.map(([month,total])=>`<div aria-label="${escape(month)} ${total} 篇"><strong>${total}</strong><span style="--bar:${100*total/most}%"></span><small>${escape(month.slice(5))}月</small></div>`).join('')}</div>
        ${data.recent.length ? `<ol class="insight-recent">${data.recent.slice(0,3).map(note=>`<li><a href="${window.noteHash(note.path)}">${escape(note.title)}</a><time>${escape(note.modified_at?.slice(0,10))}</time></li>`).join('')}</ol>` : '<p class="graph-caption">当前领域暂无编辑记录。</p>'}
      </div>
    </section>`;
    if (data.nodes.length) window.renderVaultGraph(container.querySelector('.graph-stage'),data);
  };
})();
