if (localStorage.getItem('access_token') && !isTokenExpired()) {
  window.location.replace('/');
}

const usernameEl = document.getElementById('username');
const passwordEl = document.getElementById('password');
const codeEl = document.getElementById('signup-code');
const btn = document.getElementById('btn');
const errorEl = document.getElementById('error');

function validateInputs(username, password) {
  if (!/^[a-zA-Z0-9_\-]{3,30}$/.test(username)) {
    return 'Username must be 3–30 characters: letters, numbers, _ or -.';
  }
  if (password.length < 3 || password.length > 72) {
    return 'Password must be 3–72 characters.';
  }
  if (!/^[\x20-\x7E]+$/.test(password)) {
    return 'Password contains invalid characters.';
  }
  return null;
}

async function register() {
  const username = usernameEl.value.trim();
  const password = passwordEl.value;
  const signup_code = codeEl.value.trim();
  if (!username || !password || !signup_code) return;
  const validationError = validateInputs(username, password);
  if (validationError) { errorEl.textContent = validationError; return; }
  btn.disabled = true;
  btn.textContent = 'Creating account…';
  errorEl.textContent = '';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, signup_code }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else if (res.status === 409) {
      errorEl.textContent = 'That username is already taken.';
      usernameEl.select();
    } else if (res.status === 400) {
      errorEl.textContent = 'Invalid signup code.';
      codeEl.value = '';
      codeEl.focus();
    } else {
      errorEl.textContent = 'Something went wrong. Try again.';
    }
  } catch (e) {
    clearTimeout(timer);
    errorEl.textContent = e.name === 'AbortError'
      ? 'Request timed out. Try again.'
      : 'Something went wrong. Try again.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create account';
  }
}

btn.addEventListener('click', register);
[usernameEl, passwordEl, codeEl].forEach(el => {
  el.addEventListener('keydown', e => { if (e.key === 'Enter') register(); });
});
