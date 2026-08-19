# Batch JSON Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /api/workouts/import` endpoint that lets admin users bulk-insert historical workout sessions from a JSON array.

**Architecture:** One new route calls one new service function; both use the existing `Workout`/`Exercise` ORM models and follow the existing layer pattern (thin route → service with all DB logic). Two new Pydantic schemas define the request and response shapes.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest with `TestClient`

## Global Constraints

- Max line length: 79 chars for code, 72 for docstrings
- Every function/method/class must have a docstring (PEP 257 one-liner form)
- Two blank lines between top-level definitions
- Imports grouped: stdlib → third-party → local, each group blank-line separated
- Run tests with: `pytest tests/ -v` from `/Users/sameerrao/code/GymLog`
- Activate venv first: `source .venv/bin/activate`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `app/api/schemas.py` | Add `WorkoutImportRequest`, `ImportError`, `ImportResponse` |
| Modify | `app/services/workout_service.py` | Add `import_workouts(db, sessions, user_id)` |
| Modify | `app/api/workout_routes.py` | Add `POST /api/workouts/import` route |
| Create | `tests/test_import.py` | Integration tests for the import endpoint |

---

### Task 1: Add Import Schemas

**Files:**
- Modify: `app/api/schemas.py`

**Interfaces:**
- Produces:
  - `WorkoutImportRequest` — `logged_at: datetime` (required), `exercises: list[ExerciseLogRequest]`
  - `ImportError` — `index: int`, `reason: str`
  - `ImportResponse` — `sessions_created: int`, `sets_created: int`, `errors: list[ImportError]`

- [ ] **Step 1: Add the three schemas to `app/api/schemas.py`**

Open `app/api/schemas.py`. After the `WorkoutRequest` class (currently ends around line 110), add:

```python
class WorkoutImportRequest(BaseModel):
    """One session in a batch import request; logged_at is required."""

    logged_at: datetime
    exercises: list[ExerciseLogRequest]


class ImportError(BaseModel):
    """One skipped session reported in a batch import response."""

    index: int
    reason: str


class ImportResponse(BaseModel):
    """Summary returned after a batch import completes."""

    sessions_created: int
    sets_created: int
    errors: list[ImportError]
```

- [ ] **Step 2: Commit**

```bash
git add app/api/schemas.py
git commit -m "feat: add WorkoutImportRequest, ImportError, ImportResponse schemas"
```

---

### Task 2: Service Function + Route + Tests (TDD)

**Files:**
- Modify: `app/services/workout_service.py`
- Modify: `app/api/workout_routes.py`
- Create: `tests/test_import.py`

**Interfaces:**
- Consumes: `WorkoutImportRequest`, `ImportError`, `ImportResponse` from Task 1; `Workout`, `Exercise`, `ExerciseDef` ORM models; `get_current_user` dependency from `auth_routes`
- Produces: `import_workouts(db: Session, sessions: list[WorkoutImportRequest], user_id: int) -> ImportResponse`

- [ ] **Step 1: Write the failing tests in `tests/test_import.py`**

```python
from conftest import make_exercise, make_user
from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# POST /api/workouts/import
# ---------------------------------------------------------------------------

def test_import_single_session(admin_client, db):
    """Assert POST /api/workouts/import creates one session and its sets."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {
                    "exercise_id": ex.id,
                    "sets": [
                        {"reps": 8, "weight_lbs": 135},
                        {"reps": 8, "weight_lbs": 135},
                    ],
                }
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 1
    assert data["sets_created"] == 2
    assert data["errors"] == []


def test_import_multiple_sessions(admin_client, db):
    """Assert POST /api/workouts/import handles multiple sessions correctly."""
    ex1 = make_exercise(db, name="Bench Press")
    ex2 = make_exercise(db, name="Squat")
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": ex1.id, "sets": [{"reps": 8, "weight_lbs": 135}]},
            ],
        },
        {
            "logged_at": "2025-01-11T10:00:00",
            "exercises": [
                {
                    "exercise_id": ex2.id,
                    "sets": [
                        {"reps": 5, "weight_lbs": 225},
                        {"reps": 5, "weight_lbs": 225},
                    ],
                }
            ],
        },
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 2
    assert data["sets_created"] == 3
    assert data["errors"] == []


def test_import_invalid_exercise_id_skipped(admin_client, db):
    """Assert sessions with unknown exercise_ids are skipped and reported."""
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": 9999, "sets": [{"reps": 8}]},
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 0
    assert data["sets_created"] == 0
    assert len(data["errors"]) == 1
    assert "9999" in data["errors"][0]["reason"]
    assert data["errors"][0]["index"] == 0


def test_import_partial_error_continues(admin_client, db):
    """Assert a bad session is skipped but valid sessions still import."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": 9999, "sets": [{"reps": 8}]},
            ],
        },
        {
            "logged_at": "2025-01-11T10:00:00",
            "exercises": [
                {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]},
            ],
        },
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 1
    assert data["sets_created"] == 1
    assert len(data["errors"]) == 1


def test_import_non_admin_forbidden(client):
    """Assert POST /api/workouts/import returns 403 for non-admin users."""
    r = client.post("/api/workouts/import", json=[])
    assert r.status_code == 403


def test_import_bodyweight_set(admin_client, db):
    """Assert sets without weight_lbs (bodyweight) are accepted."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": ex.id, "sets": [{"reps": 10}]},
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    assert r.json()["sets_created"] == 1


def test_import_logged_at_persisted(admin_client, db):
    """Assert the logged_at timestamp from the payload is stored on the session."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-03-15T07:30:00",
            "exercises": [
                {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]},
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    session_id = None

    # Verify via GET /api/workouts that the session appears with correct date
    def db_override():
        """Yield db for admin user override."""
        yield db

    def user_override():
        """Return admin user dict."""
        from conftest import make_user
        # admin_client fixture creates user with username="admin"
        from app.model.models import User
        admin = db.query(User).filter(User.username == "admin").first()
        return {
            "sub": str(admin.id),
            "username": admin.username,
            "is_admin": True,
            "is_premium": True,
        }

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = user_override
    with TestClient(app) as c:
        workouts = c.get("/api/workouts").json()
    app.dependency_overrides.clear()

    assert any("2025-03-15" in w["logged_at"] for w in workouts)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source .venv/bin/activate && pytest tests/test_import.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — route and service don't exist yet.

- [ ] **Step 3: Implement `import_workouts` in `app/services/workout_service.py`**

First, update the existing top-level import in `workout_service.py` (currently imports only `WorkoutRequest`):

```python
from app.api.schemas import ImportError, ImportResponse, WorkoutRequest
```

Then add the function after `delete_workout`:

```python
def import_workouts(
    db: Session,
    sessions: list,
    user_id: int,
) -> ImportResponse:
    """Bulk-insert workout sessions; skip invalid ones and report errors."""
    all_exercise_ids: set[int] = {
        e.exercise_id
        for s in sessions
        for e in s.exercises
    }
    valid_ids: set[int] = {
        row[0]
        for row in db.query(ExerciseDef.id)
        .filter(ExerciseDef.id.in_(all_exercise_ids))
        .all()
    }

    sessions_created = 0
    sets_created = 0
    errors: list[ImportError] = []

    for i, s in enumerate(sessions):
        invalid = [
            e.exercise_id
            for e in s.exercises
            if e.exercise_id not in valid_ids
        ]
        if invalid:
            errors.append(
                ImportError(
                    index=i,
                    reason=f"exercise_id {invalid[0]} does not exist",
                )
            )
            continue

        workout = Workout(logged_at=s.logged_at, user_id=user_id)
        db.add(workout)
        db.flush()

        for exercise in s.exercises:
            for j, ex_set in enumerate(exercise.sets):
                db.add(Exercise(
                    session_id=workout.id,
                    exercise_id=exercise.exercise_id,
                    set_number=j + 1,
                    reps=ex_set.reps,
                    weight_lbs=ex_set.weight_lbs,
                ))
                sets_created += 1

        sessions_created += 1

    db.commit()
    return ImportResponse(
        sessions_created=sessions_created,
        sets_created=sets_created,
        errors=errors,
    )
```

- [ ] **Step 4: Add the route to `app/api/workout_routes.py`**

Add at the top of the file, update the imports to include the new schemas:

```python
from app.api.schemas import (
    ImportResponse,
    WorkoutDetailed,
    WorkoutImportRequest,
    WorkoutRequest,
    WorkoutResponse,
)
```

Add the import of `import_workouts` to the service imports:

```python
from app.services.workout_service import (
    build_workout_detailed,
    delete_workout,
    get_all_workouts,
    get_workout,
    import_workouts,
    log_workout,
    update_workout,
)
```

Add the route after the existing `create_workout` handler:

```python
@router.post("/workouts/import", response_model=ImportResponse)
def batch_import_workouts(
    sessions: list[WorkoutImportRequest],
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Bulk-insert workout sessions; admin only, demo users blocked."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Admin access required"
        )
    return import_workouts(db, sessions, int(current_user["sub"]))
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
source .venv/bin/activate && pytest tests/test_import.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/workout_service.py \
        app/api/workout_routes.py \
        tests/test_import.py
git commit -m "feat: add POST /api/workouts/import for admin bulk insert"
```
