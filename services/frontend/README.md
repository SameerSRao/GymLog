# Frontend Service

nginx serving static HTML/CSS/JS pages. No server-side rendering — pages are plain HTML files that fetch their own data via `fetch()`. nginx also proxies `/api/chat` to the chat service and all other `/api/*` to the API service.

---

## How It Works

```
Browser requests /workouts
  │
  ▼
nginx
  ├── Serves /usr/share/nginx/html/static/workouts.html
  └── (page's JS then calls /api/workouts via fetch())

Browser calls fetch('/api/workouts')
  │
  ▼
nginx location /api/
  └── Proxies to http://api:8000

Browser calls fetch('/api/chat') for SSE
  │
  ▼
nginx location /api/chat
  └── Proxies to http://chat:8000 (with proxy_buffering off for streaming)
```

---

## nginx Config (`nginx.conf.template`)

The Dockerfile runs `envsubst` at startup to substitute `${PORT}`, `${API_HOST}`, `${API_PORT}`, `${CHAT_HOST}`, `${CHAT_PORT}` into the template, producing the live nginx config.

**Routing rules (in priority order):**

| Pattern | Destination |
|---------|-------------|
| `/api/chat` | Proxy to chat service; `proxy_buffering off` for SSE |
| `/api/` | Proxy to API service |
| `/static/` | Served directly with 1-hour cache |
| `= /` | `static/dashboard.html` |
| `= /workouts` | `static/workouts.html` |
| `= /log` | `static/log.html` |
| `= /exercises` | `static/exercises.html` |
| `= /routines` | `static/routines.html` |
| `= /login` | `static/login.html` |
| `= /register` | `static/register.html` |
| `= /import` | `static/import.html` |
| `~ ^/workout/[0-9]+$` | `static/workout.html` |
| `~ ^/exercise/[0-9]+$` | `static/exercise.html` |
| `= /health` | Returns `200 ok` (no access log) |

The `/workout/{id}` and `/exercise/{id}` patterns serve the same HTML file for any numeric ID. The page's JS reads the ID from `window.location.pathname`.

---

## Shared Auth (`src/auth.js`)

Loaded by every page. Provides a global IIFE (immediately-invoked function expression) that exposes these window functions:

**`checkAuth()`** — checks for `access_token` in `localStorage`. Redirects to `/login` if absent. Call at the top of every page's init.

**`authFetch(url, options)`** — wrapper around `fetch()` that automatically adds `Authorization: Bearer <token>`. If the response is `401`, removes the token from `localStorage` and redirects to `/login`.

**`logout()`** — clears token from `localStorage` and redirects to `/login`.

**`getTokenPayload()`** — decodes the JWT payload (base64 decode of the middle part). Returns `null` on failure.

**`getUsername()`** — returns the `username` claim from the token.

**`isAdmin()`** — returns the `is_admin` claim.

**`isPremium()`** — returns the `is_premium` claim.

**`isDemo()`** — returns the `is_demo` claim. Pages use this to hide write controls for demo accounts.

**`getCurrentUserId()`** — returns `sub` claim as an integer.

---

## Pages

### `dashboard.html` — `/`

Calls three endpoints on init:
- `GET /api/workouts` — to count total sessions
- `GET /api/workouts?year=&month=` — for recent workouts list
- Computes stats client-side (total sets, total volume from exercises — or shows a loading state)

Shows:
- Summary stats bar (total workouts, this month's count)
- Recent workouts list with date and set count, linking to `/workout/{id}`
- Quick nav links to log, workouts, exercises, routines

**AI chat panel** (visible to premium/admin users only — checked via `isPremium()` and `isAdmin()`):
- Full conversation UI with a scrollable message history
- Sends `POST /api/chat` with the full `messages` array on each submit
- Reads the SSE stream, appending text chunks to the last assistant message as they arrive
- Sends `local_time` as `new Date().toISOString()` so the AI can timestamp workouts correctly

---

### `login.html` — `/login`

Does not call `checkAuth()`. Shows a username/password form.

On submit: `POST /api/auth/login`. On success, stores the `access_token` in `localStorage` and redirects to `/`.

Also shows a "Try Demo" button that calls `GET /api/auth/demo` and does the same redirect.

---

### `register.html` — `/register`

Does not call `checkAuth()`. Username, password, and invite code form.

On submit: `POST /api/auth/register`. On success, stores the token and redirects to `/`.

---

### `log.html` — `/log`

The most complex page. On init: loads all exercises via `GET /api/exercises` into memory (`allExercises` array + `exerciseMap` by ID). Loads routines via `GET /api/routines`.

**Exercise search combobox:** A custom-built combobox (plain text input + absolutely-positioned results div) rather than a `<select>` or `<datalist>`. Reasons:
1. Needs rich per-row display: exercise name + equipment badge + muscle group tags.
2. Token-based search: splits query into words and requires all words to match somewhere in the name ("weighted dip" matches "Weighted Tricep Dip").
3. Per-block multi-select muscle group and equipment filters (with their own search and clear controls).

**State per exercise block:**
- Selected exercise ID (stored in a `data-exercise-id` attribute)
- Sets list (each row: reps input + weight input + remove button)
- Muscle/equipment filter state

**"Load routine" button:** fetches `GET /api/routine/{id}` and pre-populates exercise blocks with the routine's exercises and set counts. User fills in the actual weights.

**Date picker:** allows backdating the workout. Defaults to current time.

**Submit:** builds `{ exercises: [{exercise_id, sets}], notes, logged_at }` and posts to `POST /api/workouts`. On success shows a "View workout →" link to the new session.

**"New Exercise" form:** inline form to create a custom exercise. Loads muscle groups via `GET /api/muscle-groups` for the checkboxes. Posts to `POST /api/exercises`, then refreshes the exercise list.

---

### `workouts.html` — `/workouts`

**Calendar view:**
- Tracks current `year` and `month` in JS state.
- On month change: `GET /api/workouts?year=&month=` to get that month's sessions.
- Builds an HTML calendar grid. Days with sessions get a green highlight.
- Days with multiple sessions show dot indicators; clicking opens an inline popup listing each session with a link.

**Recent workouts list:** `GET /api/workouts` (no filter) for a flat list, newest first. Shows date, time, exercise count, set count, links to `/workout/{id}`.

---

### `workout.html` — `/workout/{id}`

Reads session ID from `window.location.pathname.split('/').pop()`.

On init: `GET /api/workout/{session_id}`.

Shows:
- Date and time header
- For each exercise: name (linking to `/exercise/{id}`), muscle group tags, sets table with reps and weight, volume total, best set weight
- Delete button: confirmation modal → `DELETE /api/workout/{session_id}` → redirect to `/workouts`
- Edit button: opens an inline edit form (same exercise/set UI as log.html) → `PUT /api/workout/{session_id}`

---

### `exercises.html` — `/exercises`

On init: loads all exercises into `allExercises` and `exerciseMap`. Loads muscle groups for filter UI.

**Search:** client-side token matching (same algorithm as log.html combobox) against the in-memory array. No API calls on each keystroke.

**Filters:** multi-select muscle group and equipment dropdowns, applied client-side.

**Per-exercise actions:**
- "Edit" — inline form: name, equipment, muscle group checkboxes. Calls `PUT /api/exercise/{id}`. Visible only for exercises you own or if `isAdmin()`.
- "Delete" — confirmation → `DELETE /api/exercise/{id}`. 409 if the exercise has logged history (shown as a message, not an error). Same visibility rules.

**"New Exercise" button** — same as in log.html: inline form, muscle group checkboxes, `POST /api/exercises`.

---

### `exercise.html` — `/exercise/{id}`

Reads exercise ID from pathname.

On init, fires two requests in parallel:
- `GET /api/exercise/{id}/info` — name, equipment, instructions, muscle groups
- `GET /api/exercise/{id}/progression` — per-session history

Shows:
- Exercise name, equipment badge, muscle group tags
- Collapsible "How to perform" section (if instructions exist)
- Line chart of best-set weight over sessions (rendered as an SVG, shown only if ≥2 sessions with weight data exist)
- Session cards newest-first: sets table, volume, best weight

---

### `routines.html` — `/routines`

On init: `GET /api/routines` for the summary list.

For each routine:
- Expand/collapse to reveal exercise list (fetches `GET /api/routine/{id}` on first expand)
- Edit button: inline form with name field and re-orderable exercise list (exercise search + set count per row). Saves via `PUT /api/routine/{id}`.
- Delete button: confirmation → `DELETE /api/routine/{id}`.

**"New Routine" form:** name field + add-exercise rows (same combobox as log.html). Saves via `POST /api/routines`.

---

### `import.html` — `/import`

Accepts a JSON array pasted into a textarea or uploaded as a file. Expected format:

```json
[
  {
    "logged_at": "2026-01-15T09:00:00",
    "exercises": [
      {
        "exercise_id": 42,
        "sets": [
          { "reps": 5, "weight_lbs": 100 }
        ]
      }
    ]
  }
]
```

On submit: `POST /api/workouts/import`. Shows result: sessions created, sets created, and any skipped sessions with their error messages.

---

## No Framework, No Build Step

The frontend intentionally uses no JavaScript framework and no bundler. Every page is a self-contained HTML file with inline `<script>` tags and `<style>` blocks.

`auth.js` is the only shared script file; it's included via a `<script src="/static/auth.js">` tag on every page.

State is local to each page — there is no shared state between pages except the JWT in `localStorage`. The exercise browser loads all 1,324 exercises once on init and keeps them in a JS array for client-side filtering; no subsequent search requests hit the server.
