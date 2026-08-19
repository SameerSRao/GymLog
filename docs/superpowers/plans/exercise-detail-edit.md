# Exercise Detail Edit & Equipment Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an equipment `<select>` dropdown to the exercises browser edit form and add inline edit functionality to the exercise detail page (`/exercise/{id}`).

**Architecture:** Two isolated frontend-only changes to existing HTML/JS pages. No backend changes needed — `PUT /api/exercise/{id}` already handles all fields. The detail page edit follows the same inline header-swap pattern as the exercises browser, using the same CSS classes.

**Tech Stack:** Vanilla HTML/CSS/JS, no framework. FastAPI serves static files. Dark theme (`#0f0f0f` background).

## Global Constraints

- No backend changes — `PUT /api/exercise/{id}` and `GET /api/muscle-groups` already exist
- No tests (out of scope)
- Do not modify any Python files
- Match existing dark theme: background `#0f0f0f`, card background `#1a1a1a`, borders `#2a2a2a`, text `#f0f0f0`
- Equipment options are a fixed static list of 29 values (see Task 1) — no free-text fallback
- User does not run git commands — do NOT include any `git add` or `git commit` steps

---

## Shared constant: equipment options

Both tasks use the same 29 equipment values. Define a JS helper function in each file:

```js
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
```

`current` is the exercise's current `equipment` value (or `''` if none). The selected option pre-populates on edit open.

---

### Task 1: Equipment `<select>` in exercises.html

**Files:**
- Modify: `app/static/exercises.html`

**Interfaces:**
- Consumes: existing `renderEditRow(ex)` function and `saveEdit(id)` function
- Produces: `equipmentOptions(current)` helper; `<select id="edit-equipment-${ex.id}">` element in `renderEditRow`

- [ ] **Step 1: Add `equipmentOptions()` helper function**

In `app/static/exercises.html`, find the `<script>` block. Locate where `let activeEditId = null` is declared (near the top of the script). Add `equipmentOptions` as a standalone function somewhere before `renderEditRow`. The exact placement is anywhere before `renderEditRow` in the script block.

```js
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
```

- [ ] **Step 2: Replace equipment `<input>` with `<select>` in `renderEditRow`**

In `renderEditRow(ex)`, find these two lines:

```js
const equipVal = escHtml(ex.equipment || '');
```

and later in the template:

```html
<input id="edit-equipment-${ex.id}" class="edit-input" value="${equipVal}" placeholder="e.g. barbell" autocomplete="off" />
```

Remove the `equipVal` line. Replace the `<input>` line with:

```html
<select id="edit-equipment-${ex.id}" class="edit-input">
  ${equipmentOptions(ex.equipment || '')}
</select>
```

`saveEdit(id)` already reads `.value` from the element and does `|| null` for empty string — no change to `saveEdit` needed.

- [ ] **Step 3: Add `select.edit-input` CSS rule**

In the `<style>` block, find the `.edit-input` rule:

```css
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
```

Add immediately after it:

```css
select.edit-input option { background: #1a1a1a; }
```

This ensures dropdown option items render with the dark background.

- [ ] **Step 4: Manual smoke test**

Start the app: `docker compose up --build` (or `uvicorn app.main:app --reload` with venv active).

Open `http://localhost:8000/exercises`. Click **Edit** on any row. Verify:
- Equipment field shows a `<select>` dropdown (not a text input)
- The dropdown pre-selects the exercise's current equipment value (or shows "— none —" if empty)
- Save with a different equipment value, confirm the row re-renders with the new value
- Save with "— none —" selected, confirm equipment tag disappears from the row

---

### Task 2: Inline edit on exercise detail page (`exercise.html`)

**Files:**
- Modify: `app/static/exercise.html`

**Interfaces:**
- Consumes: `GET /api/exercise/${exerciseId}/info` (already called in `load()`), `GET /api/muscle-groups` (new parallel fetch), `PUT /api/exercise/${exerciseId}` (new)
- Produces: module-level `info` variable; `openEditDetail()`, `closeEditDetail()`, `saveEditDetail()` functions; `<div id="ex-header">` containing the swappable header

**Overview of changes:**

1. Add CSS for the edit form and Edit button
2. Replace the static `<h1>`, `.tags`, `<details>` elements in HTML with `<div id="ex-header"></div>`
3. Add module-level state variables
4. Add `escHtml()`, `equipmentOptions()`, `renderViewHeader()`, `renderEditHeader()` functions
5. Refactor `load()` to fetch muscle groups, store `info`, and call `renderViewHeader()`
6. Add `openEditDetail()`, `closeEditDetail()`, `saveEditDetail()`
7. Add muscle group dropdown functions

- [ ] **Step 1: Add CSS for the edit form**

In `app/static/exercise.html`, find the existing `h1` CSS rule:

```css
h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 10px; }
```

Replace with (removes margin-bottom — the wrapper handles spacing now):

```css
h1 { font-size: 1.6rem; font-weight: 700; }
```

Then find the `#loading` rule near the bottom of the `<style>` block:

```css
#loading { color: #555; font-size: 0.9rem; padding: 20px 0; }
```

Add the following CSS block **after** it (before `</style>`):

```css
.ex-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
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
  flex-shrink: 0;
}
.btn-edit:hover { border-color: #555; color: #ccc; }

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
select.edit-input option { background: #1a1a1a; }

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
  margin-bottom: 20px;
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

.filter-wrap { position: relative; }

.filter-trigger {
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  color: #666;
  font-size: 0.82rem;
  padding: 7px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.filter-trigger:hover { border-color: #444; color: #aaa; }
.filter-trigger.active { border-color: #5a9cf5; color: #8ab8ff; }

.filter-panel {
  display: none;
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 200px;
  background: #1a1a1a;
  border: 1px solid #444;
  border-radius: 8px;
  z-index: 200;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.filter-panel.open { display: block; }

.filter-search {
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid #2a2a2a;
  border-radius: 8px 8px 0 0;
  color: #f0f0f0;
  font-size: 0.85rem;
  padding: 9px 12px;
}
.filter-search:focus { outline: none; }

.filter-list { max-height: 200px; overflow-y: auto; padding: 4px 0; }

.filter-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  font-size: 0.85rem;
  color: #bbb;
  cursor: pointer;
  user-select: none;
}
.filter-option:hover { background: #252525; }
.filter-option input { width: auto; accent-color: #5a9cf5; }
.filter-option.checked { color: #f0f0f0; }

.filter-empty { padding: 10px 12px; font-size: 0.82rem; color: #555; }
```

- [ ] **Step 2: Replace static header elements in HTML with `<div id="ex-header">`**

Find this block in the `<body>`:

```html
  <div id="loading">Loading…</div>
  <div id="content" style="display:none">
    <h1 id="ex-name"></h1>
    <div class="tags" id="ex-tags"></div>

    <details id="instructions-section" style="display:none">
      <summary>How to perform</summary>
      <p class="instructions-text" id="ex-instructions"></p>
    </details>
```

Replace with:

```html
  <div id="loading">Loading…</div>
  <div id="content" style="display:none">
    <div id="ex-header"></div>
```

- [ ] **Step 3: Add module-level state variables and helper functions**

In the `<script>` block, find the existing variable declarations at the top:

```js
const exerciseId = window.location.pathname.split('/').filter(Boolean).pop();

let currentView = 'weight';
let chartData = {};
```

Replace with:

```js
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
```

- [ ] **Step 4: Add `renderViewHeader()` and `renderEditHeader()` functions**

Add these two functions after the `equipmentOptions` function (still in the `<script>` block, before `load()`):

```js
function renderViewHeader() {
  const tags = [];
  if (info.equipment) tags.push(`<span class="tag tag-equipment">${escHtml(info.equipment)}</span>`);
  for (const mg of info.muscle_groups) tags.push(`<span class="tag tag-muscle">${escHtml(mg.name)}</span>`);
  if (info.target) tags.push(`<span class="tag tag-target">${escHtml(info.target)}</span>`);

  const instructionsHtml = info.instructions
    ? `<details>
        <summary>How to perform</summary>
        <p class="instructions-text">${escHtml(info.instructions)}</p>
      </details>`
    : '';

  return `<div class="ex-title-row">
    <h1>${escHtml(info.name)}</h1>
    <button class="btn-edit" onclick="openEditDetail()">Edit</button>
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

    <label class="edit-label">Target</label>
    <input id="detail-edit-target" class="edit-input" value="${escHtml(info.target || '')}" placeholder="e.g. biceps" autocomplete="off" />

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
```

- [ ] **Step 5: Refactor `load()` to fetch muscle groups and use `renderViewHeader()`**

Find the existing `load()` function:

```js
async function load() {
  const [infoRes, progRes] = await Promise.all([
    fetch(`/api/exercise/${exerciseId}/info`),
    fetch(`/api/exercise/${exerciseId}/progression`),
  ]);

  if (!infoRes.ok) {
    document.getElementById('loading').textContent = 'Exercise not found.';
    return;
  }
  if (!progRes.ok) {
    document.getElementById('loading').textContent = 'Failed to load progression data.';
    return;
  }

  const info = await infoRes.json();
  const prog = await progRes.json();

  document.title = `${info.name} — GymLog`;
  document.getElementById('loading').style.display = 'none';
  document.getElementById('content').style.display = 'block';

  // Header
  document.getElementById('ex-name').textContent = info.name;

  const tagsDiv = document.getElementById('ex-tags');
  const parts = [];
  if (info.equipment) parts.push(`<span class="tag tag-equipment">${info.equipment}</span>`);
  for (const mg of info.muscle_groups) {
    parts.push(`<span class="tag tag-muscle">${mg.name}</span>`);
  }
  tagsDiv.innerHTML = parts.join('');

  // Instructions
  if (info.instructions) {
    document.getElementById('ex-instructions').textContent = info.instructions;
    document.getElementById('instructions-section').style.display = 'block';
  }

  // Progression
  renderSessions(prog.sessions);
}
```

Replace with:

```js
async function load() {
  const [infoRes, progRes, mgRes] = await Promise.all([
    fetch(`/api/exercise/${exerciseId}/info`),
    fetch(`/api/exercise/${exerciseId}/progression`),
    fetch('/api/muscle-groups'),
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
```

Key changes: `info` now assigns to the module-level variable (no `const`); adds `mgRes` parallel fetch; replaces the manual header DOM manipulation with `renderViewHeader()`.

- [ ] **Step 6: Add `openEditDetail()`, `closeEditDetail()`, and `saveEditDetail()`**

Add these three functions after `load()` (before `renderSessions` or anywhere in the script block after `renderEditHeader`):

```js
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
  const target = document.getElementById('detail-edit-target').value.trim() || null;
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
    const res = await fetch(`/api/exercise/${exerciseId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, equipment, target, instructions, muscle_group_ids }),
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
```

- [ ] **Step 7: Add muscle group dropdown functions**

Add these three functions after `saveEditDetail()`:

```js
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
```

- [ ] **Step 8: Manual smoke test**

Start the app: `docker compose up --build` (or `uvicorn app.main:app --reload` with venv active).

Open any exercise detail page, e.g. `http://localhost:8000/exercise/1`.

**View mode:** Confirm the page loads normally — name, tags, PR banner, chart, and session cards all visible. An **Edit** button appears to the right of the exercise name.

**Edit mode — open:**
- Click **Edit**
- Confirm the name/tags/instructions section is replaced by the edit form
- Confirm name field is prefilled with the exercise name
- Confirm equipment dropdown pre-selects the current value
- Confirm muscle groups dropdown shows correct pre-checked groups
- Confirm the PR banner, chart, and session cards are still visible below

**Edit mode — cancel:**
- Click **Cancel**
- Confirm the header snaps back to view mode with the original values

**Edit mode — save:**
- Change the name to something unique (e.g. append " TEST")
- Change equipment to a different value
- Click **Save**
- Confirm the header re-renders with the updated name and equipment tag
- Confirm `document.title` updated
- Confirm the PR banner, chart, and session cards are unaffected

**409 conflict:**
- Click **Edit**
- Type the exact name of a different existing exercise in the name field
- Click **Save**
- Confirm the inline error "An exercise with that name already exists" appears
- Confirm the Save button re-enables

**404 / error:**
- Temporarily change `exerciseId` in console to `999999`, call `saveEditDetail()` — or just verify the error path exists in code
