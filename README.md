# GymLog

Personal gym workout tracker. Log workouts, browse history on a calendar, and track lift progression over time.

---

## Features

- **Log workouts** — searchable exercise dropdown with token-based search ("weighted dip" finds "weighted tricep dip"), per-block muscle group and equipment filters, add multiple exercises and sets per session
- **AI assistant** — chat with a Gemini-powered coach; can search exercises, review progression, list routines, and log workouts on your behalf
- **Exercise library** — 1,324 seeded exercises with muscle groups, equipment, and instructions; create custom exercises
- **Workout calendar** — month view with days highlighted when you trained, multi-workout days show a picker
- **Progression tracking** — per-exercise history with volume, best set weight, and a line chart over time
- **Workout detail** — full set breakdown per session with links to each exercise's progression page
- **Routines** — save and reuse exercise templates; load a routine to pre-fill the log form

---

## Running Locally

```bash
docker compose up --build
```

Open `http://localhost:8000`

The database is seeded automatically on first startup (1,324 exercises). Subsequent starts skip seeding.

To reset the database:

```bash
rm data/gymlog.db
docker compose down && docker compose up --build
```

---

## Stack

- **Backend** — Python + FastAPI + Uvicorn
- **ORM** — SQLAlchemy
- **Database** — SQLite (local) / Postgres (production)
- **Frontend** — Vanilla HTML/CSS/JS, no framework
- **AI** — Google Gemini (`gemini-3-flash-preview`) via `google-genai` SDK
- **Auth** — JWT (HS256) via `python-jose`; single-user password auth
- **Deploy** — Docker

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Dashboard — stats, recent workouts, AI chat |
| `/login` | Login |
| `/log` | Log a workout |
| `/workouts` | Calendar + recent workout list |
| `/workout/{id}` | Workout detail with sets, volume, exercise links |
| `/exercises` | Exercise browser — search, filter, edit, delete |
| `/exercise/{id}` | Exercise info, instructions, progression chart |
| `/routines` | Routine list — expand, edit, delete |

---

## API

All endpoints are prefixed with `/api`. All routes except `POST /api/auth/login` require `Authorization: Bearer <token>`.

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Verify password; return a 30-day JWT |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Stream an AI response over SSE (client manages history) |

### Workouts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/workouts` | Log a workout session |
| GET | `/api/workouts` | List all sessions |
| GET | `/api/workout/{id}` | Session with full exercise + set detail |
| PUT | `/api/workout/{id}` | Replace all exercises/sets for a session |
| DELETE | `/api/workout/{id}` | Delete a session and all its sets |

### Exercises

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/exercises` | List all exercises |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Exercise detail |
| PUT | `/api/exercise/{id}` | Update an exercise (partial or full) |
| DELETE | `/api/exercise/{id}` | Delete an exercise (409 if it has logged history) |
| GET | `/api/exercise/{id}/progression` | Workout history for a lift |

### Routines

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/routines` | Create a routine; 409 on name conflict |
| GET | `/api/routines` | List all routines |
| GET | `/api/routine/{id}` | Routine detail with ordered exercises |
| PUT | `/api/routine/{id}` | Full replace — name and all exercises |
| DELETE | `/api/routine/{id}` | Delete routine (does not affect logged workouts) |

---

## Environment

Copy `.env.example` to `.env` and set:

```
DATABASE_URL=sqlite:////app/data/gymlog.db   # local
DATABASE_URL=postgresql://...                # production
ADMIN_PASSWORD=your-password
JWT_SECRET=some-long-random-string
GOOGLE_API_KEY=your-gemini-api-key
ENVIRONMENT=development                      # enables /docs and /redoc
```

---

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the system is structured, data flows, key design decisions
- [SPEC.md](SPEC.md) — full feature spec, schema reference, what's not built yet
