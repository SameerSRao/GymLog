if (localStorage.getItem('access_token')) {
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
  errorEl.textContent = '';
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else {
      errorEl.textContent = 'Incorrect username or password.';
      passwordEl.value = '';
      usernameEl.select();
    }
  } catch {
    errorEl.textContent = 'Something went wrong. Try again.';
  } finally {
    btn.disabled = false;
  }
}

btn.addEventListener('click', login);
[usernameEl, passwordEl].forEach(el => {
  el.addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
});

document.getElementById('demo-btn').addEventListener('click', async function() {
  errorEl.textContent = '';
  try {
    const res = await fetch('/api/auth/demo');
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else {
      errorEl.textContent = 'Demo is unavailable right now.';
    }
  } catch {
    errorEl.textContent = 'Something went wrong. Try again.';
  }
});
