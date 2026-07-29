# Pytest Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 44-test pytest suite covering every API endpoint, the service layer, and seed logic, with a fast subset (40 tests) runnable without touching the seed file.

**Architecture:** In-memory SQLite database with `StaticPool` ensures tests are fully isolated from production data. FastAPI's `get_db` dependency is overridden in fixtures so all HTTP calls and direct `db` access share the same session. A `TESTING` env var guard in `app/main.py` prevents the seed from running at import time.

**Tech Stack:** pytest, httpx, FastAPI TestClient, SQLAlchemy StaticPool, SQLite in-memory

## Global Constraints

- Do not add `target` anywhere — it was removed from `ExerciseDef` today; it must not appear in helpers, request bodies, or assertions
- `make_muscle_group` and `make_exercise` helpers are defined at the top of each test file, not in conftest
- All test functions are standalone — no shared state between tests
- Seed tests are marked `@pytest.mark.slow` and excluded from the default fast run
- Run commands: `pytest -m "not slow"` (fast), `pytest -m slow` (seed only), `pytest` (all)
- Never call `seed_exercises` from conftest or from non-seed test files

---

### Task 1: Infrastructure — dependencies, pytest.ini, main.py guard

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `TESTING` env var guard in `app/main.py` — consumed by Task 2's conftest which sets `os.environ["TESTING"] = "1"` before importing the app

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append two lines to `requirements.txt`:
```
pytest
httpx
```

- [ ] **Step 2: Create `pytest.ini` at the project root**

```ini
[pytest]
testpaths = tests
pythonpath = .

markers =
    slow: marks tests as slow (run with -m slow)
```

`pythonpath = .` is critical — without it `from app.main import app` fails at collection time because Python can't find the `app` package.

- [ ] **Step 3: Create `tests/__init__.py` (empty)**

Create an empty file at `tests/__init__.py`. This makes `tests/` a package so pytest can collect modules inside it correctly.

- [ ] **Step 4: Add `TESTING` guard to `app/main.py`**

Find these lines near the top of `app/main.py`:
```python
with SessionLocal() as db:
    seed_exercises(db)
```

Replace with:
```python
import os

if not os.getenv("TESTING"):
    with SessionLocal() as db:
        seed_exercises(db)
```

Add the `import os` at the top of the file with the other imports if it isn't already there.

- [ ] **Step 5: Verify the app still starts**

Run the app locally to confirm the guard doesn't break normal startup:
```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```
Expected: server starts, `/health` returns `{"status": "ok"}`. Ctrl-C to stop.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py app/main.py
git commit -m "test: add pytest infrastructure and TESTING guard"
```

---

### Task 2: Test fixtures (`tests/conftest.py`)

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: `setup_database` fixture (autouse) — creates/drops tables around every test
- Produces: `db` fixture — yields a `Session` connected to the in-memory test engine
- Produces: `client` fixture — yields a `TestClient` with `get_db` overridden to use the `db` fixture's session

- [ ] **Step 1: Create `tests/conftest.py`**

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

Why `StaticPool`: `sqlite:///:memory:` normally gives each connection its own isolated database. `StaticPool` forces all sessions to reuse one connection, so `create_all` and test sessions see the same tables and data.

Why the `db` session is shared with `client`: if a test inserts data via `db` and then calls an endpoint via `client`, the endpoint must see that data. Sharing the session object (not just the engine) makes this work without any extra commits.

- [ ] **Step 2: Verify fixtures load without error**

```bash
pytest --collect-only
```

Expected: pytest collects 0 items (no test files yet) without any import errors or tracebacks.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add conftest fixtures with in-memory SQLite and get_db override"
```

---

### Task 3: Exercise and muscle-group tests (`tests/test_exercises.py`)

**Files:**
- Create: `tests/test_exercises.py`

**Interfaces:**
- Consumes: `db` fixture, `client` fixture from `tests/conftest.py`
- Consumes: `ExerciseDef`, `MuscleGroup` from `app.model.models`
- Produces: 24 test functions

- [ ] **Step 1: Create `tests/test_exercises.py`**

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


# ---------------------------------------------------------------------------
# GET /api/exercises
# ---------------------------------------------------------------------------

def test_list_exercises_empty(client):
    r = client.get("/api/exercises")
    assert r.status_code == 200
    assert r.json() == []


def test_list_exercises_returns_all(client, db):
    make_exercise(db, name="Bench Press")
    make_exercise(db, name="Squat")
    r = client.get("/api/exercises")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for item in data:
        assert {"id", "name", "equipment", "instructions", "muscle_groups"}.issubset(item.keys())


def test_list_exercises_includes_muscle_groups(client, db):
    mg = make_muscle_group(db, name="pectorals")
    make_exercise(db, name="Bench Press", muscle_groups=[mg])
    r = client.get("/api/exercises")
    assert r.status_code == 200
    mgs = r.json()[0]["muscle_groups"]
    assert len(mgs) == 1
    assert mgs[0]["id"] == mg.id
    assert mgs[0]["name"] == "pectorals"


# ---------------------------------------------------------------------------
# POST /api/exercises
# ---------------------------------------------------------------------------

def test_create_exercise(client, db):
    mg = make_muscle_group(db)
    r = client.post("/api/exercises", json={
        "name": "Custom Press",
        "equipment": "dumbbell",
        "instructions": "Push up",
        "muscle_group_ids": [mg.id],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Custom Press"
    assert len(data["muscle_groups"]) == 1


def test_create_exercise_no_muscle_groups(client):
    r = client.post("/api/exercises", json={"name": "Plank", "muscle_group_ids": []})
    assert r.status_code == 201
    data = r.json()
    assert data["muscle_groups"] == []
    assert data["equipment"] is None


def test_create_exercise_invalid_muscle_group_id(client):
    r = client.post("/api/exercises", json={"name": "Bad Exercise", "muscle_group_ids": [9999]})
    assert r.status_code == 400


def test_create_exercise_missing_name(client):
    r = client.post("/api/exercises", json={"muscle_group_ids": []})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/info
# ---------------------------------------------------------------------------

def test_get_exercise_info(client, db):
    ex = make_exercise(db, name="Bench Press", equipment="barbell", instructions="Press up")
    r = client.get(f"/api/exercise/{ex.id}/info")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press up"


def test_get_exercise_info_not_found(client):
    r = client.get("/api/exercise/9999/info")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_update_exercise_name(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Incline Bench Press"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Incline Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press the bar up"


def test_update_exercise_muscle_groups(client, db):
    mg1 = make_muscle_group(db, name="pectorals")
    mg2 = make_muscle_group(db, name="triceps")
    ex = make_exercise(db, muscle_groups=[mg1])
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [mg2.id]})
    assert r.status_code == 200
    data = r.json()
    assert len(data["muscle_groups"]) == 1
    assert data["muscle_groups"][0]["id"] == mg2.id


def test_update_exercise_multiple_fields(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={
        "name": "New Name",
        "equipment": "cable",
        "instructions": "Pull down",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "New Name"
    assert data["equipment"] == "cable"
    assert data["instructions"] == "Pull down"


def test_update_exercise_not_found(client):
    r = client.put("/api/exercise/9999", json={"name": "Ghost"})
    assert r.status_code == 404


def test_update_exercise_name_conflict(client, db):
    make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.put(f"/api/exercise/{ex_b.id}", json={"name": "Bench Press"})
    assert r.status_code == 409


def test_update_exercise_same_name_no_conflict(client, db):
    ex = make_exercise(db, name="Bench Press")
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Bench Press"})
    assert r.status_code == 200


def test_update_exercise_invalid_muscle_group_id(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [9999]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_delete_exercise(client, db):
    ex = make_exercise(db)
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 204
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 404


def test_delete_exercise_not_found(client):
    r = client.delete("/api/exercise/9999")
    assert r.status_code == 404


def test_delete_exercise_with_history(client, db):
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 409
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 200


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/progression
# ---------------------------------------------------------------------------

def test_progression_no_history(client, db):
    ex = make_exercise(db, name="Bench Press")
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == []
    assert data["exercise_name"] == "Bench Press"


def test_progression_with_history(client, db):
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]}],
        "logged_at": "2026-01-01T08:00:00",
    })
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 110}]}],
        "logged_at": "2026-01-15T08:00:00",
    })
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert len(data["sessions"]) == 2
    s0, s1 = data["sessions"]
    assert s0["logged_at"] < s1["logged_at"]
    for s in data["sessions"]:
        assert "sets" in s
        assert "volume" in s
        assert "best_set_weight" in s


def test_progression_not_found(client):
    r = client.get("/api/exercise/9999/progression")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/muscle-groups
# ---------------------------------------------------------------------------

def test_list_muscle_groups_empty(client):
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    assert r.json() == []


def test_list_muscle_groups(client, db):
    for name in ["traps", "abs", "chest"]:
        make_muscle_group(db, name=name)
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    names = [item["name"] for item in data]
    assert names == sorted(names)
```

- [ ] **Step 2: Run the exercise tests**

```bash
pytest tests/test_exercises.py -v
```

Expected: 24 passed. If any fail, the failure message will identify exactly which assertion failed — fix the test or the implementation as appropriate before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_exercises.py
git commit -m "test: add 24 exercise and muscle-group endpoint tests"
```

---

### Task 4: Workout tests (`tests/test_workouts.py`)

**Files:**
- Create: `tests/test_workouts.py`

**Interfaces:**
- Consumes: `db` fixture, `client` fixture from `tests/conftest.py`
- Consumes: `ExerciseDef`, `MuscleGroup`, `Exercise` from `app.model.models`
- Produces: 16 test functions

- [ ] **Step 1: Create `tests/test_workouts.py`**

```python
from app.model.models import MuscleGroup, ExerciseDef, Exercise


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


# ---------------------------------------------------------------------------
# POST /api/workouts
# ---------------------------------------------------------------------------

def test_create_workout_single_exercise(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert data["exercises_logged"] == 1
    assert data["sets_logged"] == 1


def test_create_workout_multiple_exercises(client, db):
    ex1 = make_exercise(db, name="Bench Press")
    ex2 = make_exercise(db, name="Squat")
    r = client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex1.id, "sets": [
                {"reps": 5, "weight_lbs": 135},
                {"reps": 5, "weight_lbs": 145},
                {"reps": 5, "weight_lbs": 155},
            ]},
            {"exercise_id": ex2.id, "sets": [
                {"reps": 5, "weight_lbs": 185},
                {"reps": 5, "weight_lbs": 195},
                {"reps": 5, "weight_lbs": 205},
            ]},
        ]
    })
    assert r.status_code == 200
    data = r.json()
    assert data["exercises_logged"] == 2
    assert data["sets_logged"] == 6


def test_create_workout_bodyweight_exercise(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 10}]}]
    })
    assert r.status_code == 200
    assert r.json()["sets_logged"] == 1


def test_create_workout_with_notes(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}],
        "notes": "Felt strong today",
    })
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert r2.status_code == 200
    assert r2.json()["notes"] == "Felt strong today"


def test_create_workout_with_custom_timestamp(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}],
        "logged_at": "2026-01-15T08:00:00",
    })
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert "2026-01-15" in r2.json()["logged_at"]


def test_create_workout_empty_exercises(client):
    r = client.post("/api/workouts", json={"exercises": []})
    assert r.status_code == 200
    data = r.json()
    assert data["exercises_logged"] == 0
    assert data["sets_logged"] == 0


# ---------------------------------------------------------------------------
# GET /api/workouts
# ---------------------------------------------------------------------------

def test_list_workouts_empty(client):
    r = client.get("/api/workouts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_workouts(client, db):
    ex = make_exercise(db)
    for _ in range(3):
        client.post("/api/workouts", json={
            "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
        })
    r = client.get("/api/workouts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    for item in data:
        assert "session_id" in item
        assert "logged_at" in item
        assert "exercises_logged" in item
        assert "sets_logged" in item


def test_list_workouts_ordered_by_date_desc(client, db):
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]}],
        "logged_at": "2026-01-01T08:00:00",
    })
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 110}]}],
        "logged_at": "2026-06-01T08:00:00",
    })
    r = client.get("/api/workouts")
    data = r.json()
    assert data[0]["logged_at"] > data[1]["logged_at"]


# ---------------------------------------------------------------------------
# GET /api/workout/{id}
# ---------------------------------------------------------------------------

def test_get_workout_detail(client, db):
    mg = make_muscle_group(db, name="pectorals")
    ex1 = make_exercise(db, name="Bench Press", muscle_groups=[mg])
    ex2 = make_exercise(db, name="Squat", muscle_groups=[mg])
    r = client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex1.id, "sets": [{"reps": 5, "weight_lbs": 135}, {"reps": 5, "weight_lbs": 145}]},
            {"exercise_id": ex2.id, "sets": [{"reps": 5, "weight_lbs": 185}, {"reps": 5, "weight_lbs": 195}]},
        ]
    })
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["exercises"]) == 2
    for ex in data["exercises"]:
        assert "name" in ex
        assert len(ex["muscle_groups"]) > 0
        assert len(ex["sets"]) == 2
        assert ex["sets"][0]["reps"] == 5


def test_get_workout_not_found(client):
    r = client.get("/api/workout/9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/workout/{id}
# ---------------------------------------------------------------------------

def test_update_workout_replace_exercises(client, db):
    ex_a = make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex_a.id, "sets": [
            {"reps": 5, "weight_lbs": 135},
            {"reps": 5, "weight_lbs": 145},
        ]}]
    })
    session_id = r.json()["session_id"]
    r2 = client.put(f"/api/workout/{session_id}", json={
        "exercises": [{"exercise_id": ex_b.id, "sets": [
            {"reps": 8, "weight_lbs": 185},
            {"reps": 8, "weight_lbs": 195},
            {"reps": 8, "weight_lbs": 205},
        ]}]
    })
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["exercise_id"] == ex_b.id
    assert len(data["exercises"][0]["sets"]) == 3


def test_update_workout_not_found(client, db):
    ex = make_exercise(db)
    r = client.put("/api/workout/9999", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workout/{id}
# ---------------------------------------------------------------------------

def test_delete_workout(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    session_id = r.json()["session_id"]
    r2 = client.delete(f"/api/workout/{session_id}")
    assert r2.json() == {"deleted": session_id}
    assert client.get(f"/api/workout/{session_id}").status_code == 404


def test_delete_workout_not_found(client):
    r = client.delete("/api/workout/9999")
    assert r.status_code == 404


def test_delete_workout_cascades_sets(client, db):
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [
            {"reps": 5, "weight_lbs": 135},
            {"reps": 5, "weight_lbs": 145},
            {"reps": 5, "weight_lbs": 155},
        ]}]
    })
    session_id = r.json()["session_id"]
    client.delete(f"/api/workout/{session_id}")
    count = db.query(Exercise).filter(Exercise.session_id == session_id).count()
    assert count == 0
```

- [ ] **Step 2: Run the workout tests**

```bash
pytest tests/test_workouts.py -v
```

Expected: 16 passed. Fix any failures before continuing.

- [ ] **Step 3: Run the full fast suite to check for interactions**

```bash
pytest -m "not slow" -v
```

Expected: 40 passed (24 exercise + 16 workout).

- [ ] **Step 4: Commit**

```bash
git add tests/test_workouts.py
git commit -m "test: add 16 workout endpoint tests"
```

---

### Task 5: Seed tests (`tests/test_seed.py`)

**Files:**
- Create: `tests/test_seed.py`

**Interfaces:**
- Consumes: `db` fixture from `tests/conftest.py`
- Consumes: `seed_exercises` from `app.db.seed`
- Consumes: `ExerciseDef`, `MuscleGroup` from `app.model.models`
- Produces: 4 test functions marked `@pytest.mark.slow`

- [ ] **Step 1: Create `tests/test_seed.py`**

```python
import pytest
from app.db.seed import seed_exercises
from app.model.models import ExerciseDef, MuscleGroup


@pytest.mark.slow
def test_seed_populates_exercises(db):
    seed_exercises(db)
    assert db.query(ExerciseDef).count() > 1000
    assert db.query(MuscleGroup).count() > 30


@pytest.mark.slow
def test_seed_is_idempotent(db):
    seed_exercises(db)
    count_after_first = db.query(ExerciseDef).count()
    seed_exercises(db)
    count_after_second = db.query(ExerciseDef).count()
    assert count_after_first == count_after_second


@pytest.mark.slow
def test_seed_aliases_collapsed(db):
    seed_exercises(db)
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abs").count() == 1
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abdominals").count() == 0


@pytest.mark.slow
def test_seed_exercises_have_muscle_groups(db):
    seed_exercises(db)
    ex = db.query(ExerciseDef).filter(ExerciseDef.name.ilike("%bench press%")).first()
    assert ex is not None
    assert len(ex.muscle_groups) > 0
```

- [ ] **Step 2: Run only the seed tests**

```bash
pytest -m slow -v
```

Expected: 4 passed (these are slow — expect 10–30 seconds).

- [ ] **Step 3: Run the complete suite**

```bash
pytest -v
```

Expected: 44 passed total (24 + 16 + 4).

- [ ] **Step 4: Confirm the fast suite still excludes seed tests**

```bash
pytest -m "not slow" -v
```

Expected: 40 passed, 4 deselected.

- [ ] **Step 5: Commit**

```bash
git add tests/test_seed.py
git commit -m "test: add 4 seed idempotency tests (marked slow)"
```
