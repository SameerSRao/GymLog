# Volume Trend Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Volume Load and Reps chart views to the exercise progression page with a pill tab row to switch between Weight, Volume, and Reps charts.

**Architecture:** Frontend-only change to `app/static/exercise.html`. All data is in the existing API response. `renderChart` is generalized to accept `(points, title, highlightIdx)` instead of a sessions array. `renderSessions` computes three datasets on load and shows only tabs with ≥2 data points.

**Tech Stack:** Vanilla JS, HTML, CSS (single file).

---

## File Structure

| File | Change |
|------|--------|
| `app/static/exercise.html` | Add tab CSS; add `#chart-tabs` HTML; generalize `renderChart`; add `showChart`, `buildTabs`; update `renderSessions` |

---

### Task 1: Add chart tab CSS and HTML

**Files:**
- Modify: `app/static/exercise.html`

- [ ] **Step 1: Add `.chart-tabs` and `.chart-tab` CSS**

In `app/static/exercise.html`, find the `<style>` block. Find:
```css
    .chart-title {
      font-size: 0.78rem;
      color: #666;
      margin-bottom: 12px;
    }
```

Replace with:
```css
    .chart-tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
    }

    .chart-tab {
      background: none;
      border: 1px solid #333;
      border-radius: 20px;
      color: #555;
      font-size: 0.75rem;
      padding: 4px 12px;
      cursor: pointer;
    }
    .chart-tab:hover { border-color: #444; color: #aaa; }
    .chart-tab.active { border-color: #5a9cf5; color: #5a9cf5; }

    .chart-title {
      font-size: 0.78rem;
      color: #666;
      margin-bottom: 12px;
    }
```

- [ ] **Step 2: Add `#chart-tabs` div to the chart section HTML**

Find:
```html
    <div id="chart-section" style="display:none" class="chart-wrap">
      <p class="chart-title" id="chart-title"></p>
      <svg id="chart" width="100%" viewBox="0 0 520 120" preserveAspectRatio="none"></svg>
    </div>
```

Replace with:
```html
    <div id="chart-section" style="display:none" class="chart-wrap">
      <div class="chart-tabs" id="chart-tabs"></div>
      <p class="chart-title" id="chart-title"></p>
      <svg id="chart" width="100%" viewBox="0 0 520 120" preserveAspectRatio="none"></svg>
    </div>
```

- [ ] **Step 3: Commit**

```bash
git add app/static/exercise.html
git commit -m "feat: add chart tab HTML and CSS to exercise progression page"
```

---

### Task 2: Generalize renderChart and wire up tab switching

**Files:**
- Modify: `app/static/exercise.html`

This task replaces the entire `<script>` block's chart-related code. Read the current script carefully — the session card rendering loop must remain unchanged.

- [ ] **Step 1: Add module-level state variables**

In `app/static/exercise.html`, find the `<script>` tag opening and the first line:
```js
    const exerciseId = window.location.pathname.split('/').filter(Boolean).pop();
```

Replace with:
```js
    const exerciseId = window.location.pathname.split('/').filter(Boolean).pop();

    let currentView = 'weight';
    let chartData = {};
```

- [ ] **Step 2: Replace `renderSessions` with the multi-chart version**

Find and replace the entire `renderSessions` function:

```js
    function renderSessions(sessions) {
      const container = document.getElementById('sessions');

      if (sessions.length === 0) {
        container.innerHTML = '<div class="empty-state">No workouts logged for this exercise yet.</div>';
        return;
      }

      // Compute all-time PR (max best_set_weight across sessions that have weight data)
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

      // Build chart datasets
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

      // Session cards (newest first)
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
```

- [ ] **Step 3: Replace `renderChart` with the generalized version**

Find and replace the entire `renderChart` function:

```js
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
```

- [ ] **Step 4: Add `showChart` and `buildTabs` functions**

Add these two functions immediately after `renderChart` (before `load()`):

```js
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
```

- [ ] **Step 5: Commit**

```bash
git add app/static/exercise.html
git commit -m "feat: add volume and reps chart tabs to exercise progression page"
```

---

### Task 3: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Start the app**

```bash
docker compose up --build
```

- [ ] **Step 2: Log at least 2 workouts for a weighted exercise**

Navigate to `http://localhost:8000/log`. Log the same exercise (e.g. Barbell Bench Press) at least twice, with different weights. For example:
- Session 1: 3 sets × 5 reps @ 135 lbs
- Session 2: 3 sets × 5 reps @ 185 lbs

- [ ] **Step 3: Open the exercise progression page**

Navigate to `/exercise/{id}` for that exercise.

Confirm:
- Three pill tabs appear: **Weight**, **Volume**, **Reps**
- Weight tab is active by default (blue border and text)
- Chart shows best set weight per session with the PR dot in gold
- PR banner still shows correctly above the chart section

- [ ] **Step 4: Switch to Volume tab**

Click **Volume**.

Confirm:
- Volume tab becomes active (blue)
- Chart title changes to `"Volume load per session (lbs)"`
- Chart plots volume values (e.g. session 1: 3×5×135 = 2025 lbs, session 2: 3×5×185 = 2775 lbs)
- No gold dot (no PR highlight on volume view)

- [ ] **Step 5: Switch to Reps tab**

Click **Reps**.

Confirm:
- Reps tab becomes active (blue)
- Chart title changes to `"Total reps per session"`
- Chart plots total reps per session (e.g. 15 reps for both sessions = flat line)
- No gold dot

- [ ] **Step 6: Verify bodyweight exercise shows only Reps tab**

Log a bodyweight exercise (e.g. Pull Up, no weight entered) for 2+ sessions. Navigate to its progression page.

Confirm:
- Only the **Reps** tab appears (Weight and Volume have no data — no tabs shown for them, and tab row is hidden when ≤1 tab qualifies)
- Actually: since only 1 view qualifies (Reps), `buildTabs` gets `views.length === 1` and renders NO tab row (`tabsEl.innerHTML = ''`). The chart still renders for Reps.
- Chart shows total reps per session
- No PR banner (no weight data)

- [ ] **Step 7: Verify single-session exercise shows no chart and no tabs**

Log one session for a new exercise. Navigate to its progression page.

Confirm:
- No chart section visible (requires ≥2 sessions per metric)
- No tab row visible
- PR banner shows if the exercise has weight data
