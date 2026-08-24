checkAuth();
if (!isDemo()) document.getElementById('nav-import').style.display = '';

let recentSessions = [];
let dateMap = {};
let viewYear, viewMonth;

function toLocalKey(isoString) {
  const d = new Date(isoString);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function handleDayClick(event, key) {
  const sessions = dateMap[key];
  if (!sessions || sessions.length === 0) return;

  if (sessions.length === 1) {
    window.location.href = `/workout/${sessions[0].session_id}`;
    return;
  }

  const picker = document.getElementById('day-picker');
  const rect = event.currentTarget.getBoundingClientRect();

  const dateLabel = new Date(sessions[0].logged_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric',
  });

  picker.innerHTML = `
    <div class="day-picker-header">${dateLabel} — ${sessions.length} workouts</div>
    ${sessions.map((s, i) => {
      const time = new Date(s.logged_at).toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit',
      });
      const exLabel = `${s.exercises_logged} exercise${s.exercises_logged !== 1 ? 's' : ''}`;
      return `<a class="day-picker-item" href="/workout/${s.session_id}">
        Workout ${i + 1} · ${time}
        <span>${exLabel}</span>
      </a>`;
    }).join('')}
  `;

  const top = rect.bottom + window.scrollY + 6;
  let left = rect.left + window.scrollX;
  picker.style.top = `${top}px`;
  picker.style.left = `${left}px`;
  picker.classList.add('open');

  event.stopPropagation();
}

async function loadCalendar(year, month) {
  viewYear = year;
  viewMonth = month;

  const MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
  document.getElementById('cal-month-label').textContent = `${MONTHS[month]} ${year}`;

  const res = await authFetch(`/api/workouts?year=${year}&month=${month + 1}`);
  const sessions = await res.json();

  dateMap = {};
  for (const s of sessions) {
    const key = toLocalKey(s.logged_at);
    if (!dateMap[key]) dateMap[key] = [];
    dateMap[key].push(s);
  }

  const today = new Date();
  const todayKey = toLocalKey(today.toISOString());

  const firstDay = new Date(year, month, 1);
  const lastDay  = new Date(year, month + 1, 0);
  const startOffset = firstDay.getDay();

  const grid = document.getElementById('cal-grid');
  const DOWS = ['Su','Mo','Tu','We','Th','Fr','Sa'];
  let html = DOWS.map(d => `<div class="cal-dow">${d}</div>`).join('');

  for (let i = 0; i < startOffset; i++) {
    const d = new Date(year, month, 1 - (startOffset - i));
    html += `<div class="cal-day other-month">${d.getDate()}</div>`;
  }

  for (let day = 1; day <= lastDay.getDate(); day++) {
    const key = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const daySessions = dateMap[key];
    const isToday = key === todayKey;

    let cls = 'cal-day';
    if (isToday) cls += ' today';
    if (daySessions) cls += ' has-workout';

    const badge = daySessions && daySessions.length > 1
      ? `<span class="multi-badge">${'●'.repeat(Math.min(daySessions.length, 4))}</span>`
      : '';

    const attr = daySessions ? `data-key="${key}"` : '';
    html += `<div class="${cls}" ${attr}>${day}${badge}</div>`;
  }

  const totalCells = startOffset + lastDay.getDate();
  const remainder = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  for (let i = 1; i <= remainder; i++) {
    html += `<div class="cal-day other-month">${i}</div>`;
  }

  grid.innerHTML = html;

  grid.querySelectorAll('.cal-day.has-workout').forEach(el => {
    el.addEventListener('click', e => handleDayClick(e, el.dataset.key));
  });
}

function renderRecent() {
  const list = document.getElementById('recent-list');
  if (recentSessions.length === 0) {
    list.innerHTML = '<p style="color:#444;font-size:0.9rem;">No workouts logged yet.</p>';
    return;
  }
  list.innerHTML = recentSessions.slice(0, 12).map(s => {
    const date = new Date(s.logged_at).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    });
    const time = new Date(s.logged_at).toLocaleTimeString('en-US', {
      hour: 'numeric', minute: '2-digit',
    });
    const meta = `${s.exercises_logged} exercise${s.exercises_logged !== 1 ? 's' : ''} · ${time}`;
    return `<a class="session-row" href="/workout/${s.session_id}">
      <div>
        <div class="session-row-date">${date}</div>
        <div class="session-row-meta">${meta}</div>
      </div>
      <span class="session-row-arrow">›</span>
    </a>`;
  }).join('');
}

document.addEventListener('click', () => {
  document.getElementById('day-picker').classList.remove('open');
});

async function init() {
  const recentRes = await authFetch('/api/workouts?limit=20');
  recentSessions = await recentRes.json();
  renderRecent();

  const now = new Date();
  await loadCalendar(now.getFullYear(), now.getMonth());
}

document.getElementById('prev-btn').onclick = () => {
  if (viewMonth === 0) loadCalendar(viewYear - 1, 11);
  else loadCalendar(viewYear, viewMonth - 1);
};

document.getElementById('next-btn').onclick = () => {
  if (viewMonth === 11) loadCalendar(viewYear + 1, 0);
  else loadCalendar(viewYear, viewMonth + 1);
};

init();
