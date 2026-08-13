# GymLog

Personal gym workout tracker. Log workouts, browse history on a calendar, and track lift progression over time.

---

## Features

- **Log workouts** — searchable exercise dropdown with token-based search ("weighted dip" finds "weighted tricep dip"), per-block muscle group and equipment filters, add multiple exercises and sets per session
- **AI assistant** — chat with a Gemini-powered coach that can search exercises, review your progression, list routines, and log workouts on your behalf
- **Exercise library** — 1,324 seeded exercises with muscle groups, equipment, and instructions; create and edit custom exercises
- **Workout calendar** — month view with days highlighted when you trained, multi-workout days show a picker
- **Progression tracking** — per-exercise history with volume, best set weight, and a line chart over time
- **Workout detail** — full set breakdown per session with links to each exercise's progression page
- **Routines** — save and reuse exercise templates; load a routine to pre-fill the log form
- **Batch import** — POST a list of historical sessions at once for data migration
- **Demo mode** — read-only demo account with pre-seeded workout history; no signup required

---

## Architecture

The app is a **monorepo with three Docker services** that compose into a single stack:

```
Browser
   │  HTTP :8000
   ▼
nginx (frontend service)
   ├── serves static HTML/CSS/JS pages
   ├── /api/chat/* → proxies to chat service :8000
   └── /api/*      → proxies to API service :8000

API service (FastAPI + SQLAlchemy)
   └── SQLite (local) / Postgres (production)

Chat service (FastAPI + Gemini)
   └── calls API service over HTTP using the user's JWT
```

**Key design decisions:**

- `exercise_sets` stores one row **per set**, not per exercise. Three sets of bench press = 3 rows. This makes volume and progression queries simple SQL aggregations.
- `workout_sessions` is just a timestamp container — all actual data lives in `exercise_sets`.
- Cascade delete on `Workout.sets` — deleting a session auto-deletes all its sets.
- The chat service never touches the database directly; it proxies all data operations through the API service's REST endpoints using the user's Bearer token.
- Custom exercises have a `user_id` set; seeded exercises have `user_id = NULL`. The exercises list endpoint returns both globals and the caller's own.

See the service-level READMEs for full details:
- [`services/api/README.md`](services/api/README.md) — database schema, every endpoint, file-by-file breakdown
- [`services/chat/README.md`](services/chat/README.md) — AI tool loop, every tool, how Gemini is used
- [`services/frontend/README.md`](services/frontend/README.md) — every page, nginx routing, auth flow

---

## Running Locally

```bash
docker compose up --build
```

Open `http://localhost:8000`. The database is seeded with 1,324 exercises automatically on first run.

To reset the database:

```bash
rm data/gymlog.db
docker compose down && docker compose up --build
```

For local development without Docker (API service only):

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

---

## Environment

Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=sqlite:////app/data/gymlog.db   # local SQLite
DATABASE_URL=postgresql://...                # production Postgres

JWT_SECRET=some-long-random-string           # signs all tokens; required
SIGNUP_CODE=your-invite-code                 # gates self-registration
GOOGLE_API_KEY=your-gemini-api-key           # powers AI chat

ENVIRONMENT=development                      # enables /docs and /redoc on API
ALLOWED_ORIGINS=http://localhost:8000        # CORS allowed origins
API_BASE_URL=http://api:8000                 # chat service → API service URL
```

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Dashboard — stats, recent workouts, AI chat |
| `/login` | Login form |
| `/register` | Self-registration (requires invite code) |
| `/log` | Log a new workout |
| `/workouts` | Calendar + recent workout list |
| `/workout/{id}` | Workout detail — sets, volume, exercise links |
| `/exercises` | Exercise browser — search, filter, edit, delete |
| `/exercise/{id}` | Exercise info, instructions, progression chart |
| `/routines` | Routine list — expand, edit, delete |
| `/import` | Batch import historical workouts |

---

## API Summary

All endpoints live under `/api`. Full request/response shapes are in [`services/api/README.md`](services/api/README.md).

### Auth

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| POST | `/api/auth/login` | No | Verify credentials; return 30-day JWT |
| POST | `/api/auth/register` | No | Create account with invite code; return JWT |
| GET | `/api/auth/demo` | No | Return JWT for the demo account |
| GET | `/api/auth/me` | Yes | Return current user's profile flags |

### Workouts

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| POST | `/api/workouts` | Yes (non-demo) | Log a workout session |
| POST | `/api/workouts/import` | Yes (non-demo) | Bulk-insert historical sessions |
| GET | `/api/workouts/count` | Yes | Total session count for current user |
| GET | `/api/workouts` | Yes | List sessions; optional `?year=&month=` and `?limit=N` |
| GET | `/api/workout/{id}` | Yes | Full detail with exercises and sets |
| PUT | `/api/workout/{id}` | Yes (non-demo) | Replace all exercises/sets |
| DELETE | `/api/workout/{id}` | Yes (non-demo) | Delete session and all sets |

### Exercises

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| GET | `/api/exercises` | Yes | List all exercises (global + caller's custom) |
| POST | `/api/exercises` | Yes (non-demo) | Create a custom exercise |
| GET | `/api/muscle-groups` | Yes | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Yes | Single exercise detail |
| PUT | `/api/exercise/{id}` | Yes (non-demo) | Partially update an exercise |
| DELETE | `/api/exercise/{id}` | Yes (non-demo) | Delete an exercise (409 if has history) |
| GET | `/api/exercise/{id}/progression` | Yes | Per-session progression history |

### Routines

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| POST | `/api/routines` | Yes (non-demo) | Create a routine |
| GET | `/api/routines` | Yes | List all routines (summary) |
| GET | `/api/routine/{id}` | Yes | Routine detail with ordered exercises |
| PUT | `/api/routine/{id}` | Yes (non-demo) | Full replace — name and exercises |
| DELETE | `/api/routine/{id}` | Yes (non-demo) | Delete routine |

### Chat

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| POST | `/api/chat` | Yes (premium/admin only) | Stream AI response over SSE |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| Database | SQLite (local) / Postgres (production) |
| Auth | JWT HS256 via `python-jose`; passwords hashed with `bcrypt` |
| AI | Google Gemini (`gemini-3-flash-preview`) via `google-genai` SDK |
| Frontend | Vanilla HTML/CSS/JS — no framework |
| Reverse proxy | nginx (serves static files; proxies `/api/*`) |
| Deploy | Docker + Docker Compose |
