# Exercise CRUD — Update & Delete Endpoints

**Date:** 2026-07-28
**Branch:** feat/crud-exercises-backend

## Summary

Add `PUT /api/exercise/{id}` and `DELETE /api/exercise/{id}` to complete CRUD for exercises. Also fix `CreateExerciseSchema` and `create_exercise()` to accept `equipment`, `target`, and `instructions` on create (currently silently ignored).

## Endpoints

| Method | Path | Success | Errors |
|--------|------|---------|--------|
| PUT | `/api/exercise/{id}` | 200 `ExerciseDefSchema` | 404 not found, 409 name conflict |
| DELETE | `/api/exercise/{id}` | 204 no content | 404 not found, 409 has logged history |

## Schema Changes (`app/api/schemas.py`)

### Fix `CreateExerciseSchema`

Add three optional fields so create is on par with update:

```python
class CreateExerciseSchema(BaseModel):
    name: str
    equipment: Optional[str] = None
    target: Optional[str] = None
    instructions: Optional[str] = None
    muscle_group_ids: list[int]
```

### Add `ExerciseUpdate`

All fields optional — supports partial updates:

```python
class ExerciseUpdate(BaseModel):
    name: Optional[str] = None
    equipment: Optional[str] = None
    target: Optional[str] = None
    instructions: Optional[str] = None
    muscle_group_ids: Optional[list[int]] = None
```

## Service Layer (`app/services/exercise_service.py`)

### Fix `create_exercise`

Pass `equipment`, `target`, `instructions` through to the ORM constructor.

### Add `update_exercise(db, exercise_id, data: ExerciseUpdate) -> ExerciseDef | None`

1. Fetch by ID — return `None` if missing (route raises 404)
2. If `data.name` is set and differs from current, query for a name collision on a different exercise — raise `ValueError("name_conflict")` if found
3. Apply each non-`None` field to the ORM object
4. If `data.muscle_group_ids` is provided: clear `exercise.muscle_groups`, re-query `MuscleGroup` objects and assign
5. `db.commit()` + `db.refresh()`, return exercise

### Add `delete_exercise(db, exercise_id) -> bool`

1. Fetch by ID — return `False` if missing (route raises 404)
2. Query `exercise_sets` for any row with matching `exercise_id` — raise `ValueError("has_history")` if found
3. `db.delete(exercise)` — SQLAlchemy cascades `exercise_muscle_groups` join rows automatically
4. `db.commit()`, return `True`

## Routes (`app/api/exercise_routes.py`)

Two new handlers — thin wrappers over the service functions:

- Call service, map `None`/`False` return → 404
- Catch `ValueError("name_conflict")` → 409
- Catch `ValueError("has_history")` → 409
- DELETE returns `Response(status_code=204)`

## Docs

Update API tables in `README.md` and `SPEC.md` to include the two new endpoints.

## Out of Scope

- Tests (added later)
- Exercise browser/management UI
- Bulk delete or merge
- Fixing other gaps in `CreateExerciseSchema` beyond the three fields above
