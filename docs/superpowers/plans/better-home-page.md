# Better Home Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the workout logging form at `/` with a stats dashboard, and move the logging form to `/log`.

**Architecture:** All changes are frontend-only except one backend route addition. `app/main.py` gets a new `GET /log` route (serving the existing `index.html`) and the existing `GET /` is updated to serve a new `dashboard.html`. The dashboard fetches `GET /api/workouts` once and computes all stats client-side — no new API endpoints needed. Existing `← GymLog` back-links on other pages already point to `/` and will correctly reach the new dashboard without changes.

**Tech Stack:** Vanilla JS, HTML, CSS. FastAPI page routes. No new dependencies.

---

## File Structure

| File | Change |
|------|--------|
| `app/main.py` | Add `GET /log` route; change `GET /` to serve `dashboard.html` |
| `app/static/dashboard.html` | Create — new home page with stats, CTA, recent workouts |
| `app/static/index.html` | Add `← GymLog` back link pointing to `/` |

---

### Task 1: Register `/log` route and update `/` in main.py

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add `/log` route and update `/`**

Open `app/main.py`. The file currently contains:

```python
@app.get("/workouts")
def workouts_page():
    return FileResponse("app/static/workouts.html")

@app.get("/workout/{session_id}")
def workout_page(session_id: int):
    return FileResponse("app/static/workout.html")

@app.get("/exercise/{exercise_id}")
def exercise_page(exercise_id: int):
    return FileResponse("app/static/exercise.html")
```

And at the bottom:

```python
@app.get("/")
def index():
    return FileResponse("app/static/index.html")
```

Make two changes:

1. Add a `/log` route immediately after the existing page routes (before `app.include_router`):

```python
@app.get("/log")
def log_page():
    return FileResponse("app/static/index.html")
```

2. Update the `/` handler to serve `dashboard.html`:

```python
@app.get("/")
def index():
    return FileResponse("app/static/dashboard.html")
```

- [ ] **Step 2: Verify routes are in the right order**

Page routes must be registered before `app.include_router()` — FastAPI matches in registration order. Confirm that both `/log` and `/` handlers appear before the `app.include_router(router, prefix="/api")` lines in the file.

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add /log route and update / to serve dashboard"
```

---

### Task 2: Create dashboard.html

**Files:**
- Create: `app/static/dashboard.html`

- [ ] **Step 1: Create the file with this complete content**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GymLog</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #0f0f0f;
      color: #f0f0f0;
      font-family: system-ui, sans-serif;
      padding: 24px 16px 48px;
      max-width: 520px;
      margin: 0 auto;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
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
      cursor: pointer;
    }
    .btn-secondary:hover { border-color: #555; color: #ccc; }

    /* Stats bar */
    .stats-bar {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
    }

    .stat {
      flex: 1;
      background: #1a1a1a;
      border: 1px solid #2a2a2a;
      border-radius: 10px;
      padding: 16px 12px;
      text-align: center;
    }

    .stat-value {
      font-size: 1.6rem;
      font-weight: 700;
      color: #f0f0f0;
      line-height: 1;
      margin-bottom: 6px;
    }

    .stat-label {
      font-size: 0.72rem;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    /* Log Workout CTA */
    .btn-log {
      display: block;
      background: #f0f0f0;
      color: #0f0f0f;
      border: none;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 600;
      padding: 16px;
      width: 100%;
      text-align: center;
      text-decoration: none;
      cursor: pointer;
      margin-bottom: 32px;
    }
    .btn-log:hover { background: #ccc; }

    /* Recent workouts */
    .section-title {
      font-size: 0.72rem;
      color: #444;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }

    .session-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 14px;
      background: #1a1a1a;
      border: 1px solid #2a2a2a;
      border-radius: 8px;
      margin-bottom: 8px;
      text-decoration: none;
      color: inherit;
    }
    .session-row:hover { border-color: #3a3a3a; background: #1e1e1e; }

    .session-row-date { font-size: 0.9rem; color: #ccc; }
    .session-row-meta { font-size: 0.78rem; color: #555; margin-top: 2px; }
    .session-row-arrow { color: #333; font-size: 1rem; }
    .session-row:hover .session-row-arrow { color: #666; }

    .empty-state {
      text-align: center;
      color: #444;
      font-size: 0.9rem;
      padding: 32px 0;
    }

    #loading { color: #555; font-size: 0.9rem; padding: 20px 0; }
  </style>
</head>
<body>
  <div class="page-header">
    <h1>GymLog</h1>
    <a href="/workouts" class="btn-secondary">Calendar</a>
  </div>

  <div id="loading">Loading…</div>

  <div id="content" style="display:none">
    <div class="stats-bar">
      <div class="stat">
        <div class="stat-value" id="stat-total">0</div>
        <div class="stat-label">Total</div>
      </div>
      <div class="stat">
        <div class="stat-value" id="stat-week">0</div>
        <div class="stat-label">This Week</div>
      </div>
      <div class="stat">
        <div class="stat-value" id="stat-streak">0</div>
        <div class="stat-label">Day Streak</div>
      </div>
    </div>

    <a href="/log" class="btn-log">Log Workout</a>

    <p class="section-title">Recent Workouts</p>
    <div id="recent-list"></div>
  </div>

  <script>
    function toLocalKey(date) {
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    }

    function getWeekStart() {
      const now = new Date();
      const day = now.getDay(); // 0 = Sunday
      const diff = day === 0 ? 6 : day - 1; // days since Monday
      const monday = new Date(now);
      monday.setDate(now.getDate() - diff);
      monday.setHours(0, 0, 0, 0);
      return monday;
    }

    function computeStats(sessions) {
      const total = sessions.length;

      const weekStart = getWeekStart();
      const thisWeek = sessions.filter(s => new Date(s.logged_at) >= weekStart).length;

      const loggedDates = new Set(sessions.map(s => toLocalKey(new Date(s.logged_at))));
      let streak = 0;
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      for (let i = 0; i < 365; i++) {
        const d = new Date(today);
        d.setDate(today.getDate() - i);
        if (loggedDates.has(toLocalKey(d))) {
          streak++;
        } else {
          break;
        }
      }

      return { total, thisWeek, streak };
    }

    function renderRecent(sessions) {
      const list = document.getElementById('recent-list');
      if (sessions.length === 0) {
        list.innerHTML = '<div class="empty-state">No workouts logged yet.<br>Hit "Log Workout" to get started.</div>';
        return;
      }
      list.innerHTML = sessions.slice(0, 5).map(s => {
        const date = new Date(s.logged_at);
        const dateStr = date.toLocaleDateString('en-US', {
          weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
        });
        const timeStr = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        const meta = `${s.exercises_logged} exercise${s.exercises_logged !== 1 ? 's' : ''} · ${timeStr}`;
        return `<a class="session-row" href="/workout/${s.session_id}">
          <div>
            <div class="session-row-date">${dateStr}</div>
            <div class="session-row-meta">${meta}</div>
          </div>
          <span class="session-row-arrow">›</span>
        </a>`;
      }).join('');
    }

    async function init() {
      const res = await fetch('/api/workouts');
      const sessions = await res.json();

      document.getElementById('loading').style.display = 'none';
      document.getElementById('content').style.display = 'block';

      const { total, thisWeek, streak } = computeStats(sessions);
      document.getElementById('stat-total').textContent = total;
      document.getElementById('stat-week').textContent = thisWeek;
      document.getElementById('stat-streak').textContent = streak;

      renderRecent(sessions);
    }

    init();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/static/dashboard.html
git commit -m "feat: create dashboard home page with stats and recent workouts"
```

---

### Task 3: Add back link to index.html (logging form)

The logging form moves from `/` to `/log`. It currently has no back link to the home page (it was the home page). Now that it's a secondary page, it needs a `← GymLog` link.

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add back link to the page header**

The current page header in `index.html` is:

```html
<div class="page-header">
  <h1>GymLog</h1>
  <div style="display:flex;gap:8px;">
    <a href="/workouts" class="btn-new-exercise" style="text-decoration:none;">Workouts</a>
    <button class="btn-new-exercise" onclick="toggleCreateForm()">+ New Exercise</button>
  </div>
</div>
```

Add a `← GymLog` back link immediately before the `.page-header` div:

```html
<a class="back-link" href="/">← GymLog</a>

<div class="page-header">
  <h1>GymLog</h1>
  <div style="display:flex;gap:8px;">
    <a href="/workouts" class="btn-new-exercise" style="text-decoration:none;">Workouts</a>
    <button class="btn-new-exercise" onclick="toggleCreateForm()">+ New Exercise</button>
  </div>
</div>
```

Then add the `.back-link` CSS to the `<style>` block (it's not in `index.html` yet — it exists in the other pages but not this one):

```css
.back-link {
  display: inline-block;
  color: #666;
  font-size: 0.85rem;
  text-decoration: none;
  margin-bottom: 20px;
}
.back-link:hover { color: #aaa; }
```

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html
git commit -m "feat: add back link to GymLog on logging form"
```

---

### Task 4: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Start the app**

```bash
docker compose up --build
```

- [ ] **Step 2: Verify `/` is now the dashboard**

Open `http://localhost:8000`. Confirm:
- Stats bar shows 3 stat tiles (Total, This Week, Day Streak)
- "Log Workout" button is prominent and centered
- "Recent Workouts" section appears (empty state if no data, or rows if data exists)
- "Calendar" link in header navigates to `/workouts`

- [ ] **Step 3: Verify `/log` works**

Click "Log Workout" — confirms navigation to `http://localhost:8000/log`. The full logging form renders correctly (exercise search, set inputs, submit button). Submitting a workout should still work end-to-end.

- [ ] **Step 4: Verify stats compute correctly**

Log 2 workouts (use the form). Return to `/`. Confirm:
- Total increments to 2
- This Week shows 2 (workouts are today)
- Streak shows 1 (trained today)
- Both workouts appear in Recent Workouts

- [ ] **Step 5: Verify back link on logging form**

Navigate to `/log`. Confirm `← GymLog` link appears at the top and navigates back to `/` (dashboard).

- [ ] **Step 6: Verify existing back links are unaffected**

- `/workouts` → `← GymLog` → `/` (dashboard) ✓
- `/exercise/{id}` → `← GymLog` → `/` (dashboard) ✓
- `/workout/{id}` → `← Workouts` → `/workouts` ✓
