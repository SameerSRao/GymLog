checkAuth();

let allRoutines = [];
let allExercises = [];
let exerciseMap = {};

const editState = {};

async function init() {
  const [routinesRes, exRes] = await Promise.all([
    authFetch('/api/routines'),
    authFetch('/api/exercises'),
  ]);
  allRoutines = await routinesRes.json();
  allExercises = await exRes.json();
  exerciseMap = {};
  for (const ex of allExercises) exerciseMap[ex.name.toLowerCase()] = ex;
  render();
}

function render() {
  const container = document.getElementById('routine-list');
  if (allRoutines.length === 0) {
    container.innerHTML =
      '<p class="empty-state">No routines saved yet.<br>' +
      'Use the <a href="/log" style="color:#5a9cf5;text-decoration:none;">log workout page</a> to save one.</p>';
    return;
  }
  container.innerHTML = allRoutines.map(r => routineCardHTML(r)).join('');
}

function routineCardHTML(r) {
  const date = new Date(r.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
  const n = r.exercise_count;
  return `
    <div class="routine-card" id="card-${r.id}">
      <div class="routine-card-header" onclick="toggleExpand(${r.id})">
        <div>
          <div class="routine-name">${escHtml(r.name)}</div>
          <div class="routine-meta">${n} exercise${n !== 1 ? 's' : ''} · ${date}</div>
        </div>
        <span class="expand-arrow">›</span>
      </div>
      <div class="routine-body" id="body-${r.id}">
        <div id="view-${r.id}">Loading…</div>
      </div>
    </div>`;
}

async function toggleExpand(id) {
  const card = document.getElementById(`card-${id}`);
  const isOpen = card.classList.contains('open');

  document.querySelectorAll('.routine-card.open').forEach(c => {
    c.classList.remove('open');
  });

  if (isOpen) return;

  card.classList.add('open');
  await loadDetail(id);
}

async function loadDetail(id) {
  const viewEl = document.getElementById(`view-${id}`);
  try {
    const res = await authFetch(`/api/routine/${id}`);
    if (!res.ok) throw new Error();
    const routine = await res.json();

    const idx = allRoutines.findIndex(r => r.id === id);
    if (idx !== -1) {
      allRoutines[idx] = {
        ...allRoutines[idx],
        name: routine.name,
        exercise_count: routine.exercises.length,
        created_at: routine.created_at,
      };
    }

    viewEl.innerHTML = viewModeHTML(routine);
  } catch {
    viewEl.innerHTML = '<p style="padding:14px 16px;color:#555;font-size:0.85rem;">Failed to load.</p>';
  }
}

function viewModeHTML(routine) {
  const exercises = routine.exercises.length === 0
    ? '<p style="padding:12px 16px;color:#444;font-size:0.85rem;">No exercises in this routine.</p>'
    : routine.exercises.map(ex => `
        <div class="ex-row">
          <span class="ex-pos">${ex.position}</span>
          <span class="ex-name">${escHtml(ex.name)}</span>
          <span class="ex-sets">${ex.num_sets} set${ex.num_sets !== 1 ? 's' : ''}</span>
        </div>`).join('');

  const actionsHtml = isDemo() ? '' : `
    <div class="routine-actions">
      <button class="btn-sm" onclick="enterEdit(${routine.id})">Edit</button>
      <button class="btn-sm danger" onclick="confirmDelete(${routine.id}, '${escAttr(routine.name)}')">Delete</button>
    </div>`;
  return `
    ${exercises}
    ${actionsHtml}`;
}

async function enterEdit(id) {
  const res = await authFetch(`/api/routine/${id}`);
  if (!res.ok) { showToast('Failed to load routine', 'error'); return; }
  const routine = await res.json();

  let rowId = 0;
  editState[id] = {
    name: routine.name,
    exercises: routine.exercises.map(ex => ({
      rowId: rowId++,
      exercise_id: ex.exercise_id,
      name: ex.name,
      num_sets: ex.num_sets,
    })),
    nextRowId: rowId,
  };

  renderEditMode(id);
}

function renderEditMode(id) {
  const viewEl = document.getElementById(`view-${id}`);
  const st = editState[id];
  const n = st.exercises.length;

  const rows = st.exercises.map((ex, i) => `
    <div class="edit-ex-row" id="edit-ex-row-${id}-${ex.rowId}">
      <button class="btn-reorder" onclick="moveExUp(${id}, ${ex.rowId})" ${i === 0 ? 'disabled' : ''}>↑</button>
      <button class="btn-reorder" onclick="moveExDown(${id}, ${ex.rowId})" ${i === n - 1 ? 'disabled' : ''}>↓</button>
      <span class="edit-ex-name">${escHtml(ex.name)}</span>
      <input class="sets-input" type="number" min="1" value="${ex.num_sets}"
        onchange="updateSets(${id}, ${ex.rowId}, this.value)" />
      <span class="sets-label">sets</span>
      <button class="btn-remove" onclick="removeEditEx(${id}, ${ex.rowId})" title="Remove">✕</button>
    </div>`).join('');

  viewEl.innerHTML = `
    <div class="edit-panel">
      <span class="edit-label">Routine name</span>
      <input class="edit-input" type="text" id="edit-name-${id}" value="${escAttr(st.name)}"
        oninput="editState[${id}].name = this.value" />

      <span class="edit-label" style="margin-top:16px;">Exercises</span>
      <div id="edit-ex-list-${id}">
        ${rows}
      </div>

      <div class="add-ex-wrap" id="add-ex-wrap-${id}">
        <div class="add-ex-row">
          <input class="add-ex-search" id="add-ex-input-${id}" type="text"
            placeholder="Search exercises to add…"
            autocomplete="off"
            oninput="filterAddSearch(${id}, this.value)"
            onblur="setTimeout(() => closeAddDropdown(${id}), 150)"
            onfocus="filterAddSearch(${id}, this.value)" />
          <input class="add-ex-sets" type="number" min="1" value="3"
            id="add-ex-sets-${id}" placeholder="3" />
          <button class="btn-add-ex" onclick="addEditEx(${id})" title="Add">+</button>
        </div>
        <div class="add-ex-dropdown" id="add-ex-dd-${id}"></div>
      </div>

      <div class="edit-actions">
        <button class="btn-save" id="save-btn-${id}" onclick="saveEdit(${id})">Save</button>
        <button class="btn-cancel" onclick="cancelEdit(${id})">Cancel</button>
      </div>
    </div>`;
}

function moveExUp(id, rowId) {
  const exs = editState[id].exercises;
  const i = exs.findIndex(e => e.rowId === rowId);
  if (i <= 0) return;
  [exs[i - 1], exs[i]] = [exs[i], exs[i - 1]];
  renderEditMode(id);
}

function moveExDown(id, rowId) {
  const exs = editState[id].exercises;
  const i = exs.findIndex(e => e.rowId === rowId);
  if (i < 0 || i >= exs.length - 1) return;
  [exs[i], exs[i + 1]] = [exs[i + 1], exs[i]];
  renderEditMode(id);
}

function updateSets(id, rowId, val) {
  const ex = editState[id].exercises.find(e => e.rowId === rowId);
  if (ex) ex.num_sets = parseInt(val) || 1;
}

function removeEditEx(id, rowId) {
  editState[id].exercises = editState[id].exercises.filter(e => e.rowId !== rowId);
  renderEditMode(id);
}

const addExPending = {};

function filterAddSearch(id, query) {
  addExPending[id] = null;
  const dd = document.getElementById(`add-ex-dd-${id}`);
  const q = query.toLowerCase().trim();
  const matches = allExercises
    .filter(ex => !q || ex.name.toLowerCase().includes(q))
    .slice(0, 40);

  if (matches.length === 0) {
    dd.innerHTML = '<div class="add-ex-empty">No exercises found</div>';
  } else {
    dd.innerHTML = matches.map(ex => {
      const meta = [ex.equipment, ex.muscle_groups.slice(0, 2).map(m => m.name).join(', ')]
        .filter(Boolean).join(' · ');
      return `<div class="add-ex-item"
          onmousedown="selectAddEx(${id}, ${ex.id}, '${escAttr(ex.name)}')">
          ${escHtml(ex.name)}
          <div class="item-meta">${escHtml(meta)}</div>
        </div>`;
    }).join('');
  }
  dd.classList.add('open');
}

function selectAddEx(id, exerciseId, name) {
  addExPending[id] = { exercise_id: exerciseId, name };
  const inp = document.getElementById(`add-ex-input-${id}`);
  if (inp) inp.value = name;
  closeAddDropdown(id);
}

function closeAddDropdown(id) {
  const dd = document.getElementById(`add-ex-dd-${id}`);
  if (dd) dd.classList.remove('open');
}

function addEditEx(id) {
  const pending = addExPending[id];
  if (!pending) {
    showToast('Select an exercise from the list first', 'error');
    return;
  }
  const setsInput = document.getElementById(`add-ex-sets-${id}`);
  const numSets = parseInt(setsInput.value) || 3;
  const st = editState[id];
  st.exercises.push({
    rowId: st.nextRowId++,
    exercise_id: pending.exercise_id,
    name: pending.name,
    num_sets: numSets,
  });
  addExPending[id] = null;
  renderEditMode(id);
}

async function saveEdit(id) {
  const st = editState[id];
  const name = st.name.trim();
  if (!name) { showToast('Routine name cannot be empty', 'error'); return; }

  const btn = document.getElementById(`save-btn-${id}`);
  btn.disabled = true;
  btn.textContent = 'Saving…';

  const payload = {
    name,
    exercises: st.exercises.map((ex, i) => ({
      exercise_id: ex.exercise_id,
      position: i + 1,
      num_sets: ex.num_sets,
    })),
  };

  try {
    const res = await authFetch(`/api/routine/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.status === 409) {
      showToast(`A routine named "${name}" already exists`, 'error');
      return;
    }
    if (!res.ok) throw new Error();

    showToast(`"${name}" updated`, 'success');
    delete editState[id];

    const updated = await authFetch(`/api/routine/${id}`).then(r => r.json());
    const idx = allRoutines.findIndex(r => r.id === id);
    if (idx !== -1) {
      allRoutines[idx] = {
        id: updated.id,
        name: updated.name,
        exercise_count: updated.exercises.length,
        created_at: updated.created_at,
      };
    }

    const card = document.getElementById(`card-${id}`);
    const nameEl = card.querySelector('.routine-name');
    const metaEl = card.querySelector('.routine-meta');
    const n = updated.exercises.length;
    const date = new Date(updated.created_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
    if (nameEl) nameEl.textContent = updated.name;
    if (metaEl) metaEl.textContent =
      `${n} exercise${n !== 1 ? 's' : ''} · ${date}`;

    const viewEl = document.getElementById(`view-${id}`);
    if (viewEl) viewEl.innerHTML = viewModeHTML(updated);

  } catch {
    showToast('Failed to save routine', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
  }
}

async function cancelEdit(id) {
  delete editState[id];
  await loadDetail(id);
}

let pendingDeleteId = null;

function confirmDelete(id, name) {
  pendingDeleteId = id;
  document.getElementById('confirm-msg').textContent =
    `"${name}" will be permanently deleted.`;
  document.getElementById('confirm-overlay').classList.add('open');
  document.getElementById('confirm-yes').onclick = executeDelete;
}

function closeConfirm() {
  pendingDeleteId = null;
  document.getElementById('confirm-overlay').classList.remove('open');
}

async function executeDelete() {
  const id = pendingDeleteId;
  closeConfirm();
  if (!id) return;

  try {
    const res = await authFetch(`/api/routine/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error();

    allRoutines = allRoutines.filter(r => r.id !== id);
    const card = document.getElementById(`card-${id}`);
    if (card) card.remove();
    if (allRoutines.length === 0) render();
    showToast('Routine deleted', 'success');
  } catch {
    showToast('Failed to delete routine', 'error');
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = type;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escAttr(str) {
  return String(str).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

document.addEventListener('click', e => {
  if (!e.target.closest('.add-ex-wrap')) {
    document.querySelectorAll('.add-ex-dropdown.open')
      .forEach(dd => dd.classList.remove('open'));
  }
});

document.getElementById('confirm-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('confirm-overlay')) closeConfirm();
});

init();
