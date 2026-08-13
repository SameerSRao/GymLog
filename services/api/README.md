# API Service

FastAPI backend. Handles all data storage, business logic, and authentication. Every other service (chat, frontend) talks to this one.

---

## Running

```bash
# Via Docker Compose (recommended)
docker compose up --build

# Directly (from repo root, with venv active)
uvicorn app.main:app --reload --app-dir services/api

# Tests
cd services/api
pytest
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `sqlite:////app/data/gymlog.db` (local) or `postgresql://...` (prod) |
| `JWT_SECRET` | Yes | Long random string; signs all tokens. App refuses to start if missing. |
| `SIGNUP_CODE` | Yes | Invite code required for self-registration |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Default: `http://localhost:8000` |
| `ENVIRONMENT` | No | Set to `development` to enable `/docs` and `/redoc` |
| `TESTING` | No | Set to any value to skip table creation and seeding (used by pytest) |

---

## File-by-File Breakdown

### `app/main.py`

Entry point. Three things happen at startup (skipped when `TESTING` is set):

1. `Base.metadata.create_all(bind=engine)` — creates any tables that don't exist. Additive only, never drops columns.
2. `seed_exercises(db)` — populates exercises from `exercises.json` if the table is empty.
3. `seed_demo_data(db)` — creates the demo user and refreshes their workout history if stale.

Then CORS middleware is added with origins from `ALLOWED_ORIGINS`, and four routers are registered under `/api`:

- `auth_router` → `/api/auth/*`
- `workout_router` → `/api/workouts` and `/api/workout/*`
- `exercise_router` → `/api/exercises`, `/api/exercise/*`, `/api/muscle-groups`
- `routine_router` → `/api/routines` and `/api/routine/*`

A `GET /health` endpoint returns `{"status": "ok"}`.

---

### `app/db/database.py`

Exports three things that everything else depends on:

- `Base` — SQLAlchemy declarative base; all models inherit from it.
- `engine` — the SQLAlchemy connection pool, built from `DATABASE_URL`.
- `get_db()` — a FastAPI dependency generator. Opens a `Session`, yields it for the duration of the request, then closes it in the `finally` block. Used as `db: Session = Depends(get_db)` in every route.

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### `app/db/models.py`

All ORM models. Six tables, five model classes, one association table.

**`MuscleGroup`** (`muscle_groups` table)
A named muscle group. Has a many-to-many relationship with `ExerciseDef` via `exercise_muscle_groups`.

```
id | name
---|-------
1  | abs
2  | biceps
...
```

**`exercise_muscle_groups`** (join table, no model class)
Links exercises to their muscle groups. Composite primary key `(exercise_id, muscle_group_id)`.

**`User`** (`users` table)
A registered user account.
- `is_admin` — can edit/delete any exercise including seeded globals.
- `is_premium` — can access AI chat.
- `is_demo` — all write endpoints reject with 403.

**`ExerciseDef`** (`exercises` table)
An exercise definition. Seeded exercises have `user_id = NULL`. User-created exercises have `user_id` set to their ID. The exercises list endpoint returns both globals and the caller's own.

**`Workout`** (`workout_sessions` table)
A workout session. Just a timestamp container — all actual workout data lives in `exercise_sets`. Has a `cascade="all, delete-orphan"` relationship on `sets`, so deleting a session auto-deletes all its sets.

**`Exercise`** (`exercise_sets` table)
One set of an exercise within a session. If you log 3 sets of bench press, that creates 3 rows here, each with `set_number`, `reps`, and `weight_lbs`. This flat structure makes aggregation queries (volume, best weight, progression) straightforward.

**`Routine`** (`routines` table)
A named workout template. Name is unique per user.

**`RoutineExercise`** (`routine_exercises` table)
One exercise slot in a routine. `position` is 1-indexed ordering. `num_sets` is the default set count to pre-fill when loading the routine.

---

### `app/db/seed.py`

**`seed_exercises(db)`** — No-op if the exercises table is non-empty. Reads `exercises.json` (1,324 exercises). Collapses aliases before creating muscle groups:
- `abdominals` → `abs`
- `deltoids` → `delts`
- `latissimus dorsi` → `lats`
- `quadriceps` → `quads`
- `trapezius` → `traps`

Creates 45 canonical `MuscleGroup` rows, then `ExerciseDef` rows linked via the join table. Deduplicates by lowercased name.

**`seed_demo_data(db)`** — Creates a user with `username="demo"` and `is_demo=True` if not present. If the demo user's newest workout is older than 30 days, wipes their old workouts and re-creates 8 weeks of 3×/week sessions (24 total). Each session uses the first 5 seeded exercises, 3 sets each, weight increases by 5 lbs per week to simulate progression.

---

### `app/admin.py`

CLI tool run directly inside the container. Promotes a user to admin or premium by setting flags in the database.

```bash
docker compose exec api python -m app.admin promote alice --admin
docker compose exec api python -m app.admin promote alice --premium --admin
```

---

### `app/auth/service.py`

Stateless auth functions. No FastAPI dependencies, just pure logic.

- `hash_password(plain)` — bcrypt hash.
- `verify_password(plain, hashed)` — bcrypt check.
- `check_signup_code(code)` — compares against `SIGNUP_CODE` env var.
- `create_access_token(data, expires_delta)` — signs a JWT with `JWT_SECRET` using HS256.
- `decode_access_token(token)` — decodes and validates; raises `HTTPException 401` on failure.
- `create_user(db, username, password)` — creates and persists a `User` row.
- `get_user_by_username(db, username)` — query by username.

Token expiry is 30 days (720 hours, set in `auth/routes.py`).

---

### `app/auth/routes.py`

Auth endpoints plus two shared FastAPI dependencies used by every other router.

**Dependencies:**

`get_current_user(credentials)` — extracts and validates the Bearer token. Returns the decoded JWT payload as a dict with keys `sub` (user ID string), `username`, `is_admin`, `is_premium`, `is_demo`. Raises `401` on invalid/expired token.

`require_not_demo(current_user)` — calls `get_current_user` then rejects with `403` if `is_demo=True`. Used on all write endpoints.

**Endpoints:**

`POST /api/auth/login` — verifies username/password, returns JWT.

`POST /api/auth/register` — checks signup code, checks for username conflict, creates user, returns JWT.

`GET /api/auth/demo` — returns a JWT for the `demo` user. Used by the login page's "Try Demo" button.

`GET /api/auth/me` — returns the current user's profile. Used by the chat service to validate tokens and check premium status.

---

### `app/workouts/schemas.py`

Pydantic models for request validation and response serialization.

| Schema | Used for |
|--------|----------|
| `SetSchema` | One set: `reps` (int), `weight_lbs` (float, optional) |
| `ExerciseLogRequest` | One exercise in a request: `exercise_id` (int) + `sets` list |
| `WorkoutRequest` | Create/replace request: `exercises` list + optional `notes` + optional `logged_at` |
| `ExerciseSchema` | One exercise in a response: `exercise_id`, `name`, `muscle_groups`, `sets` |
| `WorkoutResponse` | Summary: `session_id`, `logged_at`, `exercises_logged`, `sets_logged` |
| `WorkoutDetailed` | Full detail: `session_id`, `logged_at`, `notes`, `exercises` list |
| `WorkoutImportRequest` | One session in a batch import: `logged_at` (required) + `exercises` |
| `ImportError` | One skipped session: `index` + `reason` |
| `ImportResponse` | Batch import result: `sessions_created`, `sets_created`, `errors` |

Request schemas only accept IDs (no names). Response schemas join to include names and muscle groups.

---

### `app/workouts/service.py`

All database logic for workouts. Routes call these; these functions never touch HTTP.

**`log_workout(db, workout, user_id)`** — creates a `Workout` row (with optional `logged_at` and `notes`), flushes to get the ID, then creates one `Exercise` row per set (numbered `1..N`). Commits and returns the session.

**`get_workout(db, session_id, user_id)`** — fetches by session ID and user ID. Returns `None` if not found or not owned.

**`get_all_workouts(db, user_id, year, month, limit)`** — lists sessions for the user, newest first. If both `year` and `month` are provided, filters to that calendar month. If `limit` is provided, caps the result to that many rows (applied after ordering, so you get the N most recent).

**`count_workouts(db, user_id)`** — returns total session count via `SELECT COUNT(*)`. Used by `GET /api/workouts/count` to avoid serializing rows just to count them.

**`update_workout(db, session_id, workout, user_id)`** — deletes all existing `exercise_sets` rows for the session, then re-inserts from the request. Returns `None` if not found.

**`delete_workout(db, session_id, user_id)`** — deletes the session (cascade handles sets). Returns `False` if not found.

**`build_workout_detailed(db, session)`** — used by both fetch and update to build the `WorkoutDetailed` response. Fetches all sets with a `joinedload` on `exercise_def` and `muscle_groups` (prevents N+1), groups by `exercise_id`, returns the nested structure.

**`import_workouts(db, sessions, user_id)`** — validates all exercise IDs up front in a single query, then iterates sessions. Skips any session with an invalid exercise ID and records it in `errors`. Commits all valid sessions together.

---

### `app/workouts/routes.py`

Thin HTTP handlers. Every route calls a service function, handles the 404 case, and shapes the response.

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| POST | `/api/workouts` | non-demo | `create_workout` |
| POST | `/api/workouts/import` | non-demo | `batch_import_workouts` |
| GET | `/api/workouts/count` | any | `workout_count` |
| GET | `/api/workouts` | any | `list_workouts` — optional `?year=&month=` and `?limit=N` |
| GET | `/api/workout/{session_id}` | any | `fetch_workout` |
| PUT | `/api/workout/{session_id}` | non-demo | `replace_workout` |
| DELETE | `/api/workout/{session_id}` | non-demo | `remove_workout` |

All routes on this router require `get_current_user` (set at router level). Write routes additionally call `require_not_demo` as a second dependency.

---

### `app/exercises/schemas.py`

| Schema | Used for |
|--------|----------|
| `MuscleGroupSchema` | `id` + `name` |
| `ExerciseDefSchema` | Full exercise: `id`, `name`, `equipment`, `instructions`, `user_id`, `muscle_groups` |
| `CreateExerciseSchema` | Create request: `name`, `equipment`, `instructions`, `muscle_group_ids` |
| `ExerciseUpdate` | Partial update: all fields optional |
| `SetDetail` | Progression set: `set_number`, `reps`, `weight_lbs` |
| `SessionSummary` | Progression session: `session_id`, `logged_at`, `sets`, `volume`, `best_set_weight` |
| `ExerciseProgressionSchema` | Full progression: `exercise_id`, `exercise_name`, `sessions` |

---

### `app/exercises/service.py`

**`get_all_exercises(db, user_id)`** — returns exercises where `user_id IS NULL` (globals) OR `user_id = caller_id` (their custom ones). Alphabetical order with muscle groups eager-loaded.

**`get_exercise(db, exercise_id)`** — fetch by ID. Returns `None` if not found.

**`get_all_muscle_groups(db)`** — all muscle groups alphabetically.

**`create_exercise(db, data, user_id)`** — creates an `ExerciseDef` with the given muscle groups and links them. Sets `user_id` to the caller.

**`update_exercise(db, exercise_id, data, user_id, is_admin)`** — partial update. Raises `ValueError("forbidden")` if the caller doesn't own the exercise and isn't admin. Raises `ValueError("name_conflict")` if the new name is already taken in the same scope (same `user_id`). Any field that is `None` in the update schema is left unchanged.

**`delete_exercise(db, exercise_id, user_id, is_admin)`** — raises `ValueError("forbidden")` if not permitted. Raises `ValueError("has_history")` if any `exercise_sets` rows reference this exercise. Returns `False` if not found.

**`get_exercise_progression(db, exercise_id, user_id)`** — joins `exercise_sets` with `workout_sessions` to get all the caller's sets for this exercise, ordered by date and set number. Groups by session in Python. Computes `volume` (sum of `reps × weight_lbs`, excluding bodyweight sets) and `best_set_weight` (max weight) per session. Returns `(None, [])` if the exercise doesn't exist.

---

### `app/exercises/routes.py`

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/api/muscle-groups` | any | Alphabetical list |
| GET | `/api/exercises` | any | Globals + caller's custom |
| POST | `/api/exercises` | non-demo | 400 on invalid muscle group IDs |
| GET | `/api/exercise/{id}/info` | any | 404 if not found |
| PUT | `/api/exercise/{id}` | non-demo | 403/404/409 |
| DELETE | `/api/exercise/{id}` | non-demo | 204 on success, 403/404/409 |
| GET | `/api/exercise/{id}/progression` | any | 404 if exercise not found |

---

### `app/routines/schemas.py`

| Schema | Used for |
|--------|----------|
| `RoutineExerciseRequest` | One exercise in a create/update request: `exercise_id`, `position`, `num_sets` |
| `RoutineCreate` | Create request: `name` + `exercises` list |
| `RoutineUpdate` | Full replace: `name` + `exercises` list (same fields as Create) |
| `RoutineExerciseDetail` | Exercise in a response: `exercise_id`, `name`, `position`, `num_sets` |
| `RoutineListItem` | Summary: `id`, `name`, `exercise_count`, `created_at` |
| `RoutineDetail` | Full detail: `id`, `name`, `created_at`, `exercises` sorted by position |

---

### `app/routines/service.py`

**`create_routine(db, data, user_id)`** — checks for name conflict within this user's routines, creates the `Routine` row, flushes for ID, then creates one `RoutineExercise` per entry. Raises `ValueError("name_conflict")` on duplicate name.

**`get_all_routines(db, user_id)`** — all routines for the user with exercises eager-loaded, ordered by name.

**`get_routine(db, routine_id, user_id)`** — single routine with exercises and their exercise definitions loaded (two levels of joinedload). Returns `None` if not found or not owned.

**`update_routine(db, routine_id, data, user_id)`** — checks ownership, checks name conflict (ignoring the routine's own current name), deletes all existing `RoutineExercise` rows, inserts new ones. Returns `None` if not found.

**`delete_routine(db, routine_id, user_id)`** — deletes by ID and user. Cascade handles `routine_exercises`. Returns `False` if not found. Does not affect logged workout history.

---

### `app/routines/routes.py`

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/api/routines` | non-demo | 400 invalid exercise IDs, 409 name conflict |
| GET | `/api/routines` | any | Summary list |
| GET | `/api/routine/{id}` | any | Full detail, 404 |
| PUT | `/api/routine/{id}` | non-demo | Full replace, 400/404/409 |
| DELETE | `/api/routine/{id}` | non-demo | 404 |

`_validate_exercise_ids(db, exercises)` is a private helper that bulk-queries existence of all exercise IDs and returns any that are missing.

`_to_detail(routine)` builds the `RoutineDetail` response from an ORM object, sorting exercises by position.

---

## Tests

Tests live in `services/api/tests/`. `conftest.py` creates an in-memory SQLite database for each test, seeds exercises, and provides a `TestClient` with a pre-authenticated user.

| Test file | Coverage |
|-----------|---------|
| `test_auth.py` | Login, register, demo login, token validation |
| `test_workouts.py` | CRUD, ownership isolation, date filtering |
| `test_exercises.py` | CRUD, permissions, progression query |
| `test_routines.py` | CRUD, name conflict, exercise validation |
| `test_import.py` | Batch import, error handling |
| `test_admin.py` | Admin CLI promote command |
| `test_demo.py` | Demo account 403 blocking |
| `test_models.py` | ORM cascade delete, relationship integrity |
| `test_seed.py` | Idempotency, alias collapsing |
