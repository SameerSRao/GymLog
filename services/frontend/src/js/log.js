checkAuth();

if (isDemo()) { window.location.replace('/workouts'); }

function localISOString() {
  const d = new Date();
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
}

(function () {
  const el = document.getElementById('workout-date-input');
  if (el) el.value = localISOString().slice(0, 10);
})();

let allExercises = [];
let exerciseMap = {};
let muscleGroups = [];
let equipmentValues = [];
let allRoutines = [];
const blockFilters = {};

function getBlockFilter(id) {
  if (!blockFilters[id]) blockFilters[id] = { muscles: new Set(), equipment: new Set() };
  return blockFilters[id];
}

const EQUIPMENT_LIST = [
  'assisted','band','barbell','body weight','bosu ball','cable','dumbbell',
  'elliptical machine','ez barbell','hammer','kettlebell','leverage machine',
  'medicine ball','olympic barbell','resistance band','roller','rope',
  'skierg machine','sled machine','smith machine','stability ball',
  'stationary bike','stepmill machine','tire','trap bar',
  'upper body ergometer','weighted','wheel roller'
];

let exerciseCount = 0;

async function init() {
  try {
    const [exRes, mgRes] = await Promise.all([authFetch('/api/exercises'), authFetch('/api/muscle-groups')]);
    allExercises = await exRes.json();
    muscleGroups = await mgRes.json();

    exerciseMap = {};
    for (const ex of allExercises) exerciseMap[ex.name.toLowerCase()] = ex;

    equipmentValues = [...new Set(allExercises.map(e => e.equipment).filter(Boolean))].sort();

    const eqSelect = document.getElementById('new-ex-equipment');
    eqSelect.innerHTML = '<option value="">— none / unknown —</option>' +
      EQUIPMENT_LIST.map(e => `<option value="${e}">${e}</option>`).join('');

    document.getElementById('mg-checkboxes').innerHTML = muscleGroups.map(mg =>
      `<label class="mg-checkbox-label">
        <input type="checkbox" name="mg" value="${mg.id}" /> ${mg.name}
      </label>`
    ).join('');

  } catch (e) {
    console.error('Failed to load exercises', e);
  }

  try {
    const res = await authFetch('/api/routines');
    allRoutines = await res.json();
    if (allRoutines.length > 0) {
      const sel = document.getElementById('routine-select');
      sel.innerHTML = '<option value="">Load Routine…</option>' +
        allRoutines.map(r => {
          const n = r.exercise_count;
          return `<option value="${r.id}">${r.name} (${n} exercise${n !== 1 ? 's' : ''})</option>`;
        }).join('');
      document.getElementById('routine-loader').style.display = 'block';
    }
  } catch (e) {
    console.error('Failed to load routines', e);
  }

  addExercise();
}

function openDropdown(id) {
  closeAllDropdowns();
  const dd = document.getElementById(`dd-${id}`);
  dd.classList.add('open');
  filterDropdown(id, document.getElementById(`name-${id}`).value);
}

function closeAllDropdowns() {
  document.querySelectorAll('.ex-dropdown.open').forEach(el => el.classList.remove('open'));
}

function toggleMs(type, id) {
  const panel = document.getElementById(`ms-${type}-panel-${id}`);
  const isOpen = panel.classList.contains('open');
  closeAllMs();
  closeAllDropdowns();
  if (!isOpen) {
    panel.classList.add('open');
    renderMsOptions(type, id, '');
    panel.querySelector('.ms-search').focus();
  }
}

function closeAllMs() {
  document.querySelectorAll('.ms-panel.open').forEach(p => p.classList.remove('open'));
}

function renderMsOptions(type, id, query) {
  const f = getBlockFilter(id);
  const selected = type === 'muscle' ? f.muscles : f.equipment;
  const allOpts = type === 'muscle'
    ? muscleGroups.map(mg => mg.name)
    : equipmentValues;
  const q = query.toLowerCase();
  const opts = q ? allOpts.filter(o => o.includes(q)) : allOpts;

  const listEl = document.getElementById(`ms-${type}-list-${id}`);
  if (opts.length === 0) {
    listEl.innerHTML = '<div class="ms-empty">No results</div>';
    return;
  }
  listEl.innerHTML = opts.map(opt => {
    const checked = selected.has(opt);
    return `<label class="ms-option ${checked ? 'checked' : ''}">
      <input type="checkbox" ${checked ? 'checked' : ''}
        onchange="toggleMsOption('${type}',${id},'${opt.replace(/'/g,"\\'")}',this.checked)" />
      ${opt}
    </label>`;
  }).join('');
}

function toggleMsOption(type, id, value, checked) {
  const f = getBlockFilter(id);
  const set = type === 'muscle' ? f.muscles : f.equipment;
  checked ? set.add(value) : set.delete(value);
  updateMsTrigger(type, id);
  filterDropdown(id, document.getElementById(`name-${id}`).value);
  const searchInput = document.querySelector(`#ms-${type}-panel-${id} .ms-search`);
  renderMsOptions(type, id, searchInput ? searchInput.value : '');
}

function updateMsTrigger(type, id) {
  const f = getBlockFilter(id);
  const set = type === 'muscle' ? f.muscles : f.equipment;
  const btn = document.getElementById(`ms-${type}-btn-${id}`);
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
  const clearBtn = document.getElementById(`ms-clear-${id}`);
  if (clearBtn) {
    const hasAny = f.muscles.size > 0 || f.equipment.size > 0;
    clearBtn.style.display = hasAny ? 'block' : 'none';
  }
}

function clearBlockFilters(id) {
  const f = getBlockFilter(id);
  f.muscles.clear();
  f.equipment.clear();
  updateMsTrigger('muscle', id);
  updateMsTrigger('equip', id);
  filterDropdown(id, document.getElementById(`name-${id}`).value);
}

function filterDropdown(id, query) {
  const dd = document.getElementById(`dd-${id}`);
  const f = getBlockFilter(id);
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);

  const matches = allExercises.filter(ex => {
    const name = ex.name.toLowerCase();
    if (tokens.length && !tokens.every(t => name.includes(t))) return false;
    if (f.muscles.size && !ex.muscle_groups.some(mg => f.muscles.has(mg.name))) return false;
    if (f.equipment.size && !f.equipment.has(ex.equipment)) return false;
    return true;
  }).slice(0, 60);

  if (matches.length === 0) {
    dd.innerHTML = '<div class="ex-dropdown-empty">No exercises found</div>';
    return;
  }

  dd.innerHTML = matches.map(ex => {
    const muscles = ex.muscle_groups.slice(0, 3).map(m => m.name).join(', ');
    const equip = ex.equipment || '';
    return `<div class="ex-dropdown-item" onmousedown="selectExercise(${id}, '${ex.name.replace(/'/g, "\\'")}')">
      ${ex.name}
      <div class="item-meta">${[equip, muscles].filter(Boolean).join(' · ')}</div>
    </div>`;
  }).join('');
}

function selectExercise(id, name) {
  const input = document.getElementById(`name-${id}`);
  input.value = name;
  const ex = exerciseMap[name.toLowerCase()];
  input.dataset.exerciseId = ex ? ex.id : '';
  closeAllDropdowns();
  updateExerciseMeta(id, name);
}

function updateExerciseMeta(id, name) {
  const ex = exerciseMap[name.toLowerCase()];
  const input = document.getElementById(`name-${id}`);
  if (!ex) input.dataset.exerciseId = '';
  const metaDiv = document.getElementById(`ex-meta-${id}`);
  if (ex) {
    const equip = ex.equipment ? `<span class="equipment-tag">${ex.equipment}</span>` : '';
    const tags = ex.muscle_groups.map(mg => `<span class="muscle-tag">${mg.name}</span>`).join('');
    const link = `<a href="/exercise/${ex.id}" style="margin-left:auto;font-size:0.75rem;color:#555;text-decoration:none;" target="_blank">view ↗</a>`;
    metaDiv.innerHTML = equip + tags + link;
  } else {
    metaDiv.innerHTML = '';
  }
}

function updateSaveRoutineBtn() {
  const hasBlocks =
    document.querySelectorAll('#exercises .exercise-block').length > 0;
  document.getElementById('saveRoutineBtn').style.display =
    hasBlocks ? 'block' : 'none';
}

function addExercise() {
  const id = exerciseCount++;
  const div = document.createElement('div');
  div.className = 'exercise-block';
  div.id = `exercise-${id}`;
  div.innerHTML = `
    <div class="exercise-header">
      <span>Exercise ${id + 1}</span>
      <button class="btn-icon" onclick="removeExercise(${id})" title="Remove">✕</button>
    </div>
    <label>Exercise</label>
    <div class="ex-select-wrap">
      <input type="text" id="name-${id}" placeholder="Search exercises..."
             autocomplete="off"
             onfocus="openDropdown(${id})"
             oninput="filterDropdown(${id}, this.value); updateExerciseMeta(${id}, this.value)"
             onblur="setTimeout(() => closeAllDropdowns(), 150)" />
      <div class="ex-dropdown" id="dd-${id}"></div>
    </div>
    <div class="ms-row">
      <div class="ms-wrap">
        <button class="ms-trigger" id="ms-muscle-btn-${id}" onclick="toggleMs('muscle',${id})">Muscles ▾</button>
        <div class="ms-panel" id="ms-muscle-panel-${id}">
          <input class="ms-search" placeholder="Search muscles…" oninput="renderMsOptions('muscle',${id},this.value)" />
          <div class="ms-list" id="ms-muscle-list-${id}"></div>
        </div>
      </div>
      <div class="ms-wrap">
        <button class="ms-trigger" id="ms-equip-btn-${id}" onclick="toggleMs('equip',${id})">Equipment ▾</button>
        <div class="ms-panel" id="ms-equip-panel-${id}">
          <input class="ms-search" placeholder="Search equipment…" oninput="renderMsOptions('equip',${id},this.value)" />
          <div class="ms-list" id="ms-equip-list-${id}"></div>
        </div>
      </div>
      <button class="ms-clear-btn" id="ms-clear-${id}" onclick="clearBlockFilters(${id})" style="display:none">✕</button>
    </div>
    <div id="ex-meta-${id}" class="muscle-tags"></div>
    <table class="sets-table">
      <thead><tr><th>Set</th><th>Reps</th><th>Weight (lbs)</th><th></th></tr></thead>
      <tbody id="sets-${id}"></tbody>
    </table>
    <button class="btn-add-set" onclick="addSet(${id})">+ Add Set</button>
  `;
  document.getElementById('exercises').appendChild(div);
  addSet(id);
  updateSaveRoutineBtn();
  return id;
}

function removeExercise(id) {
  document.getElementById(`exercise-${id}`).remove();
  updateSaveRoutineBtn();
}

let setCounts = {};

function addSet(exerciseId) {
  if (!setCounts[exerciseId]) setCounts[exerciseId] = 0;
  const setNum = setCounts[exerciseId]++;
  const tbody = document.getElementById(`sets-${exerciseId}`);
  const tr = document.createElement('tr');
  tr.id = `set-${exerciseId}-${setNum}`;
  tr.innerHTML = `
    <td style="color:#666;font-size:0.85rem;width:32px">${setNum + 1}</td>
    <td><input type="number" id="reps-${exerciseId}-${setNum}" placeholder="8" min="1" /></td>
    <td><input type="number" id="weight-${exerciseId}-${setNum}" placeholder="—" min="0" step="2.5" /></td>
    <td><button class="btn-icon" onclick="removeSet('${exerciseId}-${setNum}')" title="Remove">✕</button></td>
  `;
  tbody.appendChild(tr);
}

function removeSet(id) {
  document.getElementById(`set-${id}`).remove();
}

function toggleCreateForm() {
  const form = document.getElementById('create-form');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function createExercise() {
  const name = document.getElementById('new-ex-name').value.trim();
  if (!name) { showToast('Exercise name is required', 'error'); return; }

  const muscle_group_ids = [...document.querySelectorAll('#mg-checkboxes input:checked')]
    .map(cb => parseInt(cb.value));

  try {
    const res = await authFetch('/api/exercises', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, muscle_group_ids }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed');
    }
    const created = await res.json();

    allExercises.push(created);
    exerciseMap[created.name.toLowerCase()] = created;

    document.getElementById('new-ex-name').value = '';
    document.querySelectorAll('#mg-checkboxes input').forEach(cb => cb.checked = false);
    toggleCreateForm();
    showToast(`"${created.name}" added`, 'success');
  } catch (e) {
    showToast(e.message || 'Error creating exercise', 'error');
  }
}

async function onRoutineChange(sel) {
  const routineId = sel.value;
  if (!routineId) return;

  const hasFilledExercises = [...document.querySelectorAll('#exercises .exercise-block')]
    .some(block => {
      const id = block.id.replace('exercise-', '');
      const inp = document.getElementById(`name-${id}`);
      return inp && inp.value.trim().length > 0;
    });

  if (hasFilledExercises &&
      !confirm('Loading this routine will replace the current exercises. Continue?')) {
    sel.value = '';
    return;
  }

  await loadRoutine(parseInt(routineId));
  sel.value = '';
}

async function loadRoutine(routineId) {
  try {
    const res = await authFetch(`/api/routine/${routineId}`);
    if (!res.ok) throw new Error('Not found');
    const routine = await res.json();

    document.getElementById('exercises').innerHTML = '';
    exerciseCount = 0;
    setCounts = {};

    if (routine.exercises.length === 0) {
      addExercise();
      return;
    }

    for (const ex of routine.exercises) {
      const id = addExercise();
      selectExercise(id, ex.name);
      for (let i = 1; i < ex.num_sets; i++) addSet(id);
    }
    updateSaveRoutineBtn();
  } catch (e) {
    showToast('Failed to load routine', 'error');
    updateSaveRoutineBtn();
  }
}

async function saveAsRoutine() {
  const blocks = [...document.querySelectorAll('#exercises .exercise-block')];

  for (const block of blocks) {
    const id = block.id.replace('exercise-', '');
    const inp = document.getElementById(`name-${id}`);
    if (inp && inp.value.trim() && !inp.dataset.exerciseId) {
      showToast(
        'Select all exercises from the list before saving as a routine',
        'error'
      );
      return;
    }
  }

  const name = window.prompt('Routine name:');
  if (!name || !name.trim()) return;
  const trimmed = name.trim();

  const exercises = blocks.map((block, i) => {
    const id = block.id.replace('exercise-', '');
    const inp = document.getElementById(`name-${id}`);
    const numSets = document.querySelectorAll(`#sets-${id} tr`).length;
    return {
      exercise_id: parseInt(inp.dataset.exerciseId),
      position: i + 1,
      num_sets: numSets,
    };
  });

  try {
    const res = await authFetch('/api/routines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: trimmed, exercises }),
    });
    if (res.status === 409) {
      showToast(`A routine named "${trimmed}" already exists`, 'error');
      return;
    }
    if (!res.ok) throw new Error();
    showToast(`"${trimmed}" saved as routine`, 'success');
  } catch {
    showToast('Failed to save routine', 'error');
  }
}

async function submitWorkout() {
  const exerciseBlocks = document.querySelectorAll('.exercise-block:not(#create-form)');
  const exercises = [];

  for (const block of exerciseBlocks) {
    const id = block.id.replace('exercise-', '');
    const nameInput = document.getElementById(`name-${id}`);
    const name = nameInput.value.trim();
    const exercise_id = parseInt(nameInput.dataset.exerciseId || '');

    if (!name) { showToast("Exercise name can't be empty", 'error'); return; }
    if (!exercise_id) { showToast(`Select "${name}" from the list or create it first`, 'error'); return; }

    const setRows = document.querySelectorAll(`#sets-${id} tr`);
    const sets = [];

    for (const row of setRows) {
      const rowId = row.id.replace('set-', '');
      const reps = parseInt(document.getElementById(`reps-${rowId}`).value);
      const weightVal = document.getElementById(`weight-${rowId}`).value;
      const weight_lbs = weightVal ? parseFloat(weightVal) : null;

      if (!reps || reps < 1) { showToast('Each set needs a rep count', 'error'); return; }
      sets.push(weight_lbs !== null ? { reps, weight_lbs } : { reps });
    }

    if (sets.length === 0) { showToast('Add at least one set', 'error'); return; }
    exercises.push({ exercise_id, sets });
  }

  if (exercises.length === 0) { showToast('Add at least one exercise', 'error'); return; }

  const notes = document.getElementById('workout-notes-input').value.trim() || null;

  const dateVal = document.getElementById('workout-date-input').value;
  let loggedAt;
  if (dateVal) {
    loggedAt = dateVal + 'T' + localISOString().slice(11);
    if (new Date(loggedAt) > new Date()) {
      showToast('Workout date cannot be in the future', 'error');
      return;
    }
  } else {
    loggedAt = localISOString();
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Logging...';

  try {
    const res = await authFetch('/api/workouts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercises, notes, logged_at: loggedAt }),
    });
    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    showToast(`Logged! ${data.exercises_logged} exercises, ${data.sets_logged} sets`, 'success');
    document.getElementById('last-workout-link').innerHTML =
      `<a href="/workout/${data.session_id}">View workout →</a>`;
    document.getElementById('exercises').innerHTML = '';
    document.getElementById('workout-notes-input').value = '';
    document.getElementById('workout-date-input').value = localISOString().slice(0, 10);
    setCounts = {};
    exerciseCount = 0;
    addExercise();
  } catch (e) {
    showToast('Error logging workout', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Log Workout';
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = type;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

document.addEventListener('click', e => {
  if (!e.target.closest('.ex-select-wrap')) closeAllDropdowns();
  if (!e.target.closest('.ms-wrap')) closeAllMs();
});

init();
