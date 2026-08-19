# Personal Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the all-time personal record (PR) weight on the exercise progression page — a prominent banner plus a highlighted session card and chart dot.

**Architecture:** All changes are frontend-only in `app/static/exercise.html`. The existing `GET /api/exercise/{id}/progression` endpoint already returns `best_set_weight` per session; the PR is computed client-side as the max across all sessions. No new API endpoints needed.

**Tech Stack:** Vanilla JS, HTML, CSS. No new dependencies.

---

## File Structure

| File | Change |
|------|--------|
| `app/static/exercise.html` | Add PR banner HTML + CSS; update `renderSessions()` and `renderChart()` |

---

### Task 1: Add PR banner CSS and HTML

**Files:**
- Modify: `app/static/exercise.html`

- [ ] **Step 1: Add CSS for PR banner, PR session card, and PR badge**

In `app/static/exercise.html`, find the `<style>` block. Add these rules after the `.empty-state` rule (before `#loading`):

```css
.pr-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1a1500;
  border: 1px solid #4a3a00;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 24px;
}

.pr-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #c9a227;
  background: #2a1f00;
  border: 1px solid #4a3a00;
  border-radius: 4px;
  padding: 2px 8px;
}

.pr-value {
  font-size: 0.95rem;
  color: #e8c84a;
}

.session-card.is-pr {
  border-color: #4a3a00;
  background: #1a1500;
}

.pr-badge {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #c9a227;
  border: 1px solid #4a3a00;
  border-radius: 4px;
  padding: 2px 7px;
}
```

- [ ] **Step 2: Add PR banner HTML element**

In `app/static/exercise.html`, find this block inside `#content`:

```html
    <p class="section-title">Progress</p>
```

Insert the PR banner immediately before it:

```html
    <div id="pr-banner" style="display:none" class="pr-banner">
      <span class="pr-label">PR</span>
      <span class="pr-value" id="pr-value"></span>
    </div>

    <p class="section-title">Progress</p>
```

- [ ] **Step 3: Commit**

```bash
git add app/static/exercise.html
git commit -m "feat: add PR banner HTML and CSS to exercise page"
```

---

### Task 2: Wire up PR computation in JavaScript

**Files:**
- Modify: `app/static/exercise.html`

This task updates two functions in the `<script>` block:
1. `renderSessions(sessions)` — compute the PR, show the banner, pass `prSessionId` to chart and session cards
2. `renderChart(sessions)` — accept `prSessionId` and highlight the PR dot in gold

- [ ] **Step 1: Replace `renderSessions` with the PR-aware version**

Find and replace the entire `renderSessions` function (lines ~222–267 in the original file):

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

  // Chart: show if 2+ sessions have weight data
  if (weightSessions.length >= 2) {
    renderChart(weightSessions, prSessionId);
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

- [ ] **Step 2: Replace `renderChart` to accept and highlight the PR dot**

Find and replace the entire `renderChart` function. The only changes vs. the original are:
- Signature changes from `renderChart(sessions)` to `renderChart(sessions, prSessionId)`
- The dots loop uses gold color and larger radius for the PR point

```js
function renderChart(sessions, prSessionId) {
  const section = document.getElementById('chart-section');
  const svg = document.getElementById('chart');
  document.getElementById('chart-title').textContent = 'Best set weight per session';
  section.style.display = 'block';

  const W = 520, H = 120;
  const padL = 40, padR = 16, padT = 12, padB = 24;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const values = sessions.map(s => s.best_set_weight);
  const dates  = sessions.map(s => new Date(s.logged_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const xOf = i => padL + (i / (sessions.length - 1)) * plotW;
  const yOf = v => padT + plotH - ((v - minV) / range) * plotH;

  const pathD = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xOf(i)} ${yOf(v)}`).join(' ');

  const dotsHtml = values.map((v, i) => {
    const isPr = sessions[i].session_id === prSessionId;
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

- [ ] **Step 3: Commit**

```bash
git add app/static/exercise.html
git commit -m "feat: compute PR client-side and highlight banner, card, and chart dot"
```

---

### Task 3: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Start the app**

```bash
docker compose up --build
```

- [ ] **Step 2: Log at least 2 workouts for the same exercise with different weights**

Navigate to `http://localhost:8000/log`. Log the same exercise twice (two separate sessions), using different weights. For example:
- Session 1: Barbell Bench Press — 1 set × 5 reps @ 135 lbs
- Session 2: Barbell Bench Press — 1 set × 5 reps @ 185 lbs

- [ ] **Step 3: Open the exercise progression page**

From the workout detail page, click the exercise name to navigate to `/exercise/{id}`.

Confirm:
- Gold PR banner appears above the "Progress" section, showing `185 lbs — <date of session 2>`
- The session card for session 2 has a gold border (`is-pr` class applied) and a `PR` badge in the header
- The chart shows the session 2 dot in gold at a larger radius than the blue dots
- Session 1 card has normal styling (dark border, no badge)

- [ ] **Step 4: Verify bodyweight-only exercise has no PR banner**

Log a bodyweight exercise (e.g. Pull Up) with no weight entered. Navigate to its progression page.

Confirm: no PR banner appears (banner stays `display:none` when all `best_set_weight` values are null).

- [ ] **Step 5: Verify single-session exercise shows PR but no chart**

Log one session for a new exercise. Navigate to its progression page.

Confirm:
- PR banner appears (single session is the PR)
- Chart does NOT render (requires ≥ 2 sessions with weight data)
- Session card shows gold border and PR badge
