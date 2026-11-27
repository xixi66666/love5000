'use strict';

window.noteHash = (path, heading = '') => '#note=' + encodeURIComponent(path) + (heading ? '&heading=' + encodeURIComponent(heading) : '');

window.renderPersonalOverview = function (view, vault, data, escape, onSearch) {
  const date = value => value ? String(value).slice(0, 10) : '';
  const hasNotes = data.nodes.length > 0;
  const areas = Object.entries(window.personalAreas);
  view.innerHTML = `<header class="workspace-intro">
    <span class="workspace-label"><i aria-hidden="true"></i> OBSIDIAN VAULT</span>
    <h1>个人资料总览</h1>
    <div class="workspace-intro-bar"><p>${escape(vault.name)}<span> / </span>${escape(vault.notes) || '0'} 篇笔记</p>
    <form id="overview-search"><input id="overview-query" aria-label="搜索全部笔记" placeholder="搜索笔记标题或正文…" maxlength="300"><button type="submit">搜索 <span aria-hidden="true">↵</span></button></form></div>
    <div class="actions workspace-shortcuts">
      <a href="#import" class="button primary">导入资料</a>
      <a href="#health-import" class="button">导入体检报告</a>
      <a href="#analysis" class="button">分析已有笔记</a>
    </div>
  </header>
  <div class="workspace-board">
    <section class="graph-panel" aria-labelledby="graph-title">
      <header class="board-header"><h2 id="graph-title">笔记双链图谱</h2><span>${hasNotes ? `${data.nodes.length} 节点 · ${data.edges.length} 链接` : '笔记尚未导入'}</span><a href="#health">历年健康关联 ↗</a></header>
      <div class="graph-stage" id="overview-graph" ${hasNotes ? '' : 'data-empty'}><canvas aria-hidden="true"></canvas>
        ${hasNotes ? '' : '<div class="graph-empty"><b>[[笔记名称]]</b><p>在 Markdown 里引用一篇笔记，<br>两者的连接就会出现在这里。</p><a href="#notes">浏览资料目录 ↗</a></div>'}
      </div>
      <footer class="graph-footer"><span>${hasNotes ? '最近编辑的笔记 · 点击节点打开' : '导入或创建笔记后显示图谱'}</span><button id="graph-full" class="quiet" type="button">完整 Quartz 图谱 ↗</button></footer>
    </section>
    <section class="recent-panel" aria-labelledby="recent-title">
      <header class="board-header"><h2 id="recent-title">最近编辑</h2><a href="#notes">全部笔记 ↗</a></header>
      ${data.recent.length ? `<ul>${data.recent.map(note=>`<li><a href="${window.noteHash(note.path)}"><span>${escape(note.title)}</span><small>${escape(window.personalAreas[note.domain]?.[0] || (note.domain === 'analysis' ? 'AI 报告' : note.domain))} · ${escape(date(note.modified_at))}</small></a></li>`).join('')}</ul>` : '<p class="recent-empty">编辑过的笔记会出现在这里。</p>'}
    </section>
  </div>
  <section class="workspace-areas" aria-labelledby="workspace-areas-title">
    <div class="board-header"><h2 id="workspace-areas-title">资料领域</h2><button type="button" class="quiet" data-ask-area="">跨领域复盘 ↗</button></div>
    <div class="area-rows">${areas.map(([key, [title, examples, question]])=>`<details class="area-row"><summary><strong>${escape(title)}</strong><span class="area-examples">${escape(examples)}</span><span class="area-count">${vault.domains?.[key] || 0} 篇</span></summary><div class="area-row-body"><p>${escape(question)}</p><div class="actions"><button type="button" data-domain="${key}">查看资料</button><button type="button" data-import-domain="${key}">导入到此领域</button><button type="button" data-ask-area="${key}">用这个问题分析</button>${key === 'health' ? '<a class="button" href="#health">查看体检档案</a>' : ''}</div></div></details>`).join('')}</div>
  </section>`;
  view.querySelector('#overview-search').onsubmit = event => {
    event.preventDefault();
    onSearch(view.querySelector('#overview-query').value.trim());
  };
  view.querySelector('#graph-full').onclick = () => {
    const quartz = document.querySelector('#library');
    if (!quartz.hidden) quartz.click();
    else {
      document.querySelector('#quartz-panel').scrollIntoView({block:'nearest'});
      const build = document.querySelector('#build');
      if (!build.disabled) build.focus();
    }
  };
  if (hasNotes) window.renderVaultGraph(view.querySelector('#overview-graph'), data);
};

window.renderVaultGraph = function (stage, data) {
  const canvas = stage.querySelector('canvas');
  const positions = new Map();
  const weights = new Map();
  for (const edge of data.edges) {
    weights.set(edge.from, (weights.get(edge.from) || 0) + 1);
    weights.set(edge.to, (weights.get(edge.to) || 0) + 1);
  }
  const nodes = [...data.nodes].sort((left, right) => (weights.get(right.path) || 0) - (weights.get(left.path) || 0));
  let active = '';
  nodes.forEach((note, index) => {
    const angle = index * Math.PI * (3 - Math.sqrt(5));
    const radius = index ? 0.39 * Math.sqrt(index / (nodes.length - 1)) : 0;
    const point = {x:0.5 + Math.cos(angle) * radius, y:0.5 + Math.sin(angle) * radius};
    positions.set(note.path, point);
    const anchor = document.createElement('a');
    anchor.className = 'graph-node';
    anchor.href = window.noteHash(note.path);
    anchor.setAttribute('aria-label', note.title);
    anchor.style.left = point.x * 100 + '%';
    anchor.style.top = point.y * 100 + '%';
    if (index === 0) anchor.classList.add('graph-node-main');
    if (note.domain === 'analysis') anchor.classList.add('graph-node-draft');
    if (nodes.length <= 7) anchor.classList.add('graph-node-labeled');
    const label = document.createElement('span');
    label.textContent = note.title;
    anchor.append(label);
    stage.append(anchor);
    anchor.onpointerenter = anchor.onfocus = () => { active = note.path; draw(); };
    anchor.onpointerleave = () => { if (document.activeElement !== anchor) { active = ''; draw(); } };
    anchor.onblur = () => { active = ''; draw(); };
  });
  function draw() {
    const width = stage.clientWidth, height = stage.clientHeight, density = Math.min(devicePixelRatio || 1, 2);
    if (!width || !height) return;
    if (canvas.width !== Math.round(width * density) || canvas.height !== Math.round(height * density)) {
      canvas.width = Math.round(width * density);
      canvas.height = Math.round(height * density);
    }
    const context = canvas.getContext('2d');
    if (!context) return;
    context.setTransform(density,0,0,density,0,0);
    context.clearRect(0,0,width,height);
    for (const {from,to} of data.edges) {
      const source = positions.get(from), target = positions.get(to);
      if (!source || !target) continue;
      const related = active && (active === from || active === to);
      context.strokeStyle = related ? '#d4c0ff' : active ? 'rgba(174,139,255,.15)' : 'rgba(174,139,255,.42)';
      context.lineWidth = related ? 2 : 1;
      context.beginPath();
      context.moveTo(source.x * width, source.y * height);
      context.lineTo(target.x * width, target.y * height);
      context.stroke();
    }
  }
  draw();
  const resize = new ResizeObserver(draw);
  resize.observe(stage);
  viewCleanup(stage, resize);
};

function viewCleanup(stage, resize) {
  const observer = new MutationObserver(() => {
    if (stage.isConnected) return;
    resize.disconnect();
    observer.disconnect();
  });
  observer.observe(document.querySelector('#view'), {childList:true});
}

window.renderNoteReading = function (heading) {
  const preview = document.querySelector('#reading-preview');
  const lists = [...document.querySelectorAll('.reading-outline')];
  const headings = [...preview.querySelectorAll('h1,h2,h3,h4,h5,h6')];
  for (const [index, element] of headings.entries()) {
    element.id = 'reading-heading-' + index;
    for (const list of lists) {
      const item = document.createElement('li'), link = document.createElement('button');
      link.type = 'button';
      link.textContent = element.textContent;
      link.onclick = () => element.scrollIntoView({block:'start'});
      item.append(link);
      list.append(item);
    }
  }
  if (heading) requestAnimationFrame(() => headings.find(element => element.textContent.trim().toLowerCase() === heading.trim().toLowerCase())?.scrollIntoView());
  if (headings.length === 0) lists.forEach(list=>{list.closest('section,details').hidden=true;});
  for (const anchor of preview.querySelectorAll('a')) {
    if (anchor.getAttribute('href').startsWith('#note=')) {
      anchor.classList.add('wiki-link');
    } else {
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
    }
  }
};
