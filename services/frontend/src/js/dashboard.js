checkAuth();

if (isDemo()) {
  var demoBanner = document.createElement('div');
  demoBanner.style.cssText =
    'background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;' +
    'color:#888;font-size:0.85rem;padding:10px 14px;margin-bottom:16px;' +
    'text-align:center;';
  demoBanner.innerHTML =
    'You\'re in demo mode. ' +
    '<a href="/register" style="color:#f0f0f0;" ' +
    'onclick="logout()">Sign up</a> to log workouts.';
  document.body.prepend(demoBanner);
  var logBtn = document.querySelector('.btn-log');
  if (logBtn) logBtn.style.display = 'none';
}

if (!isPremium() && !isAdmin()) {
  var chatWindow = document.querySelector('.chat-window');
  var locked = document.createElement('div');
  locked.className = 'chat-locked';
  locked.innerHTML = '<div class="lock-icon">🔒</div><p>AI chat is available for premium members. Upgrade to unlock GymBot.</p>';
  chatWindow.parentNode.replaceChild(locked, chatWindow);
}

function toLocalKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function getWeekStart() {
  const now = new Date();
  const diff = now.getDay() === 0 ? 6 : now.getDay() - 1;
  const mon = new Date(now);
  mon.setDate(now.getDate() - diff);
  mon.setHours(0, 0, 0, 0);
  return mon;
}
async function loadStats() {
  try {
    const [countRes, recentRes] = await Promise.all([
      authFetch('/api/workouts/count'),
      authFetch('/api/workouts?limit=90'),
    ]);
    if (!countRes.ok || !recentRes.ok) return;
    const { total } = await countRes.json();
    const sessions = await recentRes.json();
    const weekStart = getWeekStart();
    const thisWeek = sessions.filter(
      s => new Date(s.logged_at) >= weekStart
    ).length;
    const loggedDates = new Set(
      sessions.map(s => toLocalKey(new Date(s.logged_at)))
    );
    let streak = 0;
    const today = new Date(); today.setHours(0,0,0,0);
    const startOffset = loggedDates.has(toLocalKey(today)) ? 0 : 1;
    for (let i = startOffset; i < 365; i++) {
      const d = new Date(today); d.setDate(today.getDate() - i);
      if (loggedDates.has(toLocalKey(d))) streak++; else break;
    }
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-week').textContent = thisWeek;
    document.getElementById('stat-streak').textContent = streak;
  } catch (_) {}
}

const CHAT_KEY = 'gymlog_chat_history';
const MAX_STORED = 40;
const history = JSON.parse(localStorage.getItem(CHAT_KEY) || '[]');

function saveHistory() {
  localStorage.setItem(CHAT_KEY, JSON.stringify(history.slice(-MAX_STORED)));
}

function appendMsg(role, text) {
  const el = document.createElement('div');
  el.className = `msg msg-${role === 'user' ? 'user' : 'bot'}`;
  el.textContent = text;
  document.getElementById('chat-messages').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return el;
}

history.forEach(m => appendMsg(m.role, m.content));

function showTyping() {
  const el = document.createElement('div');
  el.className = 'msg msg-bot';
  el.id = 'typing-indicator';
  el.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  document.getElementById('chat-messages').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return el;
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  input.style.height = '';
  appendMsg('user', text);
  history.push({ role: 'user', content: text });
  saveHistory();

  const sendBtn = document.getElementById('chat-send');
  sendBtn.disabled = true;
  const typingEl = showTyping();

  try {
    const res = await authFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history, local_time: (function(d){ return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19); })(new Date()) }),
    });

    typingEl.remove();

    if (!res.ok) {
      appendMsg('bot', 'Something went wrong. Try again.');
      sendBtn.disabled = false;
      return;
    }

    const botEl = appendMsg('bot', '');
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let botText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6);
        if (payload === '[DONE]') break;
        try {
          const parsed = JSON.parse(payload);
          if (parsed.error) {
            botEl.textContent = 'Error: ' + parsed.error;
          } else if (parsed.text) {
            botText += parsed.text;
            botEl.textContent = botText;
            botEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
          }
        } catch (_) {}
      }
    }

    if (botText) { history.push({ role: 'assistant', content: botText }); saveHistory(); }
    loadStats();
  } catch (e) {
    typingEl.remove();
    appendMsg('bot', 'Connection error. Try again.');
  }

  sendBtn.disabled = false;
  input.focus();
}

document.getElementById('chat-send').addEventListener('click', sendMessage);
document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
document.getElementById('chat-input').addEventListener('input', function () {
  this.style.height = '';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

loadStats();
appendMsg('bot', 'Hey! I\'m GymBot. I can log workouts, check your progress, or search exercises. What\'s up?');
