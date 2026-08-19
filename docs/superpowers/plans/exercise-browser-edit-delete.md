# Exercise Browser Edit & Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline edit and delete to the existing `/exercises` browser page, and add Exercises nav links to pages that only have a Workouts link.

**Architecture:** All changes are frontend-only — the PUT and DELETE endpoints are already implemented. `exercises.html` gets new CSS, a restructured row renderer, and JS for edit/delete state management. The edit pattern (per-row full swap) mirrors `workout.html`.

**Tech Stack:** Vanilla HTML/CSS/JS, no build step, no framework. All files are in `app/static/`.

## Global Constraints

- No backend changes — `GET /exercises` route already exists in `main.py`
- No tests (no test suite exists)
- Do not run git commands — the user handles all git operations
- Do not run the app or docker — skip smoke test steps that require the server
- Follow existing visual style: dark theme (`#0f0f0f` background, `#1a1a1a` cards, `#f0f0f0` text)
- Reuse CSS classes from `workout.html` verbatim where noted — do not invent new names
- One row can be in edit mode at a time; filtering clears any open edit form

---

### Task 1: Navigation links + SPEC.md

**Files:**
- Modify: `app/static/index.html` (log page header)
- Modify: `app/static/workouts.html` (calendar page header)
- Modify: `SPEC.md`

**Interfaces:**
- Produces: nothing consumed by later tasks — standalone doc/nav change

- [ ] **Step 1: Add Exercises link to `index.html`**

Find in `app/static/index.html` (around line 377):
```html
<div style="display:flex;gap:8px;">
  <a href="/workouts" class="btn-new-exercise" style="text-decoration:none;">Workouts</a>
  <button class="btn-new-exercise" onclick="toggleCreateForm()">+ New Exercise</button>
</div>
```

Replace with:
```html
<div style="display:flex;gap:8px;">
  <a href="/exercises" class="btn-new-exercise" style="text-decoration:none;">Exercises</a>
  <a href="/workouts" class="btn-new-exercise" style="text-decoration:none;">Workouts</a>
  <button class="btn-new-exercise" onclick="toggleCreateForm()">+ New Exercise</button>
</div>
```

- [ ] **Step 2: Add Exercises link to `workouts.html`**

Find in `app/static/workouts.html` (around line 179):
```html
  <a class="back-link" href="/">← GymLog</a>
```

Replace with:
```html
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
    <a class="back-link" style="margin-bottom:0" href="/">← GymLog</a>
    <a class="back-link" style="margin-bottom:0" href="/exercises">Exercises →</a>
  </div>
```

- [ ] **Step 3: Update `SPEC.md` pages table**

Find the pages table under `### HTML pages (served by FastAPI, no prefix)`:
```markdown
| GET / | Log workout |
| GET /workouts | Calendar + recent list |
| GET /workout/{id} | Workout detail |
| GET /exercise/{id} | Exercise info + progression |
```

Replace with:
```markdown
| GET / | Dashboard |
| GET /log | Log workout |
| GET /workouts | Calendar + recent list |
| GET /workout/{id} | Workout detail |
| GET /exercises | Exercise browser — search, filter, edit, delete |
| GET /exercise/{id} | Exercise info + progression |
```

- [ ] **Step 4: Remove exercise browser from "What's Not Built Yet" in `SPEC.md`**

Find and remove this row from the "What's Not Built Yet" table:
```markdown
| Exercise browser | No page to browse/search all exercises outside of logging |
```

---

### Task 2: Row structure refactor + CSS

Restructure each exercise row from an `<a>` tag to a `<div>` with an inner link plus Edit/Delete action buttons. Extract `renderRow(ex)` helper. Add all needed CSS.

**Files:**
- Modify: `app/static/exercises.html`

**Interfaces:**
- Produces: `renderRow(ex)` — JS function returning HTML string for a single exercise in view mode; consumed by Tasks 3 and 4
- Produces: CSS classes `.ex-row-main`, `.ex-row-link`, `.ex-row-actions`, `.btn-edit`, `.btn-delete-row`

- [ ] **Step 1: Add new CSS to the `<style>` block in `exercises.html`**

Add after the existing `.empty-state` rule (before `#loading`):

```css
.ex-row-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ex-row-link {
  flex: 1;
  text-decoration: none;
  color: inherit;
  min-width: 0;
}

.ex-row-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-edit {
  background: none;
  border: 1px solid #333;
  border-radius: 6px;
  color: #888;
  font-size: 0.78rem;
  padding: 5px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-edit:hover { border-color: #555; color: #ccc; }

.btn-delete-row {
  background: none;
  border: 1px solid #3a2020;
  border-radius: 6px;
  color: #8a4a4a;
  font-size: 0.78rem;
  padding: 5px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-delete-row:hover { border-color: #6a2a2a; color: #cf6f6f; }
```

- [ ] **Step 2: Add `renderRow(ex)` function to the `<script>` block**

Add before the existing `filter()` function:

```js
function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderRow(ex) {
  const equipTag = ex.equipment
    ? `<span class="tag tag-equipment">${escHtml(ex.equipment)}</span>`
    : '';
  const muscleTags = ex.muscle_groups.slice(0, 3)
    .map(mg => `<span class="tag tag-muscle">${escHtml(mg.name)}</span>`)
    .join('');
  return `<div class="ex-row" id="row-${ex.id}">
    <div class="ex-row-main">
      <a class="ex-row-link" href="/exercise/${ex.id}">
        <div class="ex-row-name">${escHtml(ex.name)}</div>
        <div class="ex-row-tags">${equipTag}${muscleTags}</div>
      </a>
      <div class="ex-row-actions">
        <button class="btn-edit" onclick="openEdit(${ex.id})">Edit</button>
        <button class="btn-delete-row" onclick="confirmDeleteExercise(${ex.id})">Delete</button>
      </div>
    </div>
  </div>`;
}
```

- [ ] **Step 3: Update `filter()` to use `renderRow()` and reset active edit**

Find the existing `filter()` function. It currently ends with:
```js
container.innerHTML = toShow.map(ex => {
  const equipTag = ex.equipment
    ? `<span class="tag tag-equipment">${ex.equipment}</span>`
    : '';
  const muscleTags = ex.muscle_groups.slice(0, 3)
    .map(mg => `<span class="tag tag-muscle">${mg.name}</span>`)
    .join('');
  return `<a class="ex-row" href="/exercise/${ex.id}">
    <div class="ex-row-name">${ex.name}</div>
    <div class="ex-row-tags">${equipTag}${muscleTags}</div>
  </a>`;
}).join('');
```

Replace just that final block with:
```js
  activeEditId = null;
  editMuscleGroupIds = new Set();

  container.innerHTML = toShow.map(ex => renderRow(ex)).join('');
```

Also add these two variable declarations near the top of the `<script>` block, alongside the existing `let allExercises = [];` declarations:

```js
let activeEditId = null;
let editMuscleGroupIds = new Set();
```

---

### Task 3: Delete flow

Add a shared confirmation overlay and the delete logic. Clicking Delete on a row opens the overlay; confirming calls `DELETE /api/exercise/{id}`; 204 removes the row and splices from `allExercises`; 409 shows an inline message on the row.

**Files:**
- Modify: `app/static/exercises.html`

**Interfaces:**
- Consumes: `renderRow(ex)` from Task 2 (to re-render a row after failed delete)
- Produces: `confirmDeleteExercise(id)`, `closeDeleteOverlay()`, `executeDelete()` — called from `onclick` attributes in row HTML and overlay HTML

- [ ] **Step 1: Add confirm overlay CSS to the `<style>` block**

Add after the `.btn-delete-row` rules added in Task 2:

```css
.confirm-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.confirm-overlay.open { display: flex; }

.confirm-box {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 24px;
  width: 300px;
  text-align: center;
}
.confirm-box p { font-size: 0.9rem; color: #aaa; margin-bottom: 20px; line-height: 1.5; }
.confirm-actions { display: flex; gap: 10px; }
.confirm-actions button { flex: 1; padding: 10px; border-radius: 7px; cursor: pointer; font-size: 0.9rem; }
.btn-cancel { background: none; border: 1px solid #333; color: #888; }
.btn-cancel:hover { border-color: #555; color: #ccc; }
.btn-confirm-delete { background: #3a1a1a; border: 1px solid #6a2a2a; color: #cf6f6f; }
.btn-confirm-delete:hover { background: #4a2020; }
```

- [ ] **Step 2: Add the confirm overlay HTML**

Add just before the closing `</body>` tag:

```html
<div class="confirm-overlay" id="delete-overlay">
  <div class="confirm-box">
    <p>Delete <strong id="confirm-delete-name"></strong>?<br>This can't be undone.</p>
    <div class="confirm-actions">
      <button class="btn-cancel" onclick="closeDeleteOverlay()">Cancel</button>
      <button class="btn-confirm-delete" onclick="executeDelete()">Delete</button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add delete state variable and functions to the `<script>` block**

Add alongside the other `let` declarations at the top of the script:

```js
let pendingDeleteId = null;
```

Add these functions after `clearFilters()`:

```js
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
    const res = await fetch(`/api/exercise/${id}`, { method: 'DELETE' });

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
```

- [ ] **Step 4: Close the overlay when clicking the backdrop**

Find the existing `document.addEventListener('click', ...)` at the bottom of the script. Add an overlay-close clause to the existing handler:

```js
document.addEventListener('click', e => {
  if (!e.target.closest('.filter-wrap')) closeAllFilters();
  if (e.target === document.getElementById('delete-overlay')) closeDeleteOverlay();
});
```

---

### Task 4: Edit flow

Per-row inline edit form (full row swap, matching workout.html style). Clicking Edit replaces the row with a form; Save calls PUT; Cancel reverts. Only one row editable at a time.

**Files:**
- Modify: `app/static/exercises.html`

**Interfaces:**
- Consumes: `renderRow(ex)`, `activeEditId`, `editMuscleGroupIds` from Task 2
- Consumes: `muscleGroups` (already loaded in `init()`)
- Produces: `openEdit(id)`, `closeEdit(id)`, `saveEdit(id)`, `toggleMgPanel(id)`, `renderMgOptions(id, query)`, `toggleMgOption(editId, mgId, checked)`, `updateMgTrigger(id)` — called from row HTML onclick attributes

- [ ] **Step 1: Add edit form CSS to the `<style>` block**

Add after the confirm overlay CSS from Task 3:

```css
.ex-row--editing {
  background: #1e1e1e;
  border-color: #3a3a3a;
  padding: 14px;
}

.edit-label {
  display: block;
  font-size: 0.78rem;
  color: #666;
  margin: 12px 0 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.edit-label:first-child { margin-top: 0; }

.edit-input {
  width: 100%;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  color: #f0f0f0;
  font-size: 0.95rem;
  padding: 9px 12px;
}
.edit-input:focus { outline: none; border-color: #555; }

.edit-textarea {
  width: 100%;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  color: #f0f0f0;
  font-size: 0.88rem;
  font-family: system-ui, sans-serif;
  padding: 9px 12px;
  resize: vertical;
  line-height: 1.5;
}
.edit-textarea:focus { outline: none; border-color: #555; }

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.btn-save {
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  color: #0f0f0f;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 7px 16px;
  cursor: pointer;
}
.btn-save:hover { background: #ccc; }
.btn-save:disabled { background: #333; color: #666; cursor: default; }

.btn-cancel-edit {
  background: none;
  border: 1px solid #333;
  border-radius: 6px;
  color: #666;
  font-size: 0.85rem;
  padding: 7px 12px;
  cursor: pointer;
}
.btn-cancel-edit:hover { border-color: #555; color: #aaa; }

.edit-error {
  font-size: 0.8rem;
  color: #cf6f6f;
  margin-top: 8px;
}
```

- [ ] **Step 2: Add `renderEditRow(ex)` function**

Add before `openEdit()` (which you'll add next):

```js
function renderEditRow(ex) {
  const nameVal = escHtml(ex.name);
  const equipVal = escHtml(ex.equipment || '');
  const targetVal = escHtml(ex.target || '');
  const instrVal = escHtml(ex.instructions || '');
  return `<div class="ex-row ex-row--editing" id="row-${ex.id}">
    <label class="edit-label">Name</label>
    <input id="edit-name-${ex.id}" class="edit-input" value="${nameVal}" autocomplete="off" />

    <label class="edit-label">Equipment</label>
    <input id="edit-equipment-${ex.id}" class="edit-input" value="${equipVal}" placeholder="e.g. barbell" autocomplete="off" />

    <label class="edit-label">Target</label>
    <input id="edit-target-${ex.id}" class="edit-input" value="${targetVal}" placeholder="e.g. biceps" autocomplete="off" />

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
```

- [ ] **Step 3: Add `openEdit()` and `closeEdit()` functions**

Add after `renderEditRow()`:

```js
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
```

- [ ] **Step 4: Add muscle group panel helper functions**

Add after `closeEdit()`:

```js
function toggleMgPanel(id) {
  const panel = document.getElementById(`mg-panel-${id}`);
  const isOpen = panel.classList.contains('open');
  // Close existing filter panels first
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
```

- [ ] **Step 5: Add `saveEdit()` function**

Add after `updateMgTrigger()`:

```js
async function saveEdit(id) {
  const name = document.getElementById(`edit-name-${id}`).value.trim();
  const equipment = document.getElementById(`edit-equipment-${id}`).value.trim() || null;
  const target = document.getElementById(`edit-target-${id}`).value.trim() || null;
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
    const res = await fetch(`/api/exercise/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, equipment, target, instructions, muscle_group_ids }),
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
```

- [ ] **Step 6: Update the `document.addEventListener('click', ...)` to also close the muscle group panel**

Find the existing click listener (added/modified in Task 3):
```js
document.addEventListener('click', e => {
  if (!e.target.closest('.filter-wrap')) closeAllFilters();
  if (e.target === document.getElementById('delete-overlay')) closeDeleteOverlay();
});
```

The existing `closeAllFilters()` already closes any open `.filter-panel`, which includes the muscle group panel inside the edit form — no additional change needed here. Verify `closeAllFilters()` is:
```js
function closeAllFilters() {
  document.querySelectorAll('.filter-panel.open').forEach(p => p.classList.remove('open'));
}
```

If it is, no change needed. If `closeAllFilters()` only closes the two browser filter panels, update it to use the generic selector above.
