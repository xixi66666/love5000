'use strict';
const documentFormats = '.pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.md,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv';
const supportedDocumentExtensions = new Set(documentFormats.split(','));
const maxDocumentSize = 12 * 1024 * 1024;

window.showDocumentImport = function ({view, api, escape, areas, domain, workspace, alive, dirty, onSaved}) {
  const get = selector => view.querySelector(selector);
  view.innerHTML = `
    <header class="area-intro"><div><h1>导入个人资料</h1>
      <p>选择文件后，可发送原件给所选模型生成 Markdown 草稿，也可仅保存到 Vault。</p></div></header>
    <form id="document-form">
      <div class="form-grid">
        <div><label for="document-domain">资料领域</label><select name="domain" id="document-domain" required><option value="">请选择领域</option>${Object.entries(areas).map(([key, [title]]) => `<option value="${key}"${key === domain ? ' selected' : ''}>${escape(title)}</option>`).join('')}</select></div>
        <div class="full"><label for="document-file">选择文件</label><input class="document-file" id="document-file" name="file" type="file" accept="${documentFormats}" required>
          <p class="hint">PDF、照片、文本或常见 Office 文件 · 最高 12 MB</p></div>
        <div><label for="document-title">资料标题</label><input id="document-title" name="title" maxlength="150" required></div>
        <div><label for="document-date">资料日期（可留空）</label><input id="document-date" name="date" type="date"></div>
      </div>
      <p class="hint">选择「同意发送原件并分析」会把完整文件发送给所选模型。请先在文件中遮盖不想发送的内容。</p>
      <div class="actions"><button type="submit" value="archive">仅归档</button>
        <button type="submit" value="analyze" class="primary">同意发送原件并分析</button>
        <a class="button" href="#overview">返回总览</a></div>
      <p id="document-status" role="status"></p>
    </form>`;
  const form = get('#document-form');
  const message = get('#document-status');
  const fileInput = get('#document-file');
  const title = get('#document-title');
  const date = get('#document-date');
  fileInput.onchange = () => {
    const file = fileInput.files[0];
    dirty(Boolean(file));
    if (file && title && !title.value) title.value = file.name.replace(/\.[^.]+$/, '').slice(0, 150);
    message.textContent = '';
  };
  date.addEventListener('input', () => dirty(Boolean(date.value || fileInput.files.length)));
  form.onsubmit = async event => {
    event.preventDefault();
    if (!event.submitter) return;
    const file = fileInput.files[0];
    if (!file || file.size > maxDocumentSize) {
      message.textContent = '请选择不超过 12 MB 的文件。';
      return;
    }
    const mode = event.submitter.value;
    const data = new FormData(form);
    data.append('mode', mode);
    data.append('workspace', workspace);
    if (mode === 'analyze') data.append('consent', 'true');
    const fields = Array.from(form.elements);
    fields.forEach(field => { field.disabled = true; });
    message.textContent = mode === 'analyze' ? '正在读取原件并整理草稿…' : '正在保存原件…';
    try {
      const saved = await api('/api/documents', 'POST', data);
      if (alive()) {
        dirty(false);
        await onSaved(saved, data.get('domain'));
      }
    } catch (error) {
      if (alive()) message.textContent = error.message;
    } finally {
      fields.forEach(field => { field.disabled = false; });
    }
  };
};

function examDateFromFilename(name) {
  const dates = new Set();
  for (const pattern of [/(?:^|\D)(\d{4})(?:[-_.]|年)(\d{1,2})(?:[-_.]|月)(\d{1,2})(?!\d)/g, /(?:^|\D)(\d{4})(\d{2})(\d{2})(?!\d)/g]) {
    for (const [, year, month, day] of name.matchAll(pattern)) {
      const value = [year, month.padStart(2, '0'), day.padStart(2, '0')].join('-');
      const date = new Date(value);
      if (+year && Number.isFinite(date.getTime()) && date.toISOString().startsWith(value + 'T')) dates.add(value);
    }
  }
  return dates.size === 1 ? dates.values().next().value : '';
}

window.showExamImport = function ({view, api, escape, workspace, alive, dirty, onExit}) {
  view.innerHTML = `
    <header class="area-intro"><div><h1>导入体检报告</h1>
      <p>可一次选择多份报告。请逐份核对检查日期，归档后可打开各年的报告查看和对照。</p></div></header>
    <form id="exam-import-form" class="exam-import-form">
      <label for="exam-import-files">添加体检报告</label>
      <input class="document-file" id="exam-import-files" type="file" accept="${documentFormats}" multiple aria-describedby="exam-import-hint">
      <p class="hint" id="exam-import-hint">支持多选 PDF，也可添加照片、文本和常见 Office 文件。单份不超过 12 MB，归档仅保存到本机 Vault。</p>
      <p id="exam-import-selection" role="status" hidden></p>
      <ul class="exam-import-queue" aria-label="待归档报告"></ul>
      <div class="actions"><button type="submit" class="primary" disabled>归档报告</button>
        <button type="button" id="exam-import-back">返回健康档案</button></div>
      <p id="exam-import-progress" role="status"></p>
    </form>`;

  const form = view.querySelector('form'), picker = view.querySelector('#exam-import-files');
  const queue = form.querySelector('ul'), submit = form.querySelector('[type=submit]'), back = form.querySelector('#exam-import-back');
  const progress = form.querySelector('#exam-import-progress'), selection = form.querySelector('#exam-import-selection');
  const entries = [];
  let busy = false;

  function updateActions() {
    const pending = entries.filter(entry => !entry.saved);
    const saved = entries.length - pending.length;
    dirty(Boolean(pending.length || busy));
    submit.disabled = busy || !pending.length;
    submit.hidden = !pending.length && Boolean(saved);
    submit.textContent = busy ? '正在归档…' : pending.some(entry => entry.error) ? '重试未归档报告' : pending.length > 1 ? `归档 ${pending.length} 份报告` : '归档报告';
    back.textContent = saved ? `查看已归档报告（${saved}）` : '返回健康档案';
    for (const control of [back, picker, ...queue.querySelectorAll('input, button')]) {
      control.disabled = busy || control.closest('li')?.dataset.saved === 'true';
    }
  }

  function leave() {
    const latest = entries.filter(entry => entry.saved).reduce((previous, entry) => !previous || entry.date > previous.date ? entry : previous, null);
    dirty(false);
    onExit(latest?.saved.id);
  }

  back.onclick = () => {
    if (entries.some(entry => !entry.saved) && !confirm('离开并放弃尚未归档的文件？')) return;
    leave();
  };

  picker.onchange = () => {
    const rejected = [];
    for (const file of picker.files) {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      if (!supportedDocumentExtensions.has(ext) || !file.size || file.size > maxDocumentSize) {
        rejected.push(file.name);
        continue;
      }
      const date = examDateFromFilename(file.name);
      const row = document.createElement('li');
      row.className = 'exam-import-row';
      row.innerHTML = `<div class="exam-import-file"><strong>${escape(file.name)}</strong><p class="exam-import-row-status hint"></p></div>
        <label>检查日期
          <input aria-label="${escape(file.name)} 的检查日期" type="date" min="0001-01-01" max="9999-12-31" value="${date}" required>${date ? '<small>从文件名预填，请核对</small>' : ''}</label>
        <button type="button" class="quiet" aria-label="移除 ${escape(file.name)}">移除</button>`;
      const entry = {file, date, row, importId: crypto.randomUUID(), input:row.querySelector('input'), status:row.querySelector('p')};
      entries.push(entry);
      queue.append(row);
      row.querySelector('button').onclick = () => {
        entries.splice(entries.indexOf(entry), 1);
        row.remove();
        progress.textContent = '';
        updateActions();
        picker.focus();
      };
    }
    picker.value = '';
    progress.textContent = '';
    selection.textContent = rejected.length ? `未添加以下文件（格式不受支持、文件为空或超过 12 MB）：${rejected.join('、')}` : '';
    selection.hidden = !rejected.length;
    updateActions();
  };

  form.onsubmit = async event => {
    event.preventDefault();
    if (busy) return;
    const pending = entries.filter(entry => !entry.saved);
    if (!pending.length) return;
    busy = true;
    updateActions();
    for (let index = 0; index < pending.length && alive(); index++) {
      const entry = pending[index];
      entry.date = entry.input.value;
      entry.error = '';
      progress.textContent = `正在归档第 ${index + 1} / ${pending.length} 份报告…`;
      entry.status.textContent = '正在归档…';
      entry.status.classList.remove('error');
      const data = new FormData();
      data.append('mode', 'archive');
      data.append('workspace', workspace);
      data.append('file', entry.file);
      data.append('date', entry.date);
      data.append('import_id', entry.importId);
      try {
        entry.saved = await api('/api/exams', 'POST', data);
        entry.row.dataset.saved = 'true';
        entry.status.textContent = '已归档';
        entry.row.querySelector('button').hidden = true;
      } catch (error) {
        entry.error = error.message;
        entry.status.textContent = error.message;
        entry.status.classList.add('error');
      }
    }
    busy = false;
    if (!alive()) return;
    const savedCount = entries.filter(entry => entry.saved).length;
    const remaining = entries.length - savedCount;
    progress.textContent = remaining ? `已归档 ${savedCount} 份，${remaining} 份需要重试。` : `已归档 ${savedCount} 份报告。`;
    updateActions();
    if (entries.length === 1 && savedCount === 1) leave();
  };
};
