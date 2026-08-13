checkAuth();

const exerciseId = window.location.pathname.split('/').filter(Boolean).pop();

let currentView = 'weight';
let chartData = {};
let info = null;
let allMuscleGroups = [];
let editing = false;
let detailEditMgIds = new Set();

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function equipmentOptions(current) {
  const values = [
    'assisted', 'band', 'barbell', 'body weight', 'bosu ball', 'cable',
    'dumbbell', 'elliptical machine', 'ez barbell', 'hammer', 'kettlebell',
    'leverage machine', 'medicine ball', 'olympic barbell', 'resistance band',
    'roller', 'rope', 'skierg machine', 'sled machine', 'smith machine',
    'stability ball', 'stationary bike', 'stepmill machine', 'tire', 'trap bar',
    'upper body ergometer', 'weighted', 'wheel roller',
  ];
  return `<option value=""${current === '' ? ' selected' : ''}>— none —</option>` +
    values.map(v => `<option value="${v}"${v === current ? ' selected' : ''}>${v}</option>`).join('');
}

function renderViewHeader() {
  const tags = [];
  if (info.equipment) tags.push(`<span class="tag tag-equipment">${escHtml(info.equipment)}</span>`);
  for (const mg of info.muscle_groups) tags.push(`<span class="tag tag-muscle">${escHtml(mg.name)}</span>`);

  const instructionsHtml = info.instructions
    ? `<details>
        <summary>How to perform</summary>
        <p class="instructions-text">${escHtml(info.instructions)}</p>
      </details>`
    : '';

  const canEdit = !isDemo() && (isAdmin() || info.user_id === getCurrentUserId());
  return `<div class="ex-title-row">
    <h1>${escHtml(info.name)}</h1>
    ${canEdit ? '<button class="btn-edit" onclick="openEditDetail()">Edit</button>' : ''}
  </div>
  <div class="tags">${tags.join('')}</div>
  ${instructionsHtml}`;
}

function renderEditHeader() {
  return `
    <label class="edit-label">Name</label>
    <input id="detail-edit-name" class="edit-input" value="${escHtml(info.name)}" autocomplete="off" />

    <label class="edit-label">Equipment</label>
    <select id="detail-edit-equipment" class="edit-input">
      ${equipmentOptions(info.equipment || '')}
    </select>

    <label class="edit-label">Instructions</label>
    <textarea id="detail-edit-instructions" class="edit-textarea" rows="4" placeholder="How to perform this exercise…">${escHtml(info.instructions || '')}</textarea>

    <label class="edit-label">Muscle Groups</label>
    <div class="filter-wrap" id="detail-mg-wrap">
      <button class="filter-trigger" id="detail-mg-trigger" onclick="toggleDetailMgPanel()">Muscle Groups ▾</button>
      <div class="filter-panel" id="detail-mg-panel">
        <input class="filter-search" placeholder="Search muscles…" oninput="renderDetailMgOptions(this.value)" />
        <div class="filter-list" id="detail-mg-list"></div>
      </div>
    </div>

    <p class="edit-error" id="detail-edit-error" style="display:none"></p>

    <div class="edit-actions">
      <button class="btn-cancel-edit" onclick="closeEditDetail()">Cancel</button>
      <button class="btn-save" id="detail-save-btn" onclick="saveEditDetail()">Save</button>
    </div>`;
}

async function load() {
  const [infoRes, progRes, mgRes] = await Promise.all([
    authFetch(`/api/exercise/${exerciseId}/info`),
    authFetch(`/api/exercise/${exerciseId}/progression`),
    authFetch('/api/muscle-groups'),
  ]);

  if (!infoRes.ok) {
    document.getElementById('loading').textContent = 'Exercise not found.';
    return;
  }
  if (!progRes.ok) {
    document.getElementById('loading').textContent = 'Failed to load progression data.';
    return;
  }

  info = await infoRes.json();
  const prog = await progRes.json();
  if (mgRes.ok) allMuscleGroups = await mgRes.json();

  document.title = `${info.name} — GymLog`;
  document.getElementById('loading').style.display = 'none';
  document.getElementById('content').style.display = 'block';

  document.getElementById('ex-header').innerHTML = renderViewHeader();

  renderSessions(prog.sessions);
}

function openEditDetail() {
  editing = true;
  detailEditMgIds = new Set(info.muscle_groups.map(mg => mg.id));
  document.getElementById('ex-header').innerHTML = renderEditHeader();
  renderDetailMgOptions('');
  updateDetailMgTrigger();
}

function closeEditDetail() {
  editing = false;
  detailEditMgIds = new Set();
  document.getElementById('ex-header').innerHTML = renderViewHeader();
}

async function saveEditDetail() {
  const name = document.getElementById('detail-edit-name').value.trim();
  const equipment = document.getElementById('detail-edit-equipment').value || null;
  const instructions = document.getElementById('detail-edit-instructions').value.trim() || null;
  const muscle_group_ids = [...detailEditMgIds];

  const errEl = document.getElementById('detail-edit-error');
  if (!name) {
    errEl.textContent = 'Name is required';
    errEl.style.display = 'block';
    return;
  }
  errEl.style.display = 'none';

  const saveBtn = document.getElementById('detail-save-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';

  try {
    const res = await authFetch(`/api/exercise/${exerciseId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, equipment, instructions, muscle_group_ids }),
    });

    if (res.ok) {
      info = await res.json();
      document.title = `${info.name} — GymLog`;
      closeEditDetail();
    } else if (res.status === 409) {
      errEl.textContent = 'An exercise with that name already exists';
      errEl.style.display = 'block';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    } else {
      errEl.textContent = 'Something went wrong, please try again';
      errEl.style.display = 'block';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  } catch {
    errEl.textContent = 'Something went wrong, please try again';
    errEl.style.display = 'block';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save';
  }
}

function toggleDetailMgPanel() {
  const panel = document.getElementById('detail-mg-panel');
  const isOpen = panel.classList.contains('open');
  document.querySelectorAll('.filter-panel.open').forEach(p => p.classList.remove('open'));
  if (!isOpen) panel.classList.add('open');
}

function renderDetailMgOptions(query) {
  const list = document.getElementById('detail-mg-list');
  const q = query.toLowerCase();
  const filtered = q
    ? allMuscleGroups.filter(mg => mg.name.toLowerCase().includes(q))
    : allMuscleGroups;
  if (!filtered.length) {
    list.innerHTML = '<div class="filter-empty">No matches</div>';
    return;
  }
  list.innerHTML = filtered.map(mg => {
    const checked = detailEditMgIds.has(mg.id);
    return `<label class="filter-option${checked ? ' checked' : ''}">
      <input type="checkbox" ${checked ? 'checked' : ''} onchange="toggleDetailMgOption(${mg.id}, this.checked)" />
      ${escHtml(mg.name)}
    </label>`;
  }).join('');
}

function toggleDetailMgOption(mgId, checked) {
  if (checked) detailEditMgIds.add(mgId);
  else detailEditMgIds.delete(mgId);
  updateDetailMgTrigger();
  const searchInput = document.querySelector('#detail-mg-panel .filter-search');
  renderDetailMgOptions(searchInput ? searchInput.value : '');
}

function updateDetailMgTrigger() {
  const btn = document.getElementById('detail-mg-trigger');
  if (!btn) return;
  const count = detailEditMgIds.size;
  btn.textContent = count === 0
    ? 'Muscle Groups ▾'
    : `${count} muscle group${count !== 1 ? 's' : ''} ▾`;
  btn.classList.toggle('active', count > 0);
}

function renderSessions(sessions) {
  const container = document.getElementById('sessions');

  if (sessions.length === 0) {
    container.innerHTML = '<div class="empty-state">No workouts logged for this exercise yet.</div>';
    return;
  }

  const weightSessions = sessions.filter(s => s.best_set_weight != null);
  let prSessionId = null;
  if (weightSessions.length > 0) {
    const prSession = weightSessions.reduce((best, s) =>
      s.best_set_weight > best.best_set_weight ? s : best
    );
    prSessionId = prSession.session_id;
    const prDate = new Date(prSession.logged_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
    document.getElementById('pr-value').textContent = `${prSession.best_set_weight} lbs — ${prDate}`;
    document.getElementById('pr-banner').style.display = 'flex';
  }

  const dateLabel = s => new Date(s.logged_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const weightPoints = weightSessions.map(s => ({ value: s.best_set_weight, date: dateLabel(s) }));
  const prIdx = prSessionId != null
    ? weightSessions.findIndex(s => s.session_id === prSessionId)
    : undefined;

  const volumeSessions = sessions.filter(s => s.volume != null);
  const volumePoints = volumeSessions.map(s => ({ value: s.volume, date: dateLabel(s) }));

  const repsPoints = sessions.map(s => ({
    value: s.sets.reduce((sum, set) => sum + set.reps, 0),
    date: dateLabel(s),
  }));

  chartData = {
    weight: { points: weightPoints, title: 'Best set weight per session (lbs)', highlightIdx: prIdx },
    volume: { points: volumePoints, title: 'Volume load per session (lbs)',     highlightIdx: undefined },
    reps:   { points: repsPoints,   title: 'Total reps per session',            highlightIdx: undefined },
  };

  const availableViews = ['weight', 'volume', 'reps'].filter(v => chartData[v].points.length >= 2);

  if (availableViews.length > 0) {
    currentView = availableViews.includes('weight') ? 'weight' : availableViews[0];
    buildTabs(availableViews);
    showChart(currentView);
  }

  const sorted = [...sessions].reverse();
  container.innerHTML = sorted.map(s => {
    const isPr = s.session_id === prSessionId;
    const date = new Date(s.logged_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
    const statsHtml = [
      s.volume != null ? `<span>Vol <b>${s.volume.toLocaleString()} lbs</b></span>` : '',
      s.best_set_weight != null ? `<span>Best <b>${s.best_set_weight} lbs</b></span>` : '',
    ].filter(Boolean).join('');

    const setsHtml = s.sets.map(set => {
      const weight = set.weight_lbs != null ? `${set.weight_lbs} lbs` : 'bodyweight';
      return `<tr>
        <td>${set.set_number}</td>
        <td>${set.reps} reps</td>
        <td>${weight}</td>
      </tr>`;
    }).join('');

    return `<div class="session-card${isPr ? ' is-pr' : ''}">
      <div class="session-header">
        <span class="session-date">${date}</span>
        <div class="session-stats">
          ${isPr ? '<span class="pr-badge">PR</span>' : ''}
          ${statsHtml}
        </div>
      </div>
      <table class="sets-table">
        <thead><tr><th>Set</th><th>Reps</th><th>Weight</th></tr></thead>
        <tbody>${setsHtml}</tbody>
      </table>
    </div>`;
  }).join('');
}

function renderChart(points, title, highlightIdx) {
  if (points.length < 2) return;
  const section = document.getElementById('chart-section');
  const svg = document.getElementById('chart');
  document.getElementById('chart-title').textContent = title;
  section.style.display = 'block';

  const W = 520, H = 120;
  const padL = 40, padR = 16, padT = 12, padB = 24;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const values = points.map(p => p.value);
  const dates  = points.map(p => p.date);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const xOf = i => padL + (i / (points.length - 1)) * plotW;
  const yOf = v => padT + plotH - ((v - minV) / range) * plotH;

  const pathD = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xOf(i)} ${yOf(v)}`).join(' ');

  const dotsHtml = values.map((v, i) => {
    const isPr = i === highlightIdx;
    const show = i === 0 || i === values.length - 1 || i % Math.max(1, Math.floor(values.length / 5)) === 0;
    return `<circle cx="${xOf(i)}" cy="${yOf(v)}" r="${isPr ? 5 : 3}" fill="${isPr ? '#c9a227' : '#5a9cf5'}" />
      ${show ? `<text x="${xOf(i)}" y="${H - 4}" text-anchor="middle" font-size="9" fill="#555">${dates[i]}</text>` : ''}`;
  }).join('');

  const yLabels = `
    <text x="${padL - 4}" y="${padT + 4}" text-anchor="end" font-size="9" fill="#555">${maxV}</text>
    <text x="${padL - 4}" y="${padT + plotH}" text-anchor="end" font-size="9" fill="#555">${minV}</text>
  `;

  svg.innerHTML = `
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + plotH}" stroke="#2a2a2a" stroke-width="1"/>
    <line x1="${padL}" y1="${padT + plotH}" x2="${padL + plotW}" y2="${padT + plotH}" stroke="#2a2a2a" stroke-width="1"/>
    ${yLabels}
    <path d="${pathD}" fill="none" stroke="#5a9cf5" stroke-width="2" stroke-linejoin="round"/>
    ${dotsHtml}
  `;
}

function showChart(view) {
  currentView = view;
  document.querySelectorAll('.chart-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
  const d = chartData[view];
  if (!d || d.points.length < 2) return;
  renderChart(d.points, d.title, d.highlightIdx);
}

function buildTabs(views) {
  const tabsEl = document.getElementById('chart-tabs');
  if (views.length <= 1) {
    tabsEl.innerHTML = '';
    return;
  }
  const labels = { weight: 'Weight', volume: 'Volume', reps: 'Reps' };
  tabsEl.innerHTML = views.map(v =>
    `<button class="chart-tab${v === currentView ? ' active' : ''}" data-view="${v}" onclick="showChart('${v}')">${labels[v]}</button>`
  ).join('');
}

load();
