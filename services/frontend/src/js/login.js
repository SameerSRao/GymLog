if (localStorage.getItem('access_token') && !isTokenExpired()) {
  window.location.replace('/');
}

const usernameEl = document.getElementById('username');
const passwordEl = document.getElementById('password');
const btn = document.getElementById('btn');
const errorEl = document.getElementById('error');

async function login() {
  const username = usernameEl.value.trim();
  const password = passwordEl.value.trim();
  if (!username || !password) return;
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  errorEl.textContent = '';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else {
      errorEl.textContent = 'Incorrect username or password.';
      passwordEl.value = '';
      usernameEl.select();
    }
  } catch (e) {
    clearTimeout(timer);
    errorEl.textContent = e.name === 'AbortError'
      ? 'Request timed out. Try again.'
      : 'Something went wrong. Try again.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }
}

btn.addEventListener('click', login);
[usernameEl, passwordEl].forEach(el => {
  el.addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
});

document.getElementById('demo-btn').addEventListener('click', async function() {
  const demoBtn = this;
  demoBtn.disabled = true;
  demoBtn.textContent = 'Loading demo…';
  errorEl.textContent = '';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch('/api/auth/demo', { signal: controller.signal });
    clearTimeout(timer);
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else {
      errorEl.textContent = 'Demo is unavailable right now.';
    }
  } catch (e) {
    clearTimeout(timer);
    errorEl.textContent = e.name === 'AbortError'
      ? 'Request timed out. Try again.'
      : 'Something went wrong. Try again.';
  } finally {
    demoBtn.disabled = false;
    demoBtn.textContent = 'Try Demo';
  }
});
