# Routines Model and CRUD API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `routines` and `routine_exercises` tables with full CRUD endpoints to the GymLog FastAPI backend.

**Architecture:** Two new ORM models follow the existing `Mapped`/`mapped_column` style. A new service file owns all DB logic. A new router file contains thin handlers and is registered in `main.py` alongside the existing workout and exercise routers. Schemas are appended to the existing `schemas.py`.

**Tech Stack:** FastAPI, SQLAlchemy (ORM), SQLite, Pydantic v2, Python 3.12

## Global Constraints

- PEP 8: max 79 chars per line, snake_case for functions/variables, PascalCase for classes
- PEP 257: every function, method, and class must have a docstring; imperative mood; one-line form fits on one line
- Imports: stdlib → third-party → local, each group separated by a blank line
- Two blank lines between top-level definitions; one blank line between methods
- No tests in this plan (covered in the next feature)

---

### Task 1: ORM Models

**Files:**
- Modify: `app/model/models.py`

**Interfaces:**
- Produces: `Routine` class (tablename `routines`), `RoutineExercise` class (tablename `routine_exercises`), available from `app.model.models`

- [ ] **Step 1: Add `Routine` and `RoutineExercise` to `models.py`**

Append after the existing `Exercise` class (two blank lines before each new class). The existing imports (`Integer`, `String`, `DateTime`, `ForeignKey`, `relationship`, `Mapped`, `mapped_column`, `datetime`, `timezone`) are already present — no new imports needed.

```python
class Routine(Base):
    """A named workout routine — ordered template of exercises."""

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
    )


class RoutineExercise(Base):
    """One exercise slot in a routine with position and default set count."""

    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routines.id"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    num_sets: Mapped[int] = mapped_column(Integer, nullable=False)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise_def: Mapped["ExerciseDef"] = relationship()
```

- [ ] **Step 2: Verify import**

```bash
python -c "from app.model.models import Routine, RoutineExercise; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/model/models.py
git commit -m "feat: add Routine and RoutineExercise ORM models"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Modify: `app/api/schemas.py`

**Interfaces:**
- Consumes: `datetime` already imported at top of `schemas.py`
- Produces: `RoutineExerciseRequest`, `RoutineCreate`, `RoutineUpdate`, `RoutineExerciseDetail`, `RoutineListItem`, `RoutineDetail` — all importable from `app.api.schemas`

- [ ] **Step 1: Append routine schemas to `schemas.py`**

Add two blank lines after the last class (`ExerciseProgressionSchema`), then append:

```python
class RoutineExerciseRequest(BaseModel):
    """One exercise entry in a routine create/update request."""

    exercise_id: int
    position: int
    num_sets: int


class RoutineCreate(BaseModel):
    """Request schema for creating a new routine."""

    name: str
    exercises: list[RoutineExerciseRequest]


class RoutineUpdate(BaseModel):
    """Request schema for fully replacing a routine's name and exercises."""

    name: str
    exercises: list[RoutineExerciseRequest]


class RoutineExerciseDetail(BaseModel):
    """One exercise slot in a routine detail response."""

    exercise_id: int
    name: str
    position: int
    num_sets: int


class RoutineListItem(BaseModel):
    """Summary of a routine returned in list responses."""

    id: int
    name: str
    exercise_count: int


class RoutineDetail(BaseModel):
    """Full routine response with ordered exercises."""

    id: int
    name: str
    created_at: datetime
    exercises: list[RoutineExerciseDetail]
```

- [ ] **Step 2: Verify import**

```bash
python -c "
from app.api.schemas import (
    RoutineCreate, RoutineUpdate, RoutineDetail,
    RoutineListItem, RoutineExerciseDetail, RoutineExerciseRequest,
)
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/api/schemas.py
git commit -m "feat: add routine Pydantic schemas"
```

---

### Task 3: Service Layer

**Files:**
- Create: `app/services/routine_service.py`

**Interfaces:**
- Consumes: `RoutineCreate`, `RoutineUpdate` from `app.api.schemas`; `Routine`, `RoutineExercise` from `app.model.models`
- Produces:
  - `create_routine(db, data: RoutineCreate) -> Routine` — raises `ValueError("name_conflict")` if name taken
  - `get_all_routines(db) -> list[Routine]` — exercises eager-loaded via joinedload
  - `get_routine(db, routine_id: int) -> Routine | None` — exercises + exercise_def eager-loaded
  - `update_routine(db, routine_id: int, data: RoutineUpdate) -> Routine | None` — raises `ValueError("name_conflict")`; returns None if not found
  - `delete_routine(db, routine_id: int) -> bool` — returns False if not found

- [ ] **Step 1: Create `app/services/routine_service.py`**

```python
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import RoutineCreate, RoutineUpdate
from app.model.models import Routine, RoutineExercise


def create_routine(db: Session, data: RoutineCreate) -> Routine:
    """Create a new routine; raises ValueError('name_conflict') if name taken."""
    if db.query(Routine).filter(Routine.name == data.name).first():
        raise ValueError("name_conflict")
    routine = Routine(name=data.name)
    db.add(routine)
    db.flush()
    for ex in data.exercises:
        db.add(RoutineExercise(
            routine_id=routine.id,
            exercise_id=ex.exercise_id,
            position=ex.position,
            num_sets=ex.num_sets,
        ))
    db.commit()
    db.refresh(routine)
    return routine


def get_all_routines(db: Session) -> list[Routine]:
    """Return all routines with exercises eager-loaded, ordered by name."""
    return (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .order_by(Routine.name)
        .all()
    )


def get_routine(db: Session, routine_id: int) -> Routine | None:
    """Return a routine by ID with exercise definitions loaded, or None."""
    return (
        db.query(Routine)
        .options(
            joinedload(Routine.exercises).joinedload(
                RoutineExercise.exercise_def
            )
        )
        .filter(Routine.id == routine_id)
        .first()
    )


def update_routine(
    db: Session, routine_id: int, data: RoutineUpdate
) -> Routine | None:
    """Replace a routine's name and exercises; returns None if not found.

    Raises ValueError('name_conflict') if the new name is taken by another
    routine.
    """
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        return None
    conflict = (
        db.query(Routine)
        .filter(Routine.name == data.name, Routine.id != routine_id)
        .first()
    )
    if conflict:
        raise ValueError("name_conflict")
    routine.name = data.name
    db.query(RoutineExercise).filter(
        RoutineExercise.routine_id == routine_id
    ).delete()
    for ex in data.exercises:
        db.add(RoutineExercise(
            routine_id=routine.id,
            exercise_id=ex.exercise_id,
            position=ex.position,
            num_sets=ex.num_sets,
        ))
    db.commit()
    db.refresh(routine)
    return routine


def delete_routine(db: Session, routine_id: int) -> bool:
    """Delete a routine and its exercise slots; returns False if not found."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        return False
    db.delete(routine)
    db.commit()
    return True
```

- [ ] **Step 2: Verify import**

```bash
python -c "
from app.services.routine_service import (
    create_routine, get_all_routines, get_routine,
    update_routine, delete_routine,
)
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/services/routine_service.py
git commit -m "feat: add routine service layer"
```

---

### Task 4: Route Handlers and Router Registration

**Files:**
- Create: `app/api/routine_routes.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes all six schema classes from Task 2; all five service functions from Task 3
- Produces: `router` (FastAPI `APIRouter`) mounted at `/api` in `main.py`

- [ ] **Step 1: Create `app/api/routine_routes.py`**

`_to_detail` is a private helper that builds the response. After `create_routine` and `update_routine`, call `get_routine(db, routine.id)` to reload with `exercise_def` joinedloaded before passing to `_to_detail`. Exercises are sorted by `position` in Python (list is small; avoids SQLAlchemy relationship `order_by` complexity).

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    RoutineCreate,
    RoutineDetail,
    RoutineExerciseDetail,
    RoutineListItem,
    RoutineUpdate,
)
from app.db.database import get_db
from app.services.routine_service import (
    create_routine,
    delete_routine,
    get_all_routines,
    get_routine,
    update_routine,
)

router = APIRouter()


def _to_detail(routine) -> RoutineDetail:
    """Build a RoutineDetail from a fully-loaded Routine ORM object."""
    return RoutineDetail(
        id=routine.id,
        name=routine.name,
        created_at=routine.created_at,
        exercises=[
            RoutineExerciseDetail(
                exercise_id=ex.exercise_id,
                name=ex.exercise_def.name,
                position=ex.position,
                num_sets=ex.num_sets,
            )
            for ex in sorted(routine.exercises, key=lambda e: e.position)
        ],
    )


@router.post("/routines", response_model=RoutineDetail, status_code=201)
def create(data: RoutineCreate, db: Session = Depends(get_db)):
    """Create a new routine; 409 if name is already taken."""
    try:
        routine = create_routine(db, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    return _to_detail(get_routine(db, routine.id))


@router.get("/routines", response_model=list[RoutineListItem])
def list_routines(db: Session = Depends(get_db)):
    """Return all routines ordered by name with their exercise counts."""
    routines = get_all_routines(db)
    return [
        RoutineListItem(
            id=r.id,
            name=r.name,
            exercise_count=len(r.exercises),
        )
        for r in routines
    ]


@router.get("/routine/{routine_id}", response_model=RoutineDetail)
def fetch_routine(routine_id: int, db: Session = Depends(get_db)):
    """Return full detail for a single routine; 404 if not found."""
    routine = get_routine(db, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(routine)


@router.put("/routine/{routine_id}", response_model=RoutineDetail)
def replace_routine(
    routine_id: int,
    data: RoutineUpdate,
    db: Session = Depends(get_db),
):
    """Replace a routine's name and exercises; 404 if not found, 409 on conflict."""
    try:
        routine = update_routine(db, routine_id, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(get_routine(db, routine.id))


@router.delete("/routine/{routine_id}")
def remove_routine(routine_id: int, db: Session = Depends(get_db)):
    """Delete a routine and its exercise slots; 404 if not found."""
    if not delete_routine(db, routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"deleted": routine_id}
```

- [ ] **Step 2: Register the router in `app/main.py`**

Add one import line after the existing router imports:

```python
from app.api.routine_routes import router as routine_router
```

Add one `include_router` call after the existing two (before `app.mount`):

```python
app.include_router(routine_router, prefix="/api")
```

- [ ] **Step 3: Verify the app starts**

```bash
python -c "from app.main import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Smoke test with curl**

Start the app in one terminal:
```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

In another terminal, check the endpoints respond (use any valid `exercise_id` from the seeded data — e.g. 1):

```bash
# Create
curl -s -X POST http://localhost:8000/api/routines \
  -H "Content-Type: application/json" \
  -d '{"name":"Push Day","exercises":[{"exercise_id":1,"position":1,"num_sets":3}]}' | python -m json.tool

# List
curl -s http://localhost:8000/api/routines | python -m json.tool

# Detail (use the id returned by create)
curl -s http://localhost:8000/api/routine/1 | python -m json.tool

# 404
curl -s http://localhost:8000/api/routine/9999

# 409
curl -s -X POST http://localhost:8000/api/routines \
  -H "Content-Type: application/json" \
  -d '{"name":"Push Day","exercises":[]}' | python -m json.tool

# Delete
curl -s -X DELETE http://localhost:8000/api/routine/1
```

Expected: create returns 201 with `RoutineDetail`; list returns array; detail returns full object; 9999 returns 404; duplicate name returns 409; delete returns `{"deleted": 1}`.

- [ ] **Step 5: Commit**

```bash
git add app/api/routine_routes.py app/main.py
git commit -m "feat: add routine route handlers and register router"
```

---

### Task 5: Update SPEC.md

**Files:**
- Modify: `SPEC.md`

- [ ] **Step 1: Add tables to the Database Schema section**

After the `exercise_sets` table block, add:

```markdown
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
```

- [ ] **Step 2: Add Routines endpoints to the Routing section**

After the Workouts endpoint table, add:

```markdown
#### Routines
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/routines` | Create a routine; 409 on name conflict |
| GET | `/api/routines` | List all routines (id, name, exercise count) |
| GET | `/api/routine/{id}` | Routine detail with ordered exercises and set counts |
| PUT | `/api/routine/{id}` | Full replace — name and all exercises; 409 on name conflict |
| DELETE | `/api/routine/{id}` | Delete routine (does not affect logged workouts) |
```

- [ ] **Step 3: Commit**

```bash
git add SPEC.md
git commit -m "docs: update SPEC.md with routines tables and endpoints"
```
