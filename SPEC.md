# GymLog Spec

## Overview

Personal gym workout tracker. Multi-user, invite-code-gated web app for logging workouts, browsing history on a calendar, tracking lift progression, managing exercise routines, and chatting with an AI coach.

---

## Architecture

Three Docker services compose into a single stack behind nginx:

```
GymLog/
├── docker-compose.yml          ← wires up the three services
├── exercises.json              ← 1,324 seeded exercises (source of truth)
├── data/                       ← SQLite db (volume-mounted into API container)
├── services/
│   ├── api/                    ← FastAPI backend — all data + auth
│   ├── chat/                   ← FastAPI AI chatbot (calls API over HTTP)
│   └── frontend/               ← nginx — serves static HTML, proxies /api/*
└── ruff.toml                   ← Python linter config (shared standard)
```

**Request routing:**

- Browser → nginx port 8000
- `/api/chat` → chat service port 8000
- `/api/*` → API service port 8000
- All other paths → static HTML files

---

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| DB (local) | SQLite via Docker volume |
| DB (deploy) | Postgres — swap `DATABASE_URL` |
| Auth | JWT HS256 via `python-jose`; passwords hashed with `bcrypt` |
| AI | Google Gemini (`gemini-3-flash-preview`) via `google-genai` SDK |
| Frontend | Vanilla HTML/CSS/JS — no framework |
| Proxy | nginx with env-substituted config template |

---

## API Service File Layout

```
services/api/
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── app/
│   ├── main.py                  ← app setup, startup seed, CORS, router registration
│   ├── admin.py                 ← CLI tool: python -m app.admin promote <user>
│   ├── db/
│   │   ├── database.py          ← engine, SessionLocal, Base, get_db() dependency
│   │   ├── models.py            ← all ORM models
│   │   ├── seed.py              ← idempotent exercise seed + demo user seed
│   │   └── exercises.json       ← 1,324 exercises seeded on first startup
│   ├── auth/
│   │   ├── routes.py            ← /api/auth/* endpoints + get_current_user dependency
│   │   ├── schemas.py           ← LoginRequest, RegisterRequest, TokenResponse
│   │   └── service.py           ← bcrypt hashing, JWT create/decode, user CRUD
│   ├── workouts/
│   │   ├── routes.py            ← /api/workouts and /api/workout/{id} endpoints
│   │   ├── schemas.py           ← WorkoutRequest, WorkoutResponse, WorkoutDetailed, ImportResponse
│   │   └── service.py           ← log, get, list, update, delete, import workouts
│   ├── exercises/
│   │   ├── routes.py            ← /api/exercises, /api/exercise/{id}/*, /api/muscle-groups
│   │   ├── schemas.py           ← ExerciseDefSchema, CreateExerciseSchema, ExerciseProgressionSchema
│   │   └── service.py           ← exercise CRUD, progression query
│   └── routines/
│       ├── routes.py            ← /api/routines and /api/routine/{id} endpoints
│       ├── schemas.py           ← RoutineCreate, RoutineDetail, RoutineListItem
│       └── service.py           ← routine CRUD
└── tests/
    ├── conftest.py              ← in-memory SQLite test DB, test client fixture
    ├── test_auth.py
    ├── test_workouts.py
    ├── test_exercises.py
    ├── test_routines.py
    ├── test_admin.py
    ├── test_demo.py
    ├── test_import.py
    ├── test_models.py
    └── test_seed.py
```

---

## Chat Service File Layout

```
services/chat/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py                  ← FastAPI app, /api/chat router, /health
│   ├── chat/
│   │   ├── routes.py            ← POST /api/chat — validates token, streams SSE
│   │   ├── schemas.py           ← ChatRequest (messages list + local_time)
│   │   └── service.py           ← Gemini agentic tool loop, SSE generator
│   ├── client/
│   │   └── api_client.py        ← sync httpx client for calling the API service
│   ├── context/
│   │   ├── system_prompt.md     ← GymBot persona + tool usage rules injected each request
│   │   └── knowledge.md         ← fitness knowledge base (exercise recommendations, etc.)
│   └── tools/
│       ├── __init__.py          ← TOOLS registry, execute_tool() dispatcher
│       ├── base.py              ← shared fuzzy-match helpers (_best_exercise_match, etc.)
│       ├── workouts.py          ← get_recent_workouts, log_workout, delete_workout, update_workout
│       ├── exercises.py         ← search_exercises, get_exercise_progression, create/update/delete_exercise
│       └── routines.py          ← get_routines, create_routine, update_routine, delete_routine
```

---

## Frontend File Layout

```
services/frontend/
├── Dockerfile
├── docker-entrypoint.sh         ← envsubst nginx template → /etc/nginx/conf.d/default.conf
├── nginx.conf.template          ← nginx config with ${API_HOST}, ${CHAT_HOST}, ${PORT} vars
└── src/
    ├── auth.js                  ← shared: checkAuth(), authFetch(), logout(), token helpers
    ├── dashboard.html           ← /  — stats, recent workouts, AI chat panel
    ├── login.html               ← /login
    ├── register.html            ← /register
    ├── log.html                 ← /log — log a new workout
    ├── workouts.html            ← /workouts — calendar + list
    ├── workout.html             ← /workout/{id} — session detail
    ├── exercises.html           ← /exercises — browse, search, filter, edit, delete
    ├── exercise.html            ← /exercise/{id} — detail + progression chart
    ├── routines.html            ← /routines — list, expand, edit, delete
    └── import.html              ← /import — batch import JSON
```

---

## Database Schema

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| username | TEXT | unique |
| password_hash | TEXT | bcrypt hash |
| is_admin | BOOLEAN | can edit/delete any exercise |
| is_premium | BOOLEAN | can access AI chat |
| is_demo | BOOLEAN | read-only access; write routes return 403 |
| created_at | DATETIME | UTC, default now |

### `muscle_groups`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| name | TEXT | unique — 45 canonical muscles (aliases collapsed) |

### `exercise_muscle_groups` (join table)
| Column | Type | Notes |
|--------|------|-------|
| exercise_id | INTEGER | FK → exercises.id |
| muscle_group_id | INTEGER | FK → muscle_groups.id |

### `exercises`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| name | TEXT | |
| equipment | TEXT | nullable — e.g. "barbell", "dumbbell" |
| instructions | TEXT | nullable — English how-to text |
| user_id | INTEGER | FK → users.id; NULL for seeded global exercises |

### `workout_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| raw_input | TEXT | nullable — free-text notes |
| logged_at | DATETIME | UTC, default now; can be set explicitly (batch import) |
| user_id | INTEGER | FK → users.id |

Index: `(user_id, logged_at)` — used by calendar and list queries.

### `exercise_sets`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| session_id | INTEGER | FK → workout_sessions.id |
| exercise_id | INTEGER | FK → exercises.id |
| set_number | INTEGER | 1-indexed within the session for this exercise |
| reps | INTEGER | |
| weight_lbs | FLOAT | nullable (bodyweight exercises) |
| logged_at | DATETIME | UTC, default now |

One row per set. Three sets of bench press = 3 rows. Cascade delete from `workout_sessions`.

### `routines`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| name | TEXT | unique per user |
| created_at | DATETIME | UTC, default now |
| user_id | INTEGER | FK → users.id |

### `routine_exercises`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| routine_id | INTEGER | FK → routines.id, cascade delete |
| exercise_id | INTEGER | FK → exercises.id |
| position | INTEGER | 1-indexed order within the routine |
| num_sets | INTEGER | default number of sets to pre-fill when loading the routine |

---

## Auth System

Registration is gated by a `SIGNUP_CODE` env var. Users must supply this code at `/register`. The demo user is created at startup and uses `is_demo=True` — all write endpoints return 403 for demo accounts.

JWT tokens are HS256-signed with `JWT_SECRET`, expiry 30 days. The payload includes `sub` (user ID as string), `username`, `is_admin`, `is_premium`, `is_demo`.

The `get_current_user` dependency validates the Bearer token on every protected route. The `require_not_demo` dependency additionally rejects demo accounts.

Admins (`is_admin=True`) can edit or delete any exercise, including global seeded ones. Regular users can only edit/delete exercises they created. Only premium users and admins can access the AI chat.

---

## API Endpoints — Full Reference

### Auth (`/api/auth`)

**POST `/api/auth/login`** — public

Request:
```json
{ "username": "alice", "password": "secret" }
```
Response `200`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```
Errors: `401` wrong credentials.

---

**POST `/api/auth/register`** — public

Request:
```json
{ "username": "alice", "password": "secret", "signup_code": "invite123" }
```
Response `201`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```
Errors: `400` invalid signup code, `409` username taken.

---

**GET `/api/auth/demo`** — public

Response `200`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```
Errors: `503` demo user not seeded.

---

**GET `/api/auth/me`** — Bearer required

Response `200`:
```json
{ "id": 1, "username": "alice", "is_admin": false, "is_premium": true, "is_demo": false }
```

---

### Workouts (`/api/workouts`, `/api/workout/{id}`)

All workout endpoints require a valid Bearer token. Write endpoints additionally reject demo accounts.

**POST `/api/workouts`**

Request:
```json
{
  "exercises": [
    {
      "exercise_id": 42,
      "sets": [
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 5, "weight_lbs": 155 }
      ]
    }
  ],
  "notes": "Felt strong today",
  "logged_at": "2026-06-01T10:00:00"
}
```
`notes` and `logged_at` are optional. Omit `logged_at` to use server time. `weight_lbs` is optional (bodyweight exercises).

Response `200`:
```json
{ "session_id": 7, "logged_at": "2026-06-01T10:00:00", "exercises_logged": 1, "sets_logged": 3 }
```

---

**POST `/api/workouts/import`**

Bulk-insert historical sessions. Sessions with invalid exercise IDs are skipped and reported.

Request: array of `WorkoutImportRequest` (same shape as `WorkoutRequest` but `logged_at` is required):
```json
[
  {
    "logged_at": "2026-05-01T09:00:00",
    "exercises": [{ "exercise_id": 1, "sets": [{ "reps": 5, "weight_lbs": 100 }] }]
  }
]
```
Response:
```json
{ "sessions_created": 1, "sets_created": 1, "errors": [] }
```
Error entries: `{ "index": 0, "reason": "exercise_id 999 does not exist" }`.

---

**GET `/api/workouts`**

Returns all sessions for the caller, newest first. Optional query params `year` and `month` (both required together) filter to one calendar month.

Response: array of:
```json
{ "session_id": 7, "logged_at": "2026-06-01T10:00:00", "exercises_logged": 2, "sets_logged": 6 }
```

---

**GET `/api/workout/{id}`**

Response:
```json
{
  "session_id": 7,
  "logged_at": "2026-06-01T10:00:00",
  "notes": "Felt strong today",
  "exercises": [
    {
      "exercise_id": 42,
      "name": "Barbell Bench Press",
      "muscle_groups": [
        { "id": 7, "name": "pectorals" },
        { "id": 12, "name": "delts" },
        { "id": 18, "name": "triceps" }
      ],
      "sets": [
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 5, "weight_lbs": 155 }
      ]
    }
  ]
}
```
Errors: `404` not found or not owned.

---

**PUT `/api/workout/{id}`**

Full replace — deletes all existing sets and re-inserts from the request body. Same request shape as `POST /api/workouts`. Same response shape as `GET /api/workout/{id}`.

Errors: `404` not found or not owned.

---

**DELETE `/api/workout/{id}`**

Response: `{ "deleted": 7 }`
Errors: `404` not found or not owned.

---

### Exercises

**GET `/api/exercises`**

Returns global exercises (user_id NULL) plus the caller's custom exercises, alphabetically.

Response: array of:
```json
{
  "id": 42, "name": "Barbell Bench Press", "equipment": "barbell",
  "instructions": "Lie on bench...", "user_id": null,
  "muscle_groups": [{ "id": 7, "name": "pectorals" }]
}
```

---

**POST `/api/exercises`**

Request:
```json
{ "name": "Meadows Row", "equipment": "barbell", "instructions": null, "muscle_group_ids": [3, 7] }
```
Response `201`: same shape as the list item above, with `user_id` set to the caller's ID.
Errors: `400` invalid muscle group IDs.

---

**GET `/api/muscle-groups`**

Response: array of `{ "id": 1, "name": "abs" }`, alphabetical.

---

**GET `/api/exercise/{id}/info`**

Same response shape as an exercise list item.
Errors: `404`.

---

**PUT `/api/exercise/{id}`**

Partial update — any field may be omitted to leave it unchanged.

Request:
```json
{ "name": "New Name", "equipment": "dumbbell", "instructions": "...", "muscle_group_ids": [1, 2] }
```
Response: updated exercise.
Errors: `403` not permitted (not owner and not admin), `404`, `409` name conflict.

---

**DELETE `/api/exercise/{id}`**

Response: `204 No Content`.
Errors: `403` not permitted, `404`, `409` exercise has logged sets.

---

**GET `/api/exercise/{id}/progression`**

Response:
```json
{
  "exercise_id": 42,
  "exercise_name": "Barbell Bench Press",
  "sessions": [
    {
      "session_id": 1,
      "logged_at": "2026-04-21T10:00:00",
      "sets": [
        { "set_number": 1, "reps": 6, "weight_lbs": 155 },
        { "set_number": 2, "reps": 6, "weight_lbs": 155 }
      ],
      "volume": 1860.0,
      "best_set_weight": 155.0
    }
  ]
}
```
Sessions are sorted chronologically (oldest first). Volume = sum of `reps × weight_lbs` across all sets. Bodyweight sets are excluded from volume/best_weight but included in the sets array.
Errors: `404` exercise not found.

---

### Routines

**POST `/api/routines`**

Request:
```json
{
  "name": "Push Day",
  "exercises": [
    { "exercise_id": 42, "position": 1, "num_sets": 4 },
    { "exercise_id": 55, "position": 2, "num_sets": 3 }
  ]
}
```
Response `201`:
```json
{
  "id": 3, "name": "Push Day", "created_at": "2026-06-01T12:00:00",
  "exercises": [
    { "exercise_id": 42, "name": "Barbell Bench Press", "position": 1, "num_sets": 4 },
    { "exercise_id": 55, "name": "Overhead Press", "position": 2, "num_sets": 3 }
  ]
}
```
Errors: `400` invalid exercise IDs, `409` name already taken by this user.

---

**GET `/api/routines`**

Response: array of summary items (no exercises list):
```json
[{ "id": 3, "name": "Push Day", "exercise_count": 2, "created_at": "2026-06-01T12:00:00" }]
```

---

**GET `/api/routine/{id}`**

Full detail including exercises, sorted by position.
Errors: `404`.

---

**PUT `/api/routine/{id}`**

Full replace — name and entire exercise list. Same request/response as POST.
Errors: `400`, `404`, `409`.

---

**DELETE `/api/routine/{id}`**

Response: `{ "deleted": 3 }`. Does not affect logged workout history.
Errors: `404`.

---

### Chat

**POST `/api/chat`** — Bearer required, premium/admin only, demo blocked

Proxied through nginx to the chat service.

Request:
```json
{
  "messages": [
    { "role": "user", "content": "How has my bench press been progressing?" }
  ],
  "local_time": "2026-06-01T14:30:00"
}
```
`messages` is the full conversation history (client-managed). `local_time` is optional; the AI uses it when logging workouts without an explicit timestamp.

Response: `text/event-stream` SSE.

Each chunk:
```
data: {"text": "Your bench press has been..."}\n\n
```
Final chunk:
```
data: [DONE]\n\n
```
Error chunk:
```
data: {"error": "some error message"}\n\n
```

Errors: `401` invalid token, `403` demo account or not premium.

---

## Seeding

**Exercise seed** (`seed_exercises`): Runs at startup. No-op if the exercises table is non-empty. Reads `exercises.json` (1,324 items), collapses muscle name aliases (`abdominals→abs`, `deltoids→delts`, `latissimus dorsi→lats`, `quadriceps→quads`, `trapezius→traps`), creates 45 canonical `MuscleGroup` records, then creates `ExerciseDef` records linked via the join table.

**Demo seed** (`seed_demo_data`): Runs at startup after exercise seed. Creates a `demo` user (is_demo=True) if not present. If the demo user's newest workout is older than 30 days, deletes all their old workouts and creates 8 weeks of 3×/week workout data (24 sessions, using the first 5 seeded exercises, 3 sets each, with progressive weight increases week over week).

---

## Admin CLI

Promote a user to admin or premium from inside the API container:

```bash
docker compose exec api python -m app.admin promote alice --admin
docker compose exec api python -m app.admin promote alice --premium
docker compose exec api python -m app.admin promote alice --admin --premium
```

---

## Pages

### `/` — Dashboard
Stats (total workouts, sets, volume). Recent workouts list. Quick nav links. AI chat panel (premium/admin only): streams responses via SSE, conversation history kept client-side per browser session.

### `/login` — Login
Username/password form. On success stores JWT in `localStorage` and redirects to `/`. Demo login button calls `GET /api/auth/demo` and does the same.

### `/register` — Register
Username, password, and invite code. On success stores JWT and redirects to `/`.

### `/log` — Log Workout
Searchable exercise combobox per exercise block (token-based: "weighted dip" matches "weighted tricep dip"). Per-block multi-select filters for muscle group and equipment. Tags show selected exercise's attributes with a link to its progression page. Add multiple exercises, add/remove sets per exercise. Optional date picker to backdate. Submit → `POST /api/workouts`. "Load routine" button pre-fills exercises from a saved routine.

### `/workouts` — Calendar
Month calendar; days with workouts highlighted. Multi-workout days show dot indicators; clicking opens a session picker popup. Recent workouts list below. Prev/next month navigation via `GET /api/workouts?year=&month=`.

### `/workout/{id}` — Workout Detail
Date, exercise count, set count. Per exercise: name, muscle group tags, sets table, volume + best weight. "View progression" link per exercise. Delete button with confirmation modal.

### `/exercises` — Exercise Browser
Loads all exercises once into memory on init. Client-side search and muscle/equipment filters. Inline edit and delete for exercises you own (or all, if admin). "New Exercise" form creates custom exercises via `POST /api/exercises`.

### `/exercise/{id}` — Exercise Detail
Name, equipment tag, muscle group tags. Collapsible instructions. Line chart of best-set weight over sessions (shown if ≥2 sessions). Session cards newest-first: sets table, volume, best weight.

### `/routines` — Routine Manager
List all routines. Expand to see exercise list with set counts. Edit routine inline (name + exercises). Delete routine. Create new routine.

### `/import` — Batch Import
Accepts a JSON array of session objects (same shape as `POST /api/workouts/import`). Shows import results: sessions created, sets created, any skipped sessions with reasons.
