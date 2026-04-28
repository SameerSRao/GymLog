# GymLog Spec

## Overview
Personal gym workout tracker. Natural language input via web UI or SMS. Claude parses input into structured data stored in a database.

---

## Current Work

**Goal:** Barebones form-based frontend accessible from a public domain, usable in the gym.

**Frontend — structured form (no NL yet)**
- Add multiple exercises per workout (dynamic rows)
- Per exercise: name, muscle group, sets (reps + optional weight)
- Submit → `POST /workouts`
- Mobile-friendly, minimal UI
- Served by FastAPI at `GET /`

**Deployment**
- Host on Railway (Docker-native, connects to GitHub repo, auto-deploys)
- Swap SQLite → Railway Postgres (avoids persistent volume complexity)
- Public URL provided by Railway on deploy

**Changes needed**
- `app/static/index.html` — the form UI
- FastAPI serves static files at `/`
- `DATABASE_URL` env var on Railway points to Postgres
- `requirements.txt` — add `psycopg2-binary` for Postgres driver

---

## Stack
| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI |
| ORM | SQLAlchemy |
| DB (local) | SQLite via Docker volume |
| DB (deploy) | Postgres — swap `DATABASE_URL` |
| NLP | Claude API |
| Server | Uvicorn |

---

## Project Structure
```
GymLog/
├── SPEC.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── .env.example
├── data/               ← SQLite db lives here (volume mounted)
└── app/
    ├── main.py
    ├── db/
    │   └── database.py ← engine, SessionLocal, Base, get_db()
    ├── model/
    │   └── models.py   ← ORM models
    ├── services/       ← DB read/write logic
    │   └── workout_service.py
    └── api/
        ├── routes.py   ← route handlers
        └── schemas.py  ← Pydantic request/response models
```

---

## Database Schema

### `workout_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| raw_input | TEXT | nullable — stores original NL message |
| logged_at | DATETIME | UTC timestamp, default now |

### `exercise_sets`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| session_id | INTEGER | foreign key → workout_sessions.id |
| exercise_name | TEXT | e.g. "bench press" |
| muscle_group | TEXT | e.g. "chest" |
| set_number | INTEGER | 1-indexed |
| reps | INTEGER | per set — variable across sets |
| weight_lbs | FLOAT | nullable (bodyweight exercises) |
| logged_at | DATETIME | UTC timestamp, default now |

### `weight_logs` *(Phase 2)*
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| weight_lbs | FLOAT | |
| logged_at | DATETIME | UTC timestamp, default now |

---

## API

### Current

#### `POST /workouts`
Log a workout session.

**Request**
```json
{
  "exercises": [
    {
      "name": "bench press",
      "muscle_group": "chest",
      "sets": [
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 6, "weight_lbs": 155 },
        { "reps": 5, "weight_lbs": 155 }
      ]
    },
    {
      "name": "pull ups",
      "muscle_group": "back",
      "sets": [
        { "reps": 10 },
        { "reps": 9 }
      ]
    }
  ]
}
```

**Response**
```json
{
  "session_id": 1,
  "logged_at": "2026-04-28T10:30:00Z",
  "exercises_logged": 2,
  "sets_logged": 5
}
```

#### `GET /workouts`
List all sessions (summary).

#### `GET /workout/{session_id}`
Fetch one session with full exercise detail.

#### `PUT /workout/{session_id}`
Full replace — swaps all exercises/sets for a session.

#### `DELETE /workout/{session_id}`
Delete a session and all its sets.

---

### Phase 1 — NL + Web UI

#### `POST /chat`
Accepts a free-text message, returns a natural language response.

**Request**
```json
{ "message": "did upper: bench 155 6,6,5; pull ups 10,9,10" }
```

**Response**
```json
{ "reply": "Logged! Bench press 155 lbs — 3 sets (6,6,5). Pull ups — 3 sets (10,9,10)." }
```

**Flow:**
1. Message → Claude with system prompt
2. Claude returns structured JSON (`intent` + `data`)
3. Backend calls existing service functions
4. Claude generates a friendly confirmation
5. `raw_input` stored on the workout session

#### `GET /` — Web chat UI
Mobile-friendly single-page chat interface served by FastAPI.

---

### Phase 2 — Weight Tracking

#### `POST /log/weight`
```json
{ "weight_lbs": 145 }
```

NL trigger: *"weighed in at 145"*

---

### Phase 3 — SMS

#### `POST /sms`
Twilio webhook. Same NL pipeline as `/chat`.

---

## Phases

| Phase | What | Status |
|-------|------|--------|
| 0 | Structured CRUD API + Docker | ✅ Done |
| 1 | Claude NL parsing + web chat UI | Next |
| 2 | Weight tracking | Backlog |
| 3 | SMS via Twilio | Backlog |
