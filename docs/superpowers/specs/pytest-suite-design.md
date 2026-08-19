# Pytest Suite Design

**Date:** 2026-07-28
**Goal:** Add a comprehensive pytest suite covering every API endpoint, service layer, and seed logic. Zero tests exist today.

---

## Dependencies

Add to `requirements.txt`:
```
pytest
httpx
```

`httpx` is required by FastAPI's `TestClient` (Starlette 0.20+ uses it internally).

---

## File Structure

```
GymLog/
├── tests/
│   ├── __init__.py              ← empty
│   ├── conftest.py              ← fixtures and shared helpers
│   ├── test_exercises.py        ← exercise CRUD + progression endpoints (24 tests)
│   ├── test_workouts.py         ← workout CRUD endpoints (16 tests)
│   └── test_seed.py             ← seed idempotency (4 tests, marked slow)
├── app/
│   └── ...
└── pytest.ini
```

---

## `pytest.ini`

```ini
[pytest]
testpaths = tests
pythonpath = .

markers =
    slow: marks tests as slow (run with -m slow)
```

`pythonpath = .` makes `from app.main import app` resolve when running pytest from the project root.

---

## `app/main.py` change

Wrap the seed call in a `TESTING` guard to prevent it running during test collection:

```python
import os
# existing imports...

if not os.getenv("TESTING"):
    with SessionLocal() as db:
        seed_exercises(db)
```

Without this, importing `app.main` in tests would trigger the seed against the real SQLite file on every test run (slow in CI, untidy side effect).

---

## `tests/conftest.py`

```python
import os
os.environ["TESTING"] = "1"  # must be set before app.main is imported

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.main import app

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def _override_get_db():
        yield db
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### Key implementation notes

- **`StaticPool`** keeps a single connection alive for the engine. Without it, `sqlite:///:memory:` gives each new connection its own empty database — `create_all` and test sessions would see different databases.
- **`autouse=True`** on `setup_database` means every test starts with fresh tables, no pollution between tests.
- **`client` reuses the `db` session** via the dependency override. This ensures data inserted directly through `db` is visible to endpoint handlers and vice versa.
- **`os.environ["TESTING"] = "1"` is set before the import** of `app.main` to prevent the seed from running.
- **`app.dependency_overrides.clear()`** in teardown prevents leaks between tests.
- **Do not call `seed_exercises` in conftest.** Tests create only the minimal data they need via helper functions.

---

## Helper factory functions

Defined at the top of each test file:

```python
from app.model.models import MuscleGroup, ExerciseDef

def make_muscle_group(db, name="pectorals"):
    mg = MuscleGroup(name=name)
    db.add(mg)
    db.commit()
    db.refresh(mg)
    return mg

def make_exercise(db, name="Bench Press", equipment="barbell",
                  instructions="Press the bar up", muscle_groups=None):
    ex = ExerciseDef(
        name=name,
        equipment=equipment,
        instructions=instructions,
        muscle_groups=muscle_groups or [],
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex
```

Note: `target` was removed from `ExerciseDef` — it does not appear in helpers, request bodies, or assertions anywhere in the suite.

---

## `tests/test_exercises.py` — 24 tests

### GET /api/exercises

| Test | Setup | Assert |
|------|-------|--------|
| `test_list_exercises_empty` | none | 200, `[]` |
| `test_list_exercises_returns_all` | 2 exercises | 200, list of 2, each has `id, name, equipment, instructions, muscle_groups` |
| `test_list_exercises_includes_muscle_groups` | 1 muscle group, 1 exercise linked to it | first exercise's `muscle_groups` has length 1 with correct `id` and `name` |

### POST /api/exercises

| Test | Setup | Assert |
|------|-------|--------|
| `test_create_exercise` | 1 muscle group | 201, `name == "Custom Press"`, `muscle_groups` length 1 |
| `test_create_exercise_no_muscle_groups` | none | 201, `muscle_groups == []`, `equipment` is null |
| `test_create_exercise_invalid_muscle_group_id` | none | 400 |
| `test_create_exercise_missing_name` | none | 422 |

### GET /api/exercise/{id}/info

| Test | Setup | Assert |
|------|-------|--------|
| `test_get_exercise_info` | 1 exercise | 200, `name`, `equipment`, `instructions` match |
| `test_get_exercise_info_not_found` | none | 404 |

### PUT /api/exercise/{id}

| Test | Setup | Assert |
|------|-------|--------|
| `test_update_exercise_name` | 1 exercise | 200, `name` updated, other fields unchanged |
| `test_update_exercise_muscle_groups` | 2 muscle groups, exercise linked to first | 200, `muscle_groups` contains only second |
| `test_update_exercise_multiple_fields` | 1 exercise | 200, `name`, `equipment`, `instructions` all updated |
| `test_update_exercise_not_found` | none | 404 |
| `test_update_exercise_name_conflict` | exercises A and B | PUT B with A's name → 409 |
| `test_update_exercise_same_name_no_conflict` | 1 exercise | PUT with its own name → 200 |
| `test_update_exercise_invalid_muscle_group_id` | 1 exercise | 400 |

### DELETE /api/exercise/{id}

| Test | Setup | Assert |
|------|-------|--------|
| `test_delete_exercise` | 1 exercise | 204, subsequent GET → 404 |
| `test_delete_exercise_not_found` | none | 404 |
| `test_delete_exercise_with_history` | exercise + workout referencing it | 409, subsequent GET → 200 (exercise survives) |

### GET /api/exercise/{id}/progression

| Test | Setup | Assert |
|------|-------|--------|
| `test_progression_no_history` | 1 exercise, no workouts | 200, `sessions == []`, `exercise_name` matches |
| `test_progression_with_history` | 1 exercise, 2 workouts at different timestamps | 200, `sessions` length 2, each has `sets`/`volume`/`best_set_weight`, chronological order |
| `test_progression_not_found` | none | 404 |

### GET /api/muscle-groups

| Test | Setup | Assert |
|------|-------|--------|
| `test_list_muscle_groups_empty` | none | 200, `[]` |
| `test_list_muscle_groups` | 3 muscle groups: "abs", "chest", "traps" | 200, length 3, alphabetical order |

---

## `tests/test_workouts.py` — 16 tests

### POST /api/workouts

| Test | Setup | Assert |
|------|-------|--------|
| `test_create_workout_single_exercise` | 1 exercise | 200, `exercises_logged == 1`, `sets_logged == 1` |
| `test_create_workout_multiple_exercises` | 2 exercises | 200, `exercises_logged == 2`, `sets_logged == 6` (3 sets each) |
| `test_create_workout_bodyweight_exercise` | 1 exercise | 200, `sets_logged == 1` (no `weight_lbs` in body) |
| `test_create_workout_with_notes` | 1 exercise | 200, GET detail → `notes == "Felt strong today"` |
| `test_create_workout_with_custom_timestamp` | 1 exercise | 200, GET detail → `logged_at` contains `"2026-01-15"` |
| `test_create_workout_empty_exercises` | none | 200, `exercises_logged == 0`, `sets_logged == 0` |

### GET /api/workouts

| Test | Setup | Assert |
|------|-------|--------|
| `test_list_workouts_empty` | none | 200, `[]` |
| `test_list_workouts` | 3 workouts | 200, length 3, each has `session_id`, `logged_at`, `exercises_logged`, `sets_logged` |
| `test_list_workouts_ordered_by_date_desc` | 2 workouts with explicit `logged_at` | first item is newer than second |

### GET /api/workout/{id}

| Test | Setup | Assert |
|------|-------|--------|
| `test_get_workout_detail` | 2 exercises with muscle groups, 2 sets each | 200, `exercises` length 2, each has `name`, non-empty `muscle_groups`, correct `sets` |
| `test_get_workout_not_found` | none | 404 |

### PUT /api/workout/{id}

| Test | Setup | Assert |
|------|-------|--------|
| `test_update_workout_replace_exercises` | 2 exercises, workout with A | PUT with B (3 sets) → 200, only B present, 3 sets |
| `test_update_workout_not_found` | none | 404 |

### DELETE /api/workout/{id}

| Test | Setup | Assert |
|------|-------|--------|
| `test_delete_workout` | 1 workout | response `{"deleted": <id>}`, GET → 404 |
| `test_delete_workout_not_found` | none | 404 |
| `test_delete_workout_cascades_sets` | workout with 3 sets | deleted, `db.query(Exercise).filter(...).count() == 0` |

---

## `tests/test_seed.py` — 4 tests (`@pytest.mark.slow`)

| Test | Assert |
|------|--------|
| `test_seed_populates_exercises` | `ExerciseDef.count() > 1000`, `MuscleGroup.count() > 30` |
| `test_seed_is_idempotent` | count after 2nd call == count after 1st call |
| `test_seed_aliases_collapsed` | `MuscleGroup(name="abs")` exists, `MuscleGroup(name="abdominals")` does not |
| `test_seed_exercises_have_muscle_groups` | an exercise with "Bench Press" in its name has non-empty `muscle_groups` |

---

## Running tests

```bash
# Fast suite (excludes seed tests)
pytest -m "not slow"

# Seed tests only
pytest -m slow

# Everything
pytest -v

# Inside Docker
docker compose exec app pytest -m "not slow"
```

---

## Out of scope

- Frontend/HTML tests
- Load or performance tests
- Mocking the file system or `exercises.json`
