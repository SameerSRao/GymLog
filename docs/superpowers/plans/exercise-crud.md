# Exercise CRUD — Update & Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `PUT /api/exercise/{id}` and `DELETE /api/exercise/{id}`, fix `CreateExerciseSchema` to accept `equipment`/`target`/`instructions`, and update docs.

**Architecture:** All DB logic lives in `exercise_service.py`; route handlers in `exercise_routes.py` are thin wrappers that map service return values to HTTP responses. Schemas live in `schemas.py`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy (ORM), Pydantic v2, SQLite

## Global Constraints

- No tests (out of scope for this plan — added later)
- Do not modify `app/model/models.py` — no schema migrations needed
- Follow existing patterns: service functions take `db: Session`, return ORM objects or `None`/`bool`, never raise HTTP exceptions
- Route handlers call service, map `None`/`False` → 404, catch `ValueError` → 409
- All imports must be explicit (no wildcard imports)

---

### Task 1: Fix `CreateExerciseSchema` and `create_exercise()`

**Files:**
- Modify: `app/api/schemas.py`
- Modify: `app/services/exercise_service.py`

**Interfaces:**
- Produces: `CreateExerciseSchema` with fields `name: str`, `equipment: Optional[str]`, `target: Optional[str]`, `instructions: Optional[str]`, `muscle_group_ids: list[int]`
- Produces: `create_exercise(db, data: CreateExerciseSchema) -> ExerciseDef` that persists all five fields

- [ ] **Step 1: Update `CreateExerciseSchema` in `app/api/schemas.py`**

Find the existing class:
```python
class CreateExerciseSchema(BaseModel):
    name: str
    muscle_group_ids: list[int]
```

Replace with:
```python
class CreateExerciseSchema(BaseModel):
    name: str
    equipment: Optional[str] = None
    target: Optional[str] = None
    instructions: Optional[str] = None
    muscle_group_ids: list[int]
```

- [ ] **Step 2: Update `create_exercise()` in `app/services/exercise_service.py`**

Find the existing function body:
```python
def create_exercise(db: Session, data: CreateExerciseSchema) -> ExerciseDef:
    muscle_groups = db.query(MuscleGroup).filter(MuscleGroup.id.in_(data.muscle_group_ids)).all()
    exercise = ExerciseDef(name=data.name, muscle_groups=muscle_groups)
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise
```

Replace with:
```python
def create_exercise(db: Session, data: CreateExerciseSchema) -> ExerciseDef:
    muscle_groups = db.query(MuscleGroup).filter(MuscleGroup.id.in_(data.muscle_group_ids)).all()
    exercise = ExerciseDef(
        name=data.name,
        equipment=data.equipment,
        target=data.target,
        instructions=data.instructions,
        muscle_groups=muscle_groups,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise
```

- [ ] **Step 3: Manual smoke test**

Start the app: `docker compose up --build` (or `uvicorn app.main:app --reload` with venv active).

POST to create an exercise with all fields:
```bash
curl -s -X POST http://localhost:8000/api/exercises \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Curl","equipment":"barbell","target":"biceps","instructions":"Curl it.","muscle_group_ids":[]}' \
  | python3 -m json.tool
```

Expected response includes `equipment`, `target`, `instructions` in the returned object.

- [ ] **Step 4: Commit**

```bash
git add app/api/schemas.py app/services/exercise_service.py
git commit -m "fix: add equipment, target, instructions to CreateExerciseSchema and create_exercise"
```

---

### Task 2: Add `ExerciseUpdate` schema

**Files:**
- Modify: `app/api/schemas.py`

**Interfaces:**
- Produces: `ExerciseUpdate` with all-optional fields for use in the PUT route

- [ ] **Step 1: Add `ExerciseUpdate` to `app/api/schemas.py`**

Add after `CreateExerciseSchema`:
```python
class ExerciseUpdate(BaseModel):
    name: Optional[str] = None
    equipment: Optional[str] = None
    target: Optional[str] = None
    instructions: Optional[str] = None
    muscle_group_ids: Optional[list[int]] = None
```

- [ ] **Step 2: Commit**

```bash
git add app/api/schemas.py
git commit -m "feat: add ExerciseUpdate schema"
```

---

### Task 3: Add `update_exercise()` service function

**Files:**
- Modify: `app/services/exercise_service.py`

**Interfaces:**
- Consumes: `ExerciseUpdate` from Task 2
- Produces: `update_exercise(db: Session, exercise_id: int, data: ExerciseUpdate) -> ExerciseDef | None`
  - Returns `None` if exercise not found
  - Raises `ValueError("name_conflict")` if `data.name` conflicts with a different existing exercise

- [ ] **Step 1: Add import for `ExerciseUpdate` at the top of `exercise_service.py`**

The existing import line is:
```python
from app.api.schemas import CreateExerciseSchema
```

Replace with:
```python
from app.api.schemas import CreateExerciseSchema, ExerciseUpdate
```

- [ ] **Step 2: Add `update_exercise()` to `app/services/exercise_service.py`**

Add after `create_exercise()`:
```python
def update_exercise(db: Session, exercise_id: int, data: ExerciseUpdate) -> Optional[ExerciseDef]:
    exercise = db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    if not exercise:
        return None

    if data.name is not None and data.name != exercise.name:
        conflict = db.query(ExerciseDef).filter(
            ExerciseDef.name == data.name,
            ExerciseDef.id != exercise_id,
        ).first()
        if conflict:
            raise ValueError("name_conflict")
        exercise.name = data.name

    if data.equipment is not None:
        exercise.equipment = data.equipment
    if data.target is not None:
        exercise.target = data.target
    if data.instructions is not None:
        exercise.instructions = data.instructions

    if data.muscle_group_ids is not None:
        exercise.muscle_groups = db.query(MuscleGroup).filter(
            MuscleGroup.id.in_(data.muscle_group_ids)
        ).all()

    db.commit()
    db.refresh(exercise)
    return exercise
```

- [ ] **Step 3: Commit**

```bash
git add app/services/exercise_service.py
git commit -m "feat: add update_exercise service function"
```

---

### Task 4: Add `delete_exercise()` service function

**Files:**
- Modify: `app/services/exercise_service.py`

**Interfaces:**
- Produces: `delete_exercise(db: Session, exercise_id: int) -> bool`
  - Returns `False` if exercise not found
  - Raises `ValueError("has_history")` if any `exercise_sets` row references this exercise
  - Returns `True` on successful delete

- [ ] **Step 1: Add `delete_exercise()` to `app/services/exercise_service.py`**

Add after `update_exercise()`:
```python
def delete_exercise(db: Session, exercise_id: int) -> bool:
    exercise = db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    if not exercise:
        return False

    has_sets = db.query(Exercise).filter(Exercise.exercise_id == exercise_id).first()
    if has_sets:
        raise ValueError("has_history")

    db.delete(exercise)
    db.commit()
    return True
```

Note: `Exercise` (the `exercise_sets` ORM model) is already imported at the top of the file. `db.delete(exercise)` cascades to `exercise_muscle_groups` rows automatically via SQLAlchemy's relationship.

- [ ] **Step 2: Commit**

```bash
git add app/services/exercise_service.py
git commit -m "feat: add delete_exercise service function"
```

---

### Task 5: Add PUT and DELETE route handlers

**Files:**
- Modify: `app/api/exercise_routes.py`

**Interfaces:**
- Consumes: `update_exercise(db, exercise_id, data)` from Task 3
- Consumes: `delete_exercise(db, exercise_id)` from Task 4
- Consumes: `ExerciseUpdate` from Task 2
- Produces: `PUT /api/exercise/{id}` → 200 `ExerciseDefSchema` | 404 | 409
- Produces: `DELETE /api/exercise/{id}` → 204 | 404 | 409

- [ ] **Step 1: Update imports in `app/api/exercise_routes.py`**

Existing schema import line:
```python
from app.api.schemas import (
    ExerciseDefSchema, CreateExerciseSchema, MuscleGroupSchema,
    ExerciseProgressionSchema, SessionSummary, SetDetail,
)
```

Replace with:
```python
from app.api.schemas import (
    ExerciseDefSchema, CreateExerciseSchema, ExerciseUpdate, MuscleGroupSchema,
    ExerciseProgressionSchema, SessionSummary, SetDetail,
)
```

Existing service import line:
```python
from app.services.exercise_service import (
    get_all_exercises, get_exercise, get_all_muscle_groups,
    create_exercise, get_exercise_progression,
)
```

Replace with:
```python
from app.services.exercise_service import (
    get_all_exercises, get_exercise, get_all_muscle_groups,
    create_exercise, update_exercise, delete_exercise, get_exercise_progression,
)
```

Also add `Response` to the FastAPI import at the top:
```python
from fastapi import APIRouter, Depends, HTTPException, Response
```

- [ ] **Step 2: Add PUT handler to `app/api/exercise_routes.py`**

Add after the `get_exercise_info` handler:
```python
@router.put("/exercise/{exercise_id}", response_model=ExerciseDefSchema)
def edit_exercise(exercise_id: int, data: ExerciseUpdate, db: Session = Depends(get_db)):
    try:
        exercise = update_exercise(db, exercise_id, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail="An exercise with that name already exists")
        raise
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
```

- [ ] **Step 3: Add DELETE handler to `app/api/exercise_routes.py`**

Add after the PUT handler:
```python
@router.delete("/exercise/{exercise_id}", status_code=204)
def remove_exercise(exercise_id: int, db: Session = Depends(get_db)):
    try:
        found = delete_exercise(db, exercise_id)
    except ValueError as e:
        if str(e) == "has_history":
            raise HTTPException(status_code=409, detail="Exercise has logged history and cannot be deleted")
        raise
    if not found:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return Response(status_code=204)
```

- [ ] **Step 4: Manual smoke test — PUT**

Start the app. First get an exercise ID:
```bash
curl -s http://localhost:8000/api/exercises | python3 -m json.tool | head -30
```

Update an exercise (substitute a real ID):
```bash
curl -s -X PUT http://localhost:8000/api/exercise/1325 \
  -H "Content-Type: application/json" \
  -d '{"equipment":"cable","target":"biceps"}' \
  | python3 -m json.tool
```

Expected: 200 with updated fields reflected.

Test 404:
```bash
curl -s -o /dev/null -w "%{http_code}" -X PUT http://localhost:8000/api/exercise/999999 \
  -H "Content-Type: application/json" \
  -d '{"name":"Ghost"}'
```
Expected: `404`

Test 409 name conflict (use the name of any existing exercise):
```bash
curl -s -o /dev/null -w "%{http_code}" -X PUT http://localhost:8000/api/exercise/1325 \
  -H "Content-Type: application/json" \
  -d '{"name":"Barbell Bench Press"}'
```
Expected: `409`

- [ ] **Step 5: Manual smoke test — DELETE**

Create a throwaway exercise to delete:
```bash
curl -s -X POST http://localhost:8000/api/exercises \
  -H "Content-Type: application/json" \
  -d '{"name":"Throwaway Exercise","muscle_group_ids":[]}' \
  | python3 -m json.tool
```

Note the `id` in the response, then delete it:
```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/exercise/<id>
```
Expected: `204`

Test 404 on a missing exercise:
```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/exercise/999999
```
Expected: `404`

Test 409 on an exercise with history (use any seeded exercise ID that has been logged):
```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/exercise/1
```
Expected: `409` (assuming exercise 1 has been used in a workout; if not, find one via `GET /api/workouts`)

- [ ] **Step 6: Commit**

```bash
git add app/api/exercise_routes.py
git commit -m "feat: add PUT and DELETE exercise route handlers"
```

---

### Task 6: Update docs

**Files:**
- Modify: `README.md`
- Modify: `SPEC.md`

- [ ] **Step 1: Update `README.md` Exercises API table**

Find the existing Exercises table:
```markdown
| GET | `/api/exercises` | List all exercises |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Exercise detail |
| GET | `/api/exercise/{id}/progression` | Workout history for a lift |
```

Replace with:
```markdown
| GET | `/api/exercises` | List all exercises |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Exercise detail |
| PUT | `/api/exercise/{id}` | Update an exercise (partial or full) |
| DELETE | `/api/exercise/{id}` | Delete an exercise (409 if it has logged history) |
| GET | `/api/exercise/{id}/progression` | Workout history for a lift |
```

- [ ] **Step 2: Update `SPEC.md` Exercises routing table**

Find the existing Exercises table under `### JSON API`:
```markdown
| GET | `/api/exercises` | List all exercises (id, name, equipment, target, muscle_groups) |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Single exercise detail |
| GET | `/api/exercise/{id}/progression` | Workout history grouped by session |
```

Replace with:
```markdown
| GET | `/api/exercises` | List all exercises (id, name, equipment, target, muscle_groups) |
| POST | `/api/exercises` | Create a custom exercise |
| GET | `/api/muscle-groups` | List all muscle groups |
| GET | `/api/exercise/{id}/info` | Single exercise detail |
| PUT | `/api/exercise/{id}` | Update an exercise — partial or full; 409 on name conflict |
| DELETE | `/api/exercise/{id}` | Delete an exercise — 409 if referenced in exercise_sets |
| GET | `/api/exercise/{id}/progression` | Workout history grouped by session |
```

- [ ] **Step 3: Commit**

```bash
git add README.md SPEC.md
git commit -m "docs: add PUT and DELETE exercise endpoints to API tables"
```
