# GymLog Spec

## Overview
Personal gym workout tracker. Form-based web UI for logging workouts, browsing history, and tracking lift progression over time.

---

## Stack
| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI |
| ORM | SQLAlchemy |
| DB (local) | SQLite via Docker volume |
| DB (deploy) | Postgres — swap `DATABASE_URL` |
| Server | Uvicorn |
| AI | Google Gemini (`gemini-3-flash-preview`) via `google-genai` SDK |
| Auth | JWT (HS256) via `python-jose`; passwords hashed with `bcrypt` |

---

## Project Structure
```
GymLog/
├── SPEC.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── exercises.json          ← 1,324 seeded exercises (source of truth)
├── data/                   ← SQLite db (volume mounted)
└── app/
    ├── main.py             ← app setup, page routes, startup seed
    ├── context/
    │   ├── system_prompt.md  ← AI chatbot system prompt
    │   └── knowledge.md      ← fitness knowledge injected into chat context
    ├── db/
    │   ├── database.py     ← engine, SessionLocal, Base, get_db()
    │   └── seed.py         ← seeds exercises + muscle groups from exercises.json
    ├── model/
    │   └── models.py       ← ORM models
    ├── services/
    │   ├── workout_service.py
    │   ├── exercise_service.py
    │   ├── routine_service.py
    │   ├── auth_service.py ← JWT creation/validation, bcrypt password hashing
    │   ├── chat_service.py ← Gemini agentic loop with SSE streaming
    │   └── chat_tools.py   ← tool declarations + dispatch (search, log, progression)
    ├── api/
    │   ├── workout_routes.py
    │   ├── exercise_routes.py
    │   ├── routine_routes.py
    │   ├── auth_routes.py  ← POST /api/auth/login, get_current_user dependency
    │   ├── chat_routes.py  ← POST /api/chat SSE endpoint
    │   └── schemas.py      ← Pydantic request/response models
    └── static/
        ├── dashboard.html  ← home dashboard
        ├── login.html      ← login page
        ├── index.html      ← log workout page
        ├── workouts.html   ← calendar view
        ├── workout.html    ← single workout detail
        ├── exercises.html  ← exercise browser (search, filter, edit, delete)
        ├── exercise.html   ← exercise info + progression
        ├── routines.html   ← routine list (expand, edit, delete)
        └── auth.js         ← shared auth token helpers
```

---

## Database Schema

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
| name | TEXT | unique |
| equipment | TEXT | nullable — e.g. "barbell", "dumbbell" |
| target | TEXT | nullable — primary target muscle from seed data |
| instructions | TEXT | nullable — English how-to text |

### `workout_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| raw_input | TEXT | nullable |
| logged_at | DATETIME | UTC, default now |

### `exercise_sets`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| session_id | INTEGER | FK → workout_sessions.id |
| exercise_id | INTEGER | FK → exercises.id |
| set_number | INTEGER | 1-indexed |
| reps | INTEGER | |
| weight_lbs | FLOAT | nullable (bodyweight exercises) |
| logged_at | DATETIME | UTC, default now |

### `routines`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| name | TEXT | unique — e.g. "Push Day", "Full Body A" |
| created_at | DATETIME | UTC, default now |

### `routine_exercises`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| routine_id | INTEGER | FK → routines.id, cascade delete |
| exercise_id | INTEGER | FK → exercises.id |
| position | INTEGER | 1-indexed order within the routine |
| num_sets | INTEGER | default number of sets to pre-fill |

---

## Routing

### HTML pages (served by FastAPI, no prefix)
| Route | Page |
|-------|------|
| `GET /` | Dashboard |
| `GET /login` | Login |
| `GET /log` | Log workout |
| `GET /workouts` | Calendar + recent list |
| `GET /workout/{id}` | Workout detail |
| `GET /exercises` | Exercise browser — search, filter, edit, delete |
| `GET /exercise/{id}` | Exercise info + progression |
| `GET /routines` | Routine list — expand, edit, delete |

### JSON API (all under `/api`)

#### Auth
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/auth/login` | Verify password; return a 30-day JWT on success, 401 on failure |

All other `/api` routes require a `Authorization: Bearer <token>` header.

#### Chat
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/chat` | Stream an AI response over SSE; client manages conversation history |

The chat endpoint runs a Gemini agentic loop with up to 10 tool rounds. Available tools: `search_exercises`, `get_recent_workouts`, `get_exercise_progression`, `get_routines`, `log_workout`. The system prompt and fitness knowledge are injected from `app/context/`.

#### Exercises
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/exercises` | List all exercises (id, name, equipment, target, muscle_groups) |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Single exercise detail |
| PUT | `/api/exercise/{id}` | Update an exercise — partial or full; 409 on name conflict |
| DELETE | `/api/exercise/{id}` | Delete an exercise — 409 if referenced in exercise_sets |
| GET | `/api/exercise/{id}/progression` | Workout history grouped by session |

#### Workouts
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/workouts` | Log a workout session |
| GET | `/api/workouts` | List all sessions (summary) |
| GET | `/api/workout/{id}` | Session detail with full exercise + set data |
| PUT | `/api/workout/{id}` | Replace all exercises/sets for a session |
| DELETE | `/api/workout/{id}` | Delete session and all its sets |

#### Routines
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/routines` | Create a routine; 409 on name conflict |
| GET | `/api/routines` | List all routines (id, name, exercise count) |
| GET | `/api/routine/{id}` | Routine detail with ordered exercises and set counts |
| PUT | `/api/routine/{id}` | Full replace — name and all exercises; 409 on name conflict |
| DELETE | `/api/routine/{id}` | Delete routine (does not affect logged workouts) |

#### Request/response shapes

**POST `/api/workouts`**
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
  ]
}
```

**GET `/api/workout/{id}`**
```json
{
  "session_id": 1,
  "logged_at": "2026-04-28T10:30:00Z",
  "exercises": [
    {
      "exercise_id": 42,
      "name": "Barbell Bench Press",
      "muscle_groups": [
        { "id": 7, "name": "pectorals" },
        { "id": 12, "name": "shoulders" },
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

**GET `/api/exercise/{id}/progression`**
```json
{
  "exercise_id": 42,
  "exercise_name": "Barbell Bench Press",
  "sessions": [
    {
      "session_id": 1,
      "logged_at": "2026-04-21T10:00:00Z",
      "sets": [
        { "set_number": 1, "reps": 6, "weight_lbs": 155 }
      ],
      "volume": 930.0,
      "best_set_weight": 155.0
    }
  ]
}
```

---

## Pages

### `/` — Dashboard
- Summary stats (total workouts, total sets, total volume)
- Recent workouts list with date and exercise count
- Quick links to log, workouts, exercises, routines
- AI chat panel: send messages to the Gemini assistant; streams responses via SSE; history kept client-side per session

### `/login` — Login
- Password form; on success stores the JWT in `localStorage` and redirects to `/`
- All other pages redirect here if no valid token is present

### `/log` — Log Workout
- Searchable exercise dropdown per block (token-based: "weighted dip" matches "weighted tricep dip")
- Per-block multi-select filters for muscle group and equipment (with search + clear)
- Tags show equipment + muscle groups on selection, with a link to the exercise's progression page
- Add multiple exercises, add/remove sets per exercise
- Submit → `POST /api/workouts`, shows "View workout →" link after success
- "New Exercise" form to create custom exercises with muscle group checkboxes
- Link to `/workouts` in the header

### `/workouts` — Calendar
- Month calendar, days with workouts highlighted green
- Days with multiple workouts show dot indicators; clicking opens a picker popup
- Recent workouts list below (date, time, exercise count)
- Prev/next month navigation

### `/workout/{id}` — Workout Detail
- Date, exercise count, set count
- Per exercise: name, full muscle group tags, sets table, volume + best weight summary
- "View progression →" link per exercise → `/exercise/{id}`
- Delete button with confirmation modal

### `/exercise/{id}` — Exercise Detail
- Name, equipment tag, muscle group tags
- Collapsible "How to perform" instructions
- Line chart of best set weight over sessions (shown once ≥2 sessions exist)
- Session cards newest-first: sets, volume, best weight

---

## Seeding

On startup, `seed.py` checks if the exercises table is empty. If so:
- Reads `exercises.json` (1,324 exercises)
- Collapses muscle name aliases (e.g. abdominals→abs, quadriceps→quads, trapezius→traps, deltoids→delts, latissimus dorsi→lats)
- Creates 45 canonical `MuscleGroup` records
- Creates `ExerciseDef` records linked to their muscle groups via the join table
- Stores equipment, target muscle, and English instructions per exercise

Seeding is idempotent — skipped if exercises already exist.

---

## What's Not Built Yet

| Feature | Notes |
|---------|-------|
| Edit workout UI | PUT endpoint exists, no frontend |
| Personal records | No PR detection or highlighting |
| Workout notes | No free-text notes per session |
| Volume / rep trend charts | Progression page only charts best weight |
| Multi-user support | Single user (admin password) only |
| SMS via Twilio | Was in original spec, deprioritized |
| Weight tracking | Was in original spec, deprioritized |
