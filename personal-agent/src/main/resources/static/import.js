'use strict';
window.showDocumentImport = function ({view, api, escape, areas, domain, workspace, alive, dirty, onSaved, onCancel}) {
  const exam = Boolean(onCancel);
  const get = selector => view.querySelector(selector);
  view.innerHTML = `
    <header class="area-intro"><div><h1>${exam ? '导入体检报告' : '导入个人资料'}</h1>
      <p>选择文件后，可发送原件给所选模型生成 Markdown 草稿，也可仅保存到 Vault。</p></div></header>
    <form id="document-form">
      <div class="form-grid">
        ${exam ? '' : `<div><label for="document-domain">资料领域</label><select name="domain" id="document-domain" required><option value="">请选择领域</option>${Object.entries(areas).map(([key, [title]]) => `<option value="${key}"${key === domain ? ' selected' : ''}>${escape(title)}</option>`).join('')}</select></div>`}
        <div><label for="document-file">选择文件</label><input id="document-file" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.md,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv" required>
          <p class="hint">PDF、照片、文本或常见 Office 文件 · 最高 12 MB</p></div>
        ${exam ? '' : '<div><label for="document-title">资料标题</label><input id="document-title" name="title" maxlength="150" required></div>'}
        <div><label for="document-date">${exam ? '报告上的检查日期' : '资料日期（可留空）'}</label><input id="document-date" name="date" type="date"${exam ? ' required' : ''}></div>
      </div>
      <p class="hint">选择「同意发送原件并分析」会把完整文件发送给所选模型。请先在文件中遮盖不想发送的内容。</p>
      <div class="actions"><button type="submit" value="archive">仅归档</button>
        <button type="submit" value="analyze" class="primary">同意发送原件并分析</button>
        ${exam ? '<button type="button" id="document-cancel">返回健康档案</button>' : '<a class="button" href="#overview">返回总览</a>'}</div>
      <p id="document-status" role="status"></p>
    </form>`;
  const form = get('#document-form');
  const message = get('#document-status');
  const fileInput = get('#document-file');
  const title = get('#document-title');
  if (exam) get('#document-cancel').onclick = () => {
    if (fileInput.files.length && !confirm('放弃本次导入？')) return;
    dirty(false);
    onCancel();
  };
  fileInput.onchange = () => {
    const file = fileInput.files[0];
    dirty(Boolean(file));
    if (file && title && !title.value) title.value = file.name.replace(/\.[^.]+$/, '').slice(0, 150);
    message.textContent = '';
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (!event.submitter) return;
    const file = fileInput.files[0];
    if (!file || file.size > 12 * 1024 * 1024) {
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
      const saved = await api(exam ? '/api/exams' : '/api/documents', 'POST', data);
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
