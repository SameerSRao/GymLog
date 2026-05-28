# GymLog Architecture

## High-level structure

```
Browser
  │  HTTP (JSON for API, HTML for pages)
  ▼
FastAPI (Uvicorn)
  │
  ├── Page routes     → serve static HTML files
  ├── API routes      → return JSON
  │     │
  │     ├── Services  → business logic, DB queries
  │     └── Schemas   → validate in/out with Pydantic
  │
  └── SQLAlchemy ORM → SQLite (local) / Postgres (prod)
```

---

## Entry point — `main.py`

Three things happen at startup:

1. **`Base.metadata.create_all(bind=engine)`** — SQLAlchemy inspects all imported models and creates any tables that don't exist yet. Additive only — never drops or modifies existing tables.

2. **`seed_exercises(db)`** — checks if the exercises table is empty and if so, reads `exercises.json`, collapses muscle name aliases, and populates `muscle_groups`, `exercises`, and `exercise_muscle_groups`. Idempotent — skips if data already exists.

3. **Route registration** — page routes are registered directly on `app` *before* `include_router()`. FastAPI matches routes in registration order, so `/exercise/{id}` as a page route must be registered first or it would be shadowed by the API router's sub-paths.

```python
@app.get("/exercise/{exercise_id}")   # registered first → wins
def exercise_page(...): ...

app.include_router(exercise_router, prefix="/api")  # /api/exercise/{id}/info, etc.
```

---

## Database layer

**Two databases depending on environment:**
- Local dev: SQLite at `data/gymlog.db`, mounted as a Docker volume so data persists across container restarts
- Production: Postgres via `DATABASE_URL` env var

The ORM layer is identical for both — SQLAlchemy handles the dialect difference. The only driver difference is `psycopg2-binary` for Postgres.

**`database.py` exports three things everything else depends on:**
- `Base` — declarative base class all models inherit from
- `engine` — the SQLAlchemy connection pool
- `get_db()` — a FastAPI dependency that yields a `Session` and closes it after each request

```python
def get_db():
    db = SessionLocal()
    try:
        yield db       # request runs here
    finally:
        db.close()     # always cleaned up
```

---

## Models — `models.py`

Five tables, three relationships:

```
MuscleGroup ◄──────────────────────────────► ExerciseDef
              exercise_muscle_groups (join)
                                                   │
                                                   │ one-to-many
                                                   ▼
Workout ◄──────────────────────────────────── Exercise (exercise_sets)
          one-to-many (cascade delete)
```

**`ExerciseDef`** — the exercise catalogue. Seeded from JSON, user-extensible. Holds static info: name, equipment, target muscle string, instructions. Muscle groups are a many-to-many relationship via the join table.

**`Exercise` (exercise_sets)** — one row per set logged. Not one row per exercise — if you do 3 sets of bench press, that's 3 rows, each with `set_number`, `reps`, `weight_lbs`, and an FK to both the session and the exercise definition. This makes aggregations (volume, best weight, progression) straightforward SQL queries.

**`Workout` (workout_sessions)** — just a timestamp and an ID. All the actual workout data lives in `exercise_sets`. The session is a container.

**Cascade delete**: `Workout.sets` has `cascade="all, delete-orphan"` — deleting a workout session automatically deletes all its sets. No orphan rows.

---

## Services layer

Services contain all database logic. Routes call services; services never know about HTTP.

**`workout_service.py`** — CRUD for workout sessions. Each function takes a `db: Session` and returns ORM objects. Route handlers own the HTTP concerns (status codes, 404 raises, response shaping).

**`exercise_service.py`** — exercise catalogue queries plus the progression query. The progression query:

```python
rows = (
    db.query(Exercise, Workout.logged_at)
    .join(Workout, Exercise.session_id == Workout.id)
    .filter(Exercise.exercise_id == exercise.id)  # FK match, not string
    .order_by(Workout.logged_at.asc(), Exercise.set_number.asc())
    .all()
)
```

This returns flat rows of `(Exercise, datetime)`. The service then groups them by `session_id` in Python to build the nested `sessions → sets` structure the schema expects.

---

## Schemas — `schemas.py`

Pydantic models serve two purposes:

1. **Request validation** — FastAPI automatically parses and validates the request body before your route function runs. If `exercise_id` is missing or not an integer, FastAPI returns a 422 before your code sees it.

2. **Response serialization** — `response_model=WorkoutDetailed` tells FastAPI to filter the returned data through that schema. Extra fields on the ORM object are stripped; missing optional fields get their defaults.

There's a deliberate split between request and response schemas:

```python
class ExerciseLogRequest(BaseModel):   # what the client sends
    exercise_id: int
    sets: list[SetSchema]

class ExerciseSchema(BaseModel):       # what the server returns
    exercise_id: int
    name: str                          # joined from ExerciseDef
    muscle_groups: list[MuscleGroupSchema]
    sets: list[SetSchema]
```

The client only needs to send an ID. The server joins to get the full exercise data before returning it. Keeping these separate means the request schema can't accidentally expose internal data, and the response schema can include derived fields the client never sent.

---

## Route handlers — `routes.py`, `exercise_routes.py`

Routes are thin. Their job is:
1. Call a service
2. Handle the "not found" case
3. Shape the response

The one place they do real work is `_build_workout_detailed()`, which assembles the nested `WorkoutDetailed` response from flat ORM rows:

```
exercise_sets rows (flat)
  → group by exercise_id
  → for each group: join to ExerciseDef for name + muscle_groups
  → return WorkoutDetailed{ exercises: [ExerciseSchema] }
```

The `joinedload` call prevents the N+1 problem — without it, fetching a workout with 5 exercises × 3 sets = 15 sets would fire 15 individual queries to get each set's exercise name:

```python
.options(joinedload(Exercise.exercise_def).joinedload(ExerciseDef.muscle_groups))
```

---

## Frontend

No framework — plain HTML, CSS, and vanilla JS. Each page is a static `.html` file served by FastAPI's `FileResponse`. All data fetching happens client-side via `fetch()`.

**Page routing** works by having FastAPI serve the same HTML file for path-based URLs, then the JS reads `window.location.pathname` to get the ID:

```javascript
const sessionId = window.location.pathname.split('/').filter(Boolean).pop();
// → "42" from "/workout/42"
```

**State management** is local to each page — no shared state across pages, no localStorage. The exercise search page loads all 1,324 exercises once into `allExercises` and `exerciseMap` on init, then all filtering and search is done in-memory in the browser.

**The exercise search dropdown** is a custom combobox — a text input + absolutely positioned div — rather than a native `<select>` or `<datalist>` because native elements don't support rich item display (name + equipment + muscle tags per row) or per-block multi-select filters.

---

## Data flow — logging a workout

```
User selects "Barbell Bench Press" from dropdown
  → JS stores exercise_id=42 in input's data-exerciseId attribute

User adds 3 sets, hits "Log Workout"
  → submitWorkout() builds: { exercises: [{ exercise_id: 42, sets: [...] }] }
  → POST /api/workouts

FastAPI → create_workout() route
  → log_workout(db, workout) service
      → INSERT workout_sessions → get session.id
      → INSERT exercise_sets (exercise_id=42, set_number=1, reps=6, weight=155)
      → INSERT exercise_sets (exercise_id=42, set_number=2, ...)
      → INSERT exercise_sets (exercise_id=42, set_number=3, ...)
      → commit
  → return WorkoutResponse { session_id, logged_at, exercises_logged, sets_logged }

Browser receives response
  → shows toast "Logged! 1 exercise, 3 sets"
  → shows "View workout → /workout/7"
```

---

## Data flow — viewing progression

```
User navigates to /exercise/42

exercise.html JS:
  → fetch /api/exercise/42/info        → name, equipment, muscle_groups, instructions
  → fetch /api/exercise/42/progression → sessions with sets, volume, best weight

get_exercise_progression(db, 42):
  → JOIN exercise_sets ON exercise_id=42 + workout_sessions
  → returns flat rows ordered by date asc, set_number asc
  → Python groups by session_id
  → computes volume (Σ reps × weight) and best_set_weight per session
  → returns ExerciseProgressionSchema

Browser renders:
  → equipment + muscle group tags
  → SVG line chart of best_set_weight over sessions
  → session cards newest-first
```
