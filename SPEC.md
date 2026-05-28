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
    ├── db/
    │   ├── database.py     ← engine, SessionLocal, Base, get_db()
    │   └── seed.py         ← seeds exercises + muscle groups from exercises.json
    ├── model/
    │   └── models.py       ← ORM models
    ├── services/
    │   ├── workout_service.py
    │   └── exercise_service.py
    ├── api/
    │   ├── routes.py       ← workout route handlers
    │   ├── exercise_routes.py
    │   └── schemas.py      ← Pydantic request/response models
    └── static/
        ├── index.html      ← log workout page
        ├── workouts.html   ← calendar view
        ├── workout.html    ← single workout detail
        └── exercise.html   ← exercise info + progression
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

---

## Routing

### HTML pages (served by FastAPI, no prefix)
| Route | Page |
|-------|------|
| `GET /` | Log workout |
| `GET /workouts` | Calendar + recent list |
| `GET /workout/{id}` | Workout detail |
| `GET /exercise/{id}` | Exercise info + progression |

### JSON API (all under `/api`)

#### Exercises
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/exercises` | List all exercises (id, name, equipment, target, muscle_groups) |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Single exercise detail |
| GET | `/api/exercise/{id}/progression` | Workout history grouped by session |

#### Workouts
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/workouts` | Log a workout session |
| GET | `/api/workouts` | List all sessions (summary) |
| GET | `/api/workout/{id}` | Session detail with full exercise + set data |
| PUT | `/api/workout/{id}` | Replace all exercises/sets for a session |
| DELETE | `/api/workout/{id}` | Delete session and all its sets |

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

### `/` — Log Workout
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
| Exercise browser | No page to browse/search all exercises outside of logging |
| Volume / rep trend charts | Progression page only charts best weight |
| Auth / multi-user | Single user only |
| Natural language input | Was in original spec, deprioritized |
| SMS via Twilio | Was in original spec, deprioritized |
| Weight tracking | Was in original spec, deprioritized |
