'use strict';

(() => {
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
