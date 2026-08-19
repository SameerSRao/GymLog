# Volume Trend Charts Design

**Goal:** Add Volume Load and Reps chart views to the exercise progression page, with a tab row to switch between Weight, Volume, and Reps charts.

**Architecture:** Frontend-only change to `app/static/exercise.html`. All data is already in the `GET /api/exercise/{id}/progression` response (`best_set_weight`, `volume`, and `sets[].reps`). No backend changes needed.

---

## Data

Three metric datasets, computed once in `renderSessions` after the API response is received:

| Metric | Source | Null rule |
|--------|--------|-----------|
| Weight | `s.best_set_weight` | null for bodyweight sessions |
| Volume Load | `s.volume` (Σ reps × weight per set) | null for bodyweight sessions |
| Reps | `s.sets.reduce((sum, s) => sum + s.reps, 0)` — computed client-side | always available |

A tab is only shown when ≥2 sessions have data for that metric. If only one metric qualifies (or zero), no tab row is rendered.

---

## UI — Tab Row

A row of pill buttons (`Weight` | `Volume` | `Reps`) rendered inside `.chart-wrap`, above the chart title. Only tabs whose metric has ≥2 sessions are rendered. The active tab gets a blue highlight (`color: #5a9cf5; border-color: #5a9cf5`). Inactive tabs use the default muted style.

A module-level `currentView` variable (`'weight' | 'volume' | 'reps'`) tracks the active tab and defaults to `'weight'` (falling back to `'volume'` then `'reps'` if weight has <2 sessions).

Clicking a tab sets `currentView` and calls the chart renderer with the appropriate dataset.

---

## Chart Function — `renderChart(points, title, highlightIdx)`

Generalized to accept:
- `points`: `[{ value: number, date: string }]` — pre-computed per-metric array
- `title`: string displayed above the SVG (e.g. `"Best set weight per session"`, `"Volume load per session"`, `"Total reps per session"`)
- `highlightIdx` (optional): index of the point to render in gold with larger radius (used only for the Weight tab's PR dot)

The SVG drawing logic (axis lines, path, dots, y-labels, date labels) is unchanged from the current implementation — only the data source changes.

---

## PR Dot

The gold PR dot applies only on the Weight tab. `renderSessions` continues to compute `prSessionId` as before. When rendering the Weight chart, it passes `highlightIdx` = the index of the PR session in the `weightPoints` array.

---

## Scope

- No new API endpoints
- No changes to session card rendering
- No animation or transition between tab views
- The PR banner above the chart section is unchanged
