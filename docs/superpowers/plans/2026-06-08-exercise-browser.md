# Exercise Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/exercises` browse page with text search and muscle/equipment filters, accessible from the home page dashboard.

**Architecture:** No backend changes needed — `GET /api/exercises` and `GET /api/muscle-groups` already return all data needed. The new `exercises.html` loads all 1,324 exercises once and filters client-side in real-time. The dashboard gets an "Exercises" nav button alongside the existing "Calendar" button. The `/exercises` route is added to `main.py` before `app.include_router()`.

**Tech Stack:** Vanilla JS, HTML, CSS. FastAPI FileResponse. No new dependencies.

---

## File Structure

| File | Change |
|------|--------|
| `app/main.py` | Add `GET /exercises` route (with `NO_CACHE` header, same as other page routes) |
| `app/static/dashboard.html` | Add "Exercises" nav button to page header |
| `app/static/exercises.html` | Create — browse page with search, muscle/equipment filters, exercise list |

---

### Task 1: Add `/exercises` route and dashboard link

**Files:**
- Modify: `app/main.py`
- Modify: `app/static/dashboard.html`

- [ ] **Step 1: Add the `/exercises` route to `app/main.py`**

`main.py` already has a `NO_CACHE` constant and page routes registered before `app.include_router()`. Add the new route after `/workouts` and before `/workout/{session_id}`:

```python
NO_CACHE = {"Cache-Control": "no-cache"}

# HTML page routes — registered before API routers so they take priority
@app.get("/workouts")
def workouts_page():
    return FileResponse("app/static/workouts.html", headers=NO_CACHE)

@app.get("/exercises")
def exercises_page():
    return FileResponse("app/static/exercises.html", headers=NO_CACHE)

@app.get("/workout/{session_id}")
def workout_page(session_id: int):
    return FileResponse("app/static/workout.html", headers=NO_CACHE)

@app.get("/exercise/{exercise_id}")
def exercise_page(exercise_id: int):
    return FileResponse("app/static/exercise.html", headers=NO_CACHE)

@app.get("/log")
def log_page():
    return FileResponse("app/static/index.html", headers=NO_CACHE)

@app.get("/")
def index():
    return FileResponse("app/static/dashboard.html", headers=NO_CACHE)
```

**Important:** `/exercises` (plural, no path parameter) must be registered before `/exercise/{exercise_id}` (singular, with parameter) to avoid FastAPI treating "exercises" as a value for `exercise_id`.

- [ ] **Step 2: Add "Exercises" link to the dashboard header**

Open `app/static/dashboard.html`. Find this line in the `<body>`:

```html
    <a href="/workouts" class="btn-secondary">Calendar</a>
```

Replace it with a flex row containing both nav links:

```html
    <div style="display:flex;gap:8px;">
      <a href="/exercises" class="btn-secondary">Exercises</a>
      <a href="/workouts" class="btn-secondary">Calendar</a>
    </div>
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/static/dashboard.html
git commit -m "feat: add /exercises route and dashboard nav link"
```

---

### Task 2: Create exercises.html

**Files:**
- Create: `app/static/exercises.html`

Create the file with the complete content below. The page:
- Shows a `← GymLog` back link and `Exercises` heading
- Has a full-width text search input with token-based matching (same algorithm as the logging form)
- Has Muscle and Equipment multi-select filter dropdowns
- Shows a "✕ Clear" button when any filter is active
- Shows `"Showing 60 of 1324 — search or filter to see more"` when unfiltered; shows all results when any filter/search is active
- Each result row links to `/exercise/{id}` and shows the exercise name plus equipment and muscle group tags (up to 3 muscle tags per row)

- [ ] **Step 1: Create `app/static/exercises.html` with this complete content**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Exercises — GymLog</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #0f0f0f;
      color: #f0f0f0;
      font-family: system-ui, sans-serif;
      padding: 24px 16px 48px;
      max-width: 600px;
      margin: 0 auto;
    }

    .back-link {
      display: inline-block;
      color: #666;
      font-size: 0.85rem;
      text-decoration: none;
      margin-bottom: 20px;
    }
    .back-link:hover { color: #aaa; }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    h1 { font-size: 1.4rem; letter-spacing: 0.05em; }

    .btn-secondary {
      background: none;
      border: 1px solid #333;
      border-radius: 6px;
      color: #888;
      font-size: 0.85rem;
      padding: 7px 12px;
      text-decoration: none;
    }
    .btn-secondary:hover { border-color: #555; color: #ccc; }

    .search-input {
      width: 100%;
      background: #111;
      border: 1px solid #333;
      border-radius: 8px;
      color: #f0f0f0;
      font-size: 1rem;
      padding: 10px 14px;
      margin-bottom: 10px;
    }
    .search-input:focus { outline: none; border-color: #555; }

    .filter-row {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
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

    .filter-clear {
      background: none;
      border: 1px solid #333;
      border-radius: 6px;
      color: #555;
      font-size: 0.8rem;
      padding: 7px 10px;
      cursor: pointer;
    }
    .filter-clear:hover { border-color: #555; color: #aaa; }

    .results-meta {
      font-size: 0.78rem;
      color: #555;
      margin-bottom: 12px;
    }

    .ex-row {
      display: block;
      padding: 12px 14px;
      background: #1a1a1a;
      border: 1px solid #2a2a2a;
      border-radius: 8px;
      margin-bottom: 8px;
      text-decoration: none;
      color: inherit;
    }
    .ex-row:hover { border-color: #3a3a3a; background: #1e1e1e; }

    .ex-row-name { font-size: 0.95rem; color: #e0e0e0; margin-bottom: 6px; }

    .ex-row-tags { display: flex; flex-wrap: wrap; gap: 5px; }

    .tag { border-radius: 4px; font-size: 0.72rem; padding: 2px 8px; }
    .tag-equipment { background: #1c1c2e; border: 1px solid #3a3a5a; color: #8888cc; }
    .tag-muscle    { background: #252525; border: 1px solid #3a3a3a; color: #aaa; }

    .empty-state {
      text-align: center;
      color: #444;
      font-size: 0.9rem;
      padding: 40px 0;
    }

    #loading { color: #555; font-size: 0.9rem; padding: 20px 0; }
  </style>
</head>
<body>
  <a class="back-link" href="/">← GymLog</a>

  <div class="page-header">
    <h1>Exercises</h1>
    <a href="/log" class="btn-secondary">Log Workout</a>
  </div>

  <div id="loading">Loading…</div>

  <div id="browser" style="display:none">
    <input class="search-input" id="search" type="text"
           placeholder="Search exercises…" autocomplete="off" oninput="filter()" />

    <div class="filter-row">
      <div class="filter-wrap">
        <button class="filter-trigger" id="filter-trigger-muscle"
                onclick="toggleFilter('muscle')">Muscles ▾</button>
        <div class="filter-panel" id="filter-panel-muscle">
          <input class="filter-search" placeholder="Search muscles…"
                 oninput="renderFilterOptions('muscle', this.value)" />
          <div class="filter-list" id="filter-list-muscle"></div>
        </div>
      </div>
      <div class="filter-wrap">
        <button class="filter-trigger" id="filter-trigger-equipment"
                onclick="toggleFilter('equipment')">Equipment ▾</button>
        <div class="filter-panel" id="filter-panel-equipment">
          <input class="filter-search" placeholder="Search equipment…"
                 oninput="renderFilterOptions('equipment', this.value)" />
          <div class="filter-list" id="filter-list-equipment"></div>
        </div>
      </div>
      <button class="filter-clear" id="filter-clear" style="display:none"
              onclick="clearFilters()">✕ Clear</button>
    </div>

    <p class="results-meta" id="results-meta"></p>
    <div id="results"></div>
  </div>

  <script>
    let allExercises = [];
    let muscleGroups = [];
    let equipmentValues = [];
    const selectedMuscles = new Set();
    const selectedEquipment = new Set();

    const MAX_UNFILTERED = 60;

    async function init() {
      try {
        const [exRes, mgRes] = await Promise.all([
          fetch('/api/exercises'),
          fetch('/api/muscle-groups'),
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

    document.addEventListener('click', e => {
      if (!e.target.closest('.filter-wrap')) closeAllFilters();
    });

    init();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/static/exercises.html
git commit -m "feat: create exercise browser page with search and filters"
```

---

### Task 3: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Start the app**

```bash
docker compose up --build
```

- [ ] **Step 2: Verify the "Exercises" button on the home page**

Open `http://localhost:8000`. Confirm:
- "Exercises" button appears in the top-right header alongside "Calendar"
- Clicking "Exercises" navigates to `http://localhost:8000/exercises`

- [ ] **Step 3: Verify the exercise browser page loads**

On `http://localhost:8000/exercises`, confirm:
- `← GymLog` link in top-left, "Exercises" heading, "Log Workout" button top-right
- Search input visible
- "Muscles ▾" and "Equipment ▾" filter buttons visible
- Results load: "Showing 60 of 1324 — search or filter to see more"
- 60 exercise rows visible, each with name and tags

- [ ] **Step 4: Verify search**

Type "bench press" in the search input. Confirm:
- Results update immediately (no submit button needed)
- Only exercises containing both "bench" and "press" in the name are shown
- Result count in meta line reflects the filtered count

- [ ] **Step 5: Verify muscle filter**

Click "Muscles ▾". Confirm a dropdown panel opens with a search input and a list of muscle groups. Select "Chest". Confirm:
- "Chest ▾" appears on the trigger button with blue highlight
- "✕ Clear" button appears
- Results update to only show chest exercises

- [ ] **Step 6: Verify equipment filter**

Click "Equipment ▾". Select "barbell". Confirm results narrow to barbell chest exercises. Deselect to reset.

- [ ] **Step 7: Verify clicking an exercise navigates to its progression page**

Click any exercise row. Confirm it navigates to `/exercise/{id}` and the exercise detail page loads correctly.

- [ ] **Step 8: Verify "✕ Clear" resets filters**

Apply a muscle filter. Click "✕ Clear". Confirm all filters clear, trigger buttons reset to default text, and results return to the unfiltered 60-of-1324 view.

- [ ] **Step 9: Verify "← GymLog" and "Log Workout" links**

- `← GymLog` → navigates to `/` (dashboard)
- `Log Workout` → navigates to `/log` (logging form)
