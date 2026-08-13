checkAuth();

if (isDemo()) {
  var viewActionsEl = document.getElementById('view-actions');
  if (viewActionsEl) viewActionsEl.style.display = 'none';
}

let workout = null;
const sessionId = window.location.pathname.split('/').filter(Boolean).pop();

let allExercises = [];
let exerciseMap = {};
let muscleGroups = [];
let equipmentValues = [];
const blockFilters = {};
let exerciseCount = 0;
let setCounts = {};
let exerciseDataLoaded = false;

async function loadExerciseData() {
  if (exerciseDataLoaded) return;
  const [exRes, mgRes] = await Promise.all([
    authFetch('/api/exercises'),
    authFetch('/api/muscle-groups'),
  ]);
  allExercises = await exRes.json();
  muscleGroups = await mgRes.json();
  exerciseMap = {};
  for (const ex of allExercises) exerciseMap[ex.name.toLowerCase()] = ex;
  equipmentValues = [...new Set(allExercises.map(e => e.equipment).filter(Boolean))].sort();
  exerciseDataLoaded = true;
}

function getBlockFilter(id) {
  if (!blockFilters[id]) blockFilters[id] = { muscles: new Set(), equipment: new Set() };
  return blockFilters[id];
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
    const equip = ex.equipment ? `<span class="edit-equipment-tag">${ex.equipment}</span>` : '';
    const tags = ex.muscle_groups.map(mg => `<span class="muscle-tag">${mg.name}</span>`).join('');
    metaDiv.innerHTML = equip + tags;
  } else {
    metaDiv.innerHTML = '';
  }
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
  const allOpts = type === 'muscle' ? muscleGroups.map(mg => mg.name) : equipmentValues;
  const q = query.toLowerCase();
  const opts = q ? allOpts.filter(o => o.includes(q)) : allOpts;
  const listEl = document.getElementById(`ms-${type}-list-${id}`);
  if (opts.length === 0) { listEl.innerHTML = '<div class="ms-empty">No results</div>'; return; }
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
  if (set.size === 0) { btn.textContent = `${label} ▾`; btn.classList.remove('active'); }
  else if (set.size === 1) { btn.textContent = `${[...set][0]} ▾`; btn.classList.add('active'); }
  else { btn.textContent = `${set.size} ${label.toLowerCase()} ▾`; btn.classList.add('active'); }
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

function addExercise(prePopulate = null) {
  const id = exerciseCount++;
  const div = document.createElement('div');
  div.className = 'exercise-block';
  div.id = `edit-exercise-${id}`;
  div.innerHTML = `
    <div class="exercise-header-edit">
      <span>Exercise ${id + 1}</span>
      <button class="btn-icon-edit" onclick="removeExercise(${id})" title="Remove">✕</button>
    </div>
    <label class="edit-label">Exercise</label>
    <div class="ex-select-wrap">
      <input type="text" id="name-${id}" class="edit-input" placeholder="Search exercises..."
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
    <div id="ex-meta-${id}" class="edit-muscle-tags"></div>
    <table class="sets-table-edit">
      <thead><tr><th>Set</th><th>Reps</th><th>Weight (lbs)</th><th></th></tr></thead>
      <tbody id="sets-${id}"></tbody>
    </table>
    <button class="btn-add-set" onclick="addSet(${id})">+ Add Set</button>
  `;
  document.getElementById('edit-exercise-container').appendChild(div);

  if (prePopulate) {
    const input = document.getElementById(`name-${id}`);
    input.value = prePopulate.name;
    input.dataset.exerciseId = prePopulate.exercise_id;
    updateExerciseMeta(id, prePopulate.name);
    for (const set of prePopulate.sets) {
      addSet(id, set);
    }
  } else {
    addSet(id);
  }
}

function removeExercise(id) {
  document.getElementById(`edit-exercise-${id}`).remove();
}

function addSet(exerciseId, prePopulate = null) {
  if (!setCounts[exerciseId]) setCounts[exerciseId] = 0;
  const setNum = setCounts[exerciseId]++;
  const tbody = document.getElementById(`sets-${exerciseId}`);
  const tr = document.createElement('tr');
  tr.id = `set-${exerciseId}-${setNum}`;
  tr.innerHTML = `
    <td style="color:#666;font-size:0.85rem;width:32px">${setNum + 1}</td>
    <td><input type="number" id="reps-${exerciseId}-${setNum}" class="edit-input" placeholder="8" min="1" /></td>
    <td><input type="number" id="weight-${exerciseId}-${setNum}" class="edit-input" placeholder="—" min="0" step="2.5" /></td>
    <td><button class="btn-icon-edit" onclick="removeSet('${exerciseId}-${setNum}')" title="Remove">✕</button></td>
  `;
  tbody.appendChild(tr);
  if (prePopulate) {
    document.getElementById(`reps-${exerciseId}-${setNum}`).value = prePopulate.reps;
    if (prePopulate.weight_lbs != null) {
      document.getElementById(`weight-${exerciseId}-${setNum}`).value = prePopulate.weight_lbs;
    }
  }
}

function removeSet(id) {
  document.getElementById(`set-${id}`).remove();
}

async function load() {
  const res = await authFetch(`/api/workout/${sessionId}`);
  if (!res.ok) {
    document.getElementById('loading').textContent = 'Workout not found.';
    return;
  }
  workout = await res.json();
  renderWorkout(workout);
}

function renderWorkout(w) {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('content').style.display = 'block';

  const date = new Date(w.logged_at);
  document.title = `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} — GymLog`;
  document.getElementById('workout-date').textContent = date.toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });

  const totalSets = w.exercises.reduce((n, e) => n + e.sets.length, 0);
  document.getElementById('workout-meta').textContent =
    `${w.exercises.length} exercise${w.exercises.length !== 1 ? 's' : ''} · ${totalSets} sets`;

  const notesEl = document.getElementById('workout-notes');
  if (w.notes) {
    notesEl.textContent = w.notes;
    notesEl.style.display = 'block';
  } else {
    notesEl.style.display = 'none';
  }

  const container = document.getElementById('exercises');
  container.innerHTML = w.exercises.map(ex => {
    const progressionLink = ex.exercise_id
      ? `<a class="progression-link" href="/exercise/${ex.exercise_id}">View progression →</a>`
      : '';

    const setsHtml = ex.sets.map((s, i) => {
      const weight = s.weight_lbs != null ? `${s.weight_lbs} lbs` : 'bodyweight';
      return `<tr>
        <td>${i + 1}</td>
        <td>${s.reps} reps</td>
        <td>${weight}</td>
      </tr>`;
    }).join('');

    const weights = ex.sets.map(s => s.weight_lbs).filter(v => v != null);
    const volume = weights.length > 0
      ? ex.sets.reduce((sum, s) => sum + (s.weight_lbs != null ? s.reps * s.weight_lbs : 0), 0)
      : null;
    const bestWeight = weights.length > 0 ? Math.max(...weights) : null;

    const summaryHtml = [
      volume != null ? `<div class="summary-item">Vol <b>${volume.toLocaleString()} lbs</b></div>` : '',
      bestWeight != null ? `<div class="summary-item">Best <b>${bestWeight} lbs</b></div>` : '',
      `<div class="summary-item">Sets <b>${ex.sets.length}</b></div>`,
    ].filter(Boolean).join('');

    return `<div class="exercise-card">
      <div class="exercise-card-header">
        <div>
          <div class="exercise-name">${ex.name}</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">
            ${ex.muscle_groups.map(mg => `<span class="muscle-tag">${mg.name}</span>`).join('')}
          </div>
        </div>
        ${progressionLink}
      </div>
      <table class="sets-table">
        <thead><tr><th>Set</th><th>Reps</th><th>Weight</th></tr></thead>
        <tbody>${setsHtml}</tbody>
      </table>
      <div class="summary-row">${summaryHtml}</div>
    </div>`;
  }).join('');
}

function confirmDelete() {
  document.getElementById('confirm-overlay').classList.add('open');
}

function closeConfirm() {
  document.getElementById('confirm-overlay').classList.remove('open');
}

async function deleteWorkout() {
  const res = await authFetch(`/api/workout/${sessionId}`, { method: 'DELETE' });
  if (res.ok) window.location.href = '/workouts';
}

async function enterEditMode() {
  if (!workout) return;
  await loadExerciseData();

  document.getElementById('view-actions').style.display = 'none';
  document.getElementById('edit-actions').style.display = 'flex';

  document.getElementById('exercises').style.display = 'none';
  document.getElementById('edit-exercise-container').style.display = 'block';
  document.getElementById('edit-add-exercise-btn').style.display = 'block';

  document.getElementById('edit-exercise-container').innerHTML = '';
  exerciseCount = 0;
  setCounts = {};
  Object.keys(blockFilters).forEach(k => delete blockFilters[k]);

  for (const ex of workout.exercises) {
    addExercise({ exercise_id: ex.exercise_id, name: ex.name, sets: ex.sets });
  }

  const editNotes = document.getElementById('edit-notes');
  editNotes.value = workout.notes || '';
  editNotes.style.display = 'block';

  const dtRow = document.getElementById('edit-datetime-row');
  dtRow.style.display = 'block';
  const [datePart, timePart] = (workout.logged_at || '').split('T');
  document.getElementById('edit-date-input').value = datePart || '';
  document.getElementById('edit-time-input').value = (timePart || '').slice(0, 5);
}

function exitEditMode() {
  document.getElementById('view-actions').style.display = 'flex';
  document.getElementById('edit-actions').style.display = 'none';

  document.getElementById('exercises').style.display = 'block';
  document.getElementById('edit-exercise-container').style.display = 'none';
  document.getElementById('edit-add-exercise-btn').style.display = 'none';
  document.getElementById('edit-notes').style.display = 'none';
  document.getElementById('edit-datetime-row').style.display = 'none';

  renderWorkout(workout);
}

async function saveWorkout() {
  const exerciseBlocks = document.querySelectorAll('#edit-exercise-container .exercise-block');
  const exercises = [];

  for (const block of exerciseBlocks) {
    const id = block.id.replace('edit-exercise-', '');
    const nameInput = document.getElementById(`name-${id}`);
    const name = nameInput.value.trim();
    const exercise_id = parseInt(nameInput.dataset.exerciseId || '');

    if (!name) { alert("Exercise name can't be empty"); return; }
    if (!exercise_id) { alert(`Select "${name}" from the list first`); return; }

    const setRows = document.querySelectorAll(`#sets-${id} tr`);
    const sets = [];

    for (const row of setRows) {
      const rowId = row.id.replace('set-', '');
      const reps = parseInt(document.getElementById(`reps-${rowId}`).value);
      const weightVal = document.getElementById(`weight-${rowId}`).value;
      const weight_lbs = weightVal !== '' ? parseFloat(weightVal) : null;

      if (!reps || reps < 1) { alert('Each set needs a rep count'); return; }
      sets.push(weight_lbs !== null ? { reps, weight_lbs } : { reps });
    }

    if (sets.length === 0) { alert('Add at least one set'); return; }
    exercises.push({ exercise_id, sets });
  }

  if (exercises.length === 0) { alert('Add at least one exercise'); return; }

  const notes = document.getElementById('edit-notes').value.trim() || null;

  const editDate = document.getElementById('edit-date-input').value;
  const editTime = document.getElementById('edit-time-input').value;

  if (!editDate || !editTime) {
    alert('Date and time are required');
    return;
  }

  const chosenDt = new Date(editDate + 'T' + editTime + ':00');
  if (chosenDt > new Date()) {
    alert('Workout date cannot be in the future');
    return;
  }

  const loggedAt = editDate + 'T' + editTime + ':00';

  const saveBtn = document.querySelector('.btn-save');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';

  try {
    const res = await authFetch(`/api/workout/${sessionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercises, notes, logged_at: loggedAt }),
    });
    if (!res.ok) throw new Error(await res.text());
    workout = await res.json();
    exitEditMode();
  } catch (e) {
    alert('Error saving workout');
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save';
  }
}

document.addEventListener('click', e => {
  if (!e.target.closest('.ex-select-wrap')) closeAllDropdowns();
  if (!e.target.closest('.ms-wrap')) closeAllMs();
});

load();
