export function validatePhone(value) {
  return /^1[3-9]\d{9}$/.test(String(value || '').trim()) ? '' : '请输入有效的 11 位手机号';
}
export function validatePassword(value) {
  const password = String(value || '');
  if (password.length < 8 || password.length > 72) return '密码需为 8-72 个字符';
  if (/\s/.test(password)) return '密码不能包含空白字符';
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return '密码需同时包含字母和数字';
  return '';
}
export function validateNickname(value) {
  const nickname = String(value || '').trim();
  return nickname.length >= 1 && nickname.length <= 30 ? '' : '昵称需为 1-30 个字符';
}

if (typeof document !== 'undefined') {
  const { apiRequest } = await import('./api.js');
  const tabButtons = [...document.querySelectorAll('[data-auth-tab]')];
  const forms = { login: document.querySelector('#login-form'), register: document.querySelector('#register-form') };
  const errorBox = document.querySelector('#form-error');
  let mode = 'login';
  function setMode(next) {
    mode = next;
    tabButtons.forEach(button => { const active = button.dataset.authTab === mode; button.classList.toggle('is-active', active); button.setAttribute('aria-selected', String(active)); });
    Object.entries(forms).forEach(([key, form]) => { form.hidden = key !== mode; });
    errorBox.textContent = '';
  }
  tabButtons.forEach(button => button.addEventListener('click', () => setMode(button.dataset.authTab)));
  document.querySelectorAll('[data-password-toggle]').forEach(button => button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordToggle);
    const visible = input.type === 'text'; input.type = visible ? 'password' : 'text'; button.setAttribute('aria-pressed', String(!visible)); button.setAttribute('aria-label', visible ? '显示密码' : '隐藏密码');
  }));
  Object.entries(forms).forEach(([key, form]) => form.addEventListener('submit', async event => {
    event.preventDefault(); errorBox.textContent = '';
    const data = Object.fromEntries(new FormData(form));
    const errors = [validatePhone(data.phone), validatePassword(data.password)];
    if (key === 'register') errors.push(validateNickname(data.nickname));
    const firstError = errors.find(Boolean);
    if (firstError) { errorBox.textContent = firstError; return; }
    const submit = form.querySelector('button[type=submit]'); submit.disabled = true; submit.setAttribute('aria-busy', 'true');
    try { await apiRequest('/api/auth/' + key, { method: 'POST', body: data }); window.location.href = key === 'register' ? '/profile.html' : '/'; }
    catch (error) { errorBox.textContent = error.message || '提交失败，请稍后重试'; }
    finally { submit.disabled = false; submit.removeAttribute('aria-busy'); }
  }));
}
