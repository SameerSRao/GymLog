checkAuth();

let allExercises = [];
let muscleGroups = [];
let equipmentValues = [];
const selectedMuscles = new Set();
const selectedEquipment = new Set();
let activeEditId = null;
let editMuscleGroupIds = new Set();
let pendingDeleteId = null;

const MAX_UNFILTERED = 60;

async function init() {
  try {
    const [exRes, mgRes] = await Promise.all([
      authFetch('/api/exercises'),
      authFetch('/api/muscle-groups'),
    ]);
    if (!exRes.ok || !mgRes.ok) throw new Error('Failed to load');
    allExercises = await exRes.json();
    muscleGroups = await mgRes.json();
    equipmentValues = [...new Set(allExercises.map(e => e.equipment).filter(Boolean))].sort();

    document.getElementById('loading').style.display = 'none';
    document.getElementById('browser').style.display = 'block';
    filter();
  } catch (e) {
    document.getElementById('loading').textContent = 'Failed to load exercises.';
  }
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function canEditExercise(ex) {
  if (isDemo()) return false;
  return isAdmin() || (ex.user_id !== null && ex.user_id === getCurrentUserId());
}

function renderRow(ex) {
  const equipTag = ex.equipment
    ? `<span class="tag tag-equipment">${escHtml(ex.equipment)}</span>`
    : '';
  const muscleTags = ex.muscle_groups.slice(0, 3)
    .map(mg => `<span class="tag tag-muscle">${escHtml(mg.name)}</span>`)
    .join('');
  const actions = canEditExercise(ex)
    ? `<div class="ex-row-actions">
        <button class="btn-edit" onclick="openEdit(${ex.id})">Edit</button>
        <button class="btn-delete-row" onclick="confirmDeleteExercise(${ex.id})">Delete</button>
      </div>`
    : '';
  return `<div class="ex-row" id="row-${ex.id}">
    <div class="ex-row-main">
      <a class="ex-row-link" href="/exercise/${ex.id}">
        <div class="ex-row-name">${escHtml(ex.name)}</div>
        <div class="ex-row-tags">${equipTag}${muscleTags}</div>
      </a>
      ${actions}
    </div>
  </div>`;
}

function filter() {
  const query = document.getElementById('search').value;
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  const isFiltered = tokens.length > 0 || selectedMuscles.size > 0 || selectedEquipment.size > 0;

  const matches = allExercises.filter(ex => {
    const name = ex.name.toLowerCase();
    if (tokens.length && !tokens.every(t => name.includes(t))) return false;
    if (selectedMuscles.size && !ex.muscle_groups.some(mg => selectedMuscles.has(mg.name))) return false;
    if (selectedEquipment.size && !selectedEquipment.has(ex.equipment)) return false;
    return true;
  });

  const toShow = isFiltered ? matches : matches.slice(0, MAX_UNFILTERED);

  const meta = document.getElementById('results-meta');
  if (!isFiltered && matches.length > MAX_UNFILTERED) {
    meta.textContent = `Showing ${MAX_UNFILTERED} of ${matches.length} — search or filter to see more`;
  } else {
    meta.textContent = `${matches.length} exercise${matches.length !== 1 ? 's' : ''}`;
  }

  const container = document.getElementById('results');
  if (toShow.length === 0) {
    container.innerHTML = '<div class="empty-state">No exercises found.</div>';
    return;
  }

  activeEditId = null;
  editMuscleGroupIds = new Set();

  container.innerHTML = toShow.map(ex => renderRow(ex)).join('');
}

function toggleFilter(type) {
  const panel = document.getElementById(`filter-panel-${type}`);
  const isOpen = panel.classList.contains('open');
  closeAllFilters();
  if (!isOpen) {
    panel.classList.add('open');
    renderFilterOptions(type, '');
    panel.querySelector('.filter-search').focus();
  }
}

function closeAllFilters() {
  document.querySelectorAll('.filter-panel.open').forEach(p => p.classList.remove('open'));
}

function renderFilterOptions(type, query) {
  const selected = type === 'muscle' ? selectedMuscles : selectedEquipment;
  const allOpts = type === 'muscle' ? muscleGroups.map(mg => mg.name) : equipmentValues;
  const q = query.toLowerCase();
  const opts = q ? allOpts.filter(o => o.toLowerCase().includes(q)) : allOpts;

  const listEl = document.getElementById(`filter-list-${type}`);
  if (opts.length === 0) {
    listEl.innerHTML = '<div class="filter-empty">No results</div>';
    return;
  }
  listEl.innerHTML = opts.map(opt => {
    const checked = selected.has(opt);
    const escaped = opt.replace(/'/g, "\\'");
    return `<label class="filter-option ${checked ? 'checked' : ''}">
      <input type="checkbox" ${checked ? 'checked' : ''}
        onchange="toggleOption('${type}','${escaped}',this.checked)" />
      ${opt}
    </label>`;
  }).join('');
}

function toggleOption(type, value, checked) {
  const set = type === 'muscle' ? selectedMuscles : selectedEquipment;
  checked ? set.add(value) : set.delete(value);
  updateFilterTrigger(type);
  filter();
  const searchInput = document.querySelector(`#filter-panel-${type} .filter-search`);
  renderFilterOptions(type, searchInput ? searchInput.value : '');
}

function updateFilterTrigger(type) {
  const set = type === 'muscle' ? selectedMuscles : selectedEquipment;
  const btn = document.getElementById(`filter-trigger-${type}`);
  const label = type === 'muscle' ? 'Muscles' : 'Equipment';
  if (set.size === 0) {
    btn.textContent = `${label} ▾`;
    btn.classList.remove('active');
  } else if (set.size === 1) {
    btn.textContent = `${[...set][0]} ▾`;
    btn.classList.add('active');
  } else {
    btn.textContent = `${set.size} ${label.toLowerCase()} ▾`;
    btn.classList.add('active');
  }
  document.getElementById('filter-clear').style.display =
    (selectedMuscles.size > 0 || selectedEquipment.size > 0) ? 'inline-block' : 'none';
}

function clearFilters() {
  selectedMuscles.clear();
  selectedEquipment.clear();
  updateFilterTrigger('muscle');
  updateFilterTrigger('equipment');
  filter();
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

function renderEditRow(ex) {
  const nameVal = escHtml(ex.name);
  const instrVal = escHtml(ex.instructions || '');
  return `<div class="ex-row ex-row--editing" id="row-${ex.id}">
    <label class="edit-label">Name</label>
    <input id="edit-name-${ex.id}" class="edit-input" value="${nameVal}" autocomplete="off" />

    <label class="edit-label">Equipment</label>
    <select id="edit-equipment-${ex.id}" class="edit-input">
      ${equipmentOptions(ex.equipment || '')}
    </select>

    <label class="edit-label">Instructions</label>
    <textarea id="edit-instructions-${ex.id}" class="edit-textarea" rows="4" placeholder="How to perform this exercise…">${instrVal}</textarea>

    <label class="edit-label">Muscle Groups</label>
    <div class="filter-wrap" id="mg-wrap-${ex.id}">
      <button class="filter-trigger" id="mg-trigger-${ex.id}"
              onclick="toggleMgPanel(${ex.id})">Muscle Groups ▾</button>
      <div class="filter-panel" id="mg-panel-${ex.id}">
        <input class="filter-search" placeholder="Search muscles…"
               oninput="renderMgOptions(${ex.id}, this.value)" />
        <div class="filter-list" id="mg-list-${ex.id}"></div>
      </div>
    </div>

    <p class="edit-error" id="edit-error-${ex.id}" style="display:none"></p>

    <div class="edit-actions">
      <button class="btn-cancel-edit" onclick="closeEdit(${ex.id})">Cancel</button>
      <button class="btn-save" id="edit-save-${ex.id}" onclick="saveEdit(${ex.id})">Save</button>
    </div>
  </div>`;
}

function openEdit(id) {
  if (activeEditId !== null && activeEditId !== id) {
    closeEdit(activeEditId);
  }
  activeEditId = id;
  const ex = allExercises.find(e => e.id === id);
  editMuscleGroupIds = new Set(ex.muscle_groups.map(mg => mg.id));
  const rowEl = document.getElementById(`row-${id}`);
  rowEl.outerHTML = renderEditRow(ex);
  renderMgOptions(id, '');
  updateMgTrigger(id);
}

function closeEdit(id) {
  activeEditId = null;
  editMuscleGroupIds = new Set();
  const ex = allExercises.find(e => e.id === id);
  if (!ex) return;
  const rowEl = document.getElementById(`row-${id}`);
  if (rowEl) rowEl.outerHTML = renderRow(ex);
}

function toggleMgPanel(id) {
  const panel = document.getElementById(`mg-panel-${id}`);
  const isOpen = panel.classList.contains('open');
  document.querySelectorAll('.filter-panel.open').forEach(p => {
    if (p.id !== `mg-panel-${id}`) p.classList.remove('open');
  });
  if (isOpen) {
    panel.classList.remove('open');
  } else {
    panel.classList.add('open');
    renderMgOptions(id, '');
    panel.querySelector('.filter-search').focus();
  }
}

function renderMgOptions(id, query) {
  const listEl = document.getElementById(`mg-list-${id}`);
  if (!listEl) return;
  const q = query.toLowerCase();
  const opts = q ? muscleGroups.filter(mg => mg.name.toLowerCase().includes(q)) : muscleGroups;
  if (opts.length === 0) {
    listEl.innerHTML = '<div class="filter-empty">No results</div>';
    return;
  }
  listEl.innerHTML = opts.map(mg => {
    const checked = editMuscleGroupIds.has(mg.id);
    return `<label class="filter-option ${checked ? 'checked' : ''}">
      <input type="checkbox" ${checked ? 'checked' : ''}
        onchange="toggleMgOption(${id}, ${mg.id}, this.checked)" />
      ${escHtml(mg.name)}
    </label>`;
  }).join('');
}

function toggleMgOption(editId, mgId, checked) {
  checked ? editMuscleGroupIds.add(mgId) : editMuscleGroupIds.delete(mgId);
  updateMgTrigger(editId);
  const searchInput = document.querySelector(`#mg-panel-${editId} .filter-search`);
  renderMgOptions(editId, searchInput ? searchInput.value : '');
}

function updateMgTrigger(id) {
  const btn = document.getElementById(`mg-trigger-${id}`);
  if (!btn) return;
  const count = editMuscleGroupIds.size;
  if (count === 0) {
    btn.textContent = 'Muscle Groups ▾';
    btn.classList.remove('active');
  } else {
    btn.textContent = `${count} muscle group${count !== 1 ? 's' : ''} ▾`;
    btn.classList.add('active');
  }
}

async function saveEdit(id) {
  const name = document.getElementById(`edit-name-${id}`).value.trim();
  const equipment = document.getElementById(`edit-equipment-${id}`).value.trim() || null;
  const instructions = document.getElementById(`edit-instructions-${id}`).value.trim() || null;
  const muscle_group_ids = [...editMuscleGroupIds];

  const errEl = document.getElementById(`edit-error-${id}`);
  if (!name) {
    errEl.textContent = 'Name is required';
    errEl.style.display = 'block';
    return;
  }
  errEl.style.display = 'none';

  const saveBtn = document.getElementById(`edit-save-${id}`);
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';

  try {
    const res = await authFetch(`/api/exercise/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, equipment, instructions, muscle_group_ids }),
    });

    if (res.ok) {
      const updated = await res.json();
      const idx = allExercises.findIndex(e => e.id === id);
      if (idx !== -1) allExercises[idx] = updated;
      activeEditId = null;
      editMuscleGroupIds = new Set();
      const rowEl = document.getElementById(`row-${id}`);
      if (rowEl) rowEl.outerHTML = renderRow(updated);
    } else if (res.status === 409) {
      errEl.textContent = 'An exercise with that name already exists';
      errEl.style.display = 'block';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    } else {
      errEl.textContent = 'Failed to save. Try again.';
      errEl.style.display = 'block';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  } catch {
    errEl.textContent = 'Failed to save. Try again.';
    errEl.style.display = 'block';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save';
  }
}

function confirmDeleteExercise(id) {
  const ex = allExercises.find(e => e.id === id);
  pendingDeleteId = id;
  document.getElementById('confirm-delete-name').textContent = ex ? ex.name : 'this exercise';
  document.getElementById('delete-overlay').classList.add('open');
}

function closeDeleteOverlay() {
  document.getElementById('delete-overlay').classList.remove('open');
  pendingDeleteId = null;
}

async function executeDelete() {
  if (pendingDeleteId === null) return;
  const id = pendingDeleteId;
  closeDeleteOverlay();

  try {
    const res = await authFetch(`/api/exercise/${id}`, { method: 'DELETE' });

    if (res.status === 204) {
      const idx = allExercises.findIndex(e => e.id === id);
      if (idx !== -1) allExercises.splice(idx, 1);
      filter();
    } else if (res.status === 409) {
      const rowEl = document.getElementById(`row-${id}`);
      if (rowEl) {
        let msgEl = rowEl.querySelector('.delete-error-msg');
        if (!msgEl) {
          msgEl = document.createElement('p');
          msgEl.className = 'delete-error-msg';
          msgEl.style.cssText = 'font-size:0.8rem;color:#8a4a4a;padding:6px 14px 8px;margin:0';
          rowEl.appendChild(msgEl);
        }
        msgEl.textContent = "Can't delete — this exercise has logged history";
      }
    } else if (res.status === 404) {
      const idx = allExercises.findIndex(e => e.id === id);
      if (idx !== -1) allExercises.splice(idx, 1);
      filter();
    }
  } catch {
    const rowEl = document.getElementById(`row-${id}`);
    if (rowEl) {
      let msgEl = rowEl.querySelector('.delete-error-msg');
      if (!msgEl) {
        msgEl = document.createElement('p');
        msgEl.className = 'delete-error-msg';
        msgEl.style.cssText = 'font-size:0.8rem;color:#8a4a4a;padding:6px 14px 8px;margin:0';
        rowEl.appendChild(msgEl);
      }
      msgEl.textContent = 'Delete failed. Try again.';
    }
  }
}

document.addEventListener('click', e => {
  if (!e.target.closest('.filter-wrap')) closeAllFilters();
  if (e.target === document.getElementById('delete-overlay')) closeDeleteOverlay();
});

init();
