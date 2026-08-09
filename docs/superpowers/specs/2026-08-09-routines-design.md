# Routines Feature — Design Spec (1 of 5)

**Date:** 2026-08-09
**Scope:** Data model + CRUD API only. No frontend. No tests (covered in next feature).

---

## Overview

Add named workout routines that users can define as an ordered list of exercises with a default set count. Routines are templates — they do not affect logged workouts.

---

## Data Model

### `routines`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| name | TEXT | unique, e.g. "Push Day" |
| created_at | DATETIME | UTC, default now |

### `routine_exercises`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | primary key |
| routine_id | INTEGER | FK → routines.id, cascade delete |
| exercise_id | INTEGER | FK → exercises.id |
| position | INTEGER | 1-indexed order within the routine |
| num_sets | INTEGER | default number of sets to pre-fill |

Cascade: deleting a `Routine` auto-deletes all its `RoutineExercise` rows.

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/routines` | Create a routine |
| GET | `/api/routines` | List all routines (id, name, exercise count) |
| GET | `/api/routine/{id}` | Routine detail with ordered exercises and set counts |
| PUT | `/api/routine/{id}` | Full replace — name + all exercises |
| DELETE | `/api/routine/{id}` | Delete routine; does not affect logged workouts |

### Request/Response Shapes

**POST/PUT body:**
```json
{
  "name": "Push Day",
  "exercises": [
    { "exercise_id": 42, "position": 1, "num_sets": 3 },
    { "exercise_id": 17, "position": 2, "num_sets": 4 }
  ]
}
```

**GET `/api/routines` response:**
```json
[
  { "id": 1, "name": "Push Day", "exercise_count": 3 }
]
```

**GET `/api/routine/{id}` response:**
```json
{
  "id": 1,
  "name": "Push Day",
  "created_at": "2026-08-09T10:00:00Z",
  "exercises": [
    { "exercise_id": 42, "name": "Barbell Bench Press", "position": 1, "num_sets": 3 },
    { "exercise_id": 17, "name": "Overhead Press", "position": 2, "num_sets": 4 }
  ]
}
```

### Error Handling
| Condition | Status |
|-----------|--------|
| Routine not found | 404 |
| Name already in use (create or update) | 409 |

---

## Implementation Layers

### `app/model/models.py`
Add `Routine` and `RoutineExercise` ORM classes using the existing `Mapped`/`mapped_column` style. `Routine.exercises` relationship ordered by `position`, `cascade="all, delete-orphan"`.

### `app/api/schemas.py`
Append to existing file:
- `RoutineExerciseRequest` — request: exercise_id, position, num_sets
- `RoutineCreate` — name + exercises list
- `RoutineUpdate` — same shape as `RoutineCreate` (full replace)
- `RoutineExerciseDetail` — response: exercise_id, name, position, num_sets
- `RoutineListItem` — response: id, name, exercise_count
- `RoutineDetail` — response: id, name, created_at, exercises

### `app/services/routine_service.py`
New file. Functions: `create_routine`, `get_all_routines`, `get_routine`, `update_routine`, `delete_routine`. Raises `ValueError("name_conflict")` for duplicate names, matching the exercise service pattern. PUT replaces by deleting all `RoutineExercise` rows then re-inserting.

### `app/api/routine_routes.py`
New file. Thin handlers on an `APIRouter`. Catches `ValueError("name_conflict")` → 409, missing routine → 404.

### `app/main.py`
Register: `app.include_router(routine_router, prefix="/api")`.

### `SPEC.md`
Add `routines` and `routine_exercises` to the Database Schema section. Add Routines endpoints to the Routing section.

---

## Out of Scope
- Frontend
- Tests (next feature)
- Validating that `exercise_id` values exist (FK constraint handles it at the DB level)
- Enforcing consecutive positions (client responsibility)
