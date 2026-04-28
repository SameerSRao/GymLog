# GymLog Spec

## Overview
Personal gym workout tracker. Natural language input via web UI or SMS. Claude parses input into structured data stored in a database.

---

## Stack
| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI |
| ORM | SQLAlchemy |
| DB (local) | SQLite via Docker volume |
| DB (deploy) | Postgres — swap `DATABASE_URL` |
| NLP | Claude API (future) |
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
    ├── services/       ← DB read/write logic (future)
    └── api/            ← route handlers (future)
```

---

## Database Schema

### `workout_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| raw_input | TEXT | nullable — original message, used when NL parsing is added |
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

---

## API

### `POST /workouts`
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
  "logged_at": "2026-04-27T10:30:00Z",
  "exercises_logged": 2,
  "sets_logged": 5
}
```

---

## Future Phases
- **Weight tracking** — separate `weight_logs` table, `POST /log/weight`
- **NL parsing** — Claude API translates free text into the structured request body above
- **SMS** — Twilio webhook, same NL pipeline
- **Queries** — natural language questions about progression, answered by Claude with DB context
