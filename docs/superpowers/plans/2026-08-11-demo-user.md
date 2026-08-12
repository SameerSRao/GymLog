# Demo User Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only demo account so unauthenticated visitors can click "Try Demo" on the login page and immediately explore the app with pre-seeded realistic workout data.

**Architecture:** `is_demo` flag on `User` propagates into the JWT so every layer (backend dependency + frontend JS) can detect it without an extra DB lookup. A single `require_not_demo` FastAPI dependency guards all mutation routes. `seed_demo_data()` is called idempotently at startup and refreshes demo workouts when they are >30 days old.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, python-jose JWT, vanilla JS, pytest with `TestClient`

## Global Constraints

- Max line length: 79 chars for code, 72 for docstrings
- Every function/method/class must have a docstring (PEP 257 one-liner form)
- Two blank lines between top-level definitions
- Imports grouped: stdlib → third-party → local, each group blank-line separated
- Run tests with: `pytest tests/ -v` from `/Users/sameerrao/code/GymLog`
- Activate venv first: `source .venv/bin/activate`
- **After Task 1, reset the database** — SQLAlchemy's `create_all` won't add new columns to an existing SQLite file: `rm data/gymlog.db && docker compose down && docker compose up --build`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `app/model/models.py` | Add `is_demo` column to `User` |
| Modify | `app/api/auth_routes.py` | Include `is_demo` in JWT; add `GET /api/auth/demo` |
| Modify | `app/db/seed.py` | Add `seed_demo_data(db)` |
| Modify | `app/main.py` | Call `seed_demo_data` at startup |
| Modify | `app/api/workout_routes.py` | Apply `require_not_demo` to mutation routes |
| Modify | `app/api/exercise_routes.py` | Apply `require_not_demo` to mutation routes |
| Modify | `app/api/routine_routes.py` | Apply `require_not_demo` to mutation routes |
| Modify | `app/api/chat_routes.py` | Apply `require_not_demo` to `POST /api/chat` |
| Modify | `app/static/auth.js` | Add `isDemo()` helper |
| Modify | `app/static/login.html` | Add "Try Demo" button |
| Modify | `app/static/dashboard.html` | Add demo banner |
| Modify | `app/static/workouts.html` | Hide "New Workout" button for demo |
| Modify | `app/static/workout.html` | Hide edit/delete for demo |
| Modify | `app/static/index.html` | Redirect demo users away from log page |
| Modify | `app/static/routines.html` | Hide create/edit/delete for demo |
| Modify | `app/static/exercises.html` | Hide custom exercise button for demo |
| Create | `tests/test_demo.py` | Tests for demo auth and read-only enforcement |

---

### Task 1: Add `is_demo` to User Model

**Files:**
- Modify: `app/model/models.py`

**Interfaces:**
- Produces: `User.is_demo: bool` (default `False`)

- [ ] **Step 1: Add the column to the `User` model in `app/model/models.py`**

In the `User` class, after the `is_premium` field (currently around line 44), add:

```python
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
```

- [ ] **Step 2: Reset the database**

SQLAlchemy's `create_all` creates tables but does not alter existing ones. You must reset the DB so the new column is picked up:

```bash
rm data/gymlog.db
docker compose down
docker compose up --build
```

For the test suite, no action needed — tests use an in-memory SQLite DB recreated per test.

- [ ] **Step 3: Run the test suite to confirm nothing is broken**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all existing tests PASS (the new column has a default, so no existing test data breaks).

- [ ] **Step 4: Commit**

```bash
git add app/model/models.py
git commit -m "feat: add is_demo column to User model"
```

---

### Task 2: Propagate `is_demo` into JWT + Add `isDemo()` to `auth.js`

**Files:**
- Modify: `app/api/auth_routes.py`
- Modify: `app/static/auth.js`

**Interfaces:**
- Consumes: `User.is_demo` from Task 1
- Produces:
  - JWT payload now includes `"is_demo": bool`
  - `window.isDemo()` — returns `true` if the current token has `is_demo: true`
  - `require_not_demo(current_user: dict) -> dict` dependency exported from `auth_routes`

- [ ] **Step 1: Update `_make_token` in `app/api/auth_routes.py` to include `is_demo`**

Find `_make_token` (currently around line 30). Change it to:

```python
def _make_token(user) -> str:
    """Return a signed JWT for user with id, username, flags."""
    return create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
            "is_demo": user.is_demo,
        },
        timedelta(hours=_TOKEN_EXPIRE_HOURS),
    )
```

- [ ] **Step 2: Add `require_not_demo` dependency to `app/api/auth_routes.py`**

Add after `get_current_user` (around line 28):

```python
def require_not_demo(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Raise 403 if the caller is a demo account."""
    if current_user.get("is_demo"):
        raise HTTPException(
            status_code=403,
            detail="Demo accounts cannot perform this action",
        )
    return current_user
```

- [ ] **Step 3: Add `isDemo()` to `app/static/auth.js`**

After the `isPremium` function (around line 39), add:

```javascript
  function isDemo() { var p = getTokenPayload(); return p ? Boolean(p.is_demo) : false; }
```

Also expose it on `window` by adding to the bottom of the IIFE exports:

```javascript
  window.isDemo = isDemo;
```

- [ ] **Step 4: Run the test suite**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS. The `_make_token` change is backward-compatible — existing tests override `get_current_user` directly and don't go through the token.

- [ ] **Step 5: Commit**

```bash
git add app/api/auth_routes.py app/static/auth.js
git commit -m "feat: include is_demo in JWT; add require_not_demo dependency and isDemo() helper"
```

---

### Task 3: `seed_demo_data` + Startup Call

**Files:**
- Modify: `app/db/seed.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `User`, `Workout`, `Exercise`, `ExerciseDef` ORM models; `hash_password` from `auth_service`
- Produces: `seed_demo_data(db: Session) -> None` — idempotent; re-seeds workouts when newest is >30 days old

- [ ] **Step 1: Add `seed_demo_data` to `app/db/seed.py`**

Add these imports at the top of `seed.py` (in the stdlib group):

```python
from datetime import datetime, timedelta, timezone
```

Add these to the local imports group:

```python
from app.model.models import Exercise, ExerciseDef, User, Workout
from app.services.auth_service import hash_password
```

Then add the function after `seed_exercises`:

```python
def seed_demo_data(db: Session) -> None:
    """Create demo user and refresh workout data when stale (>30 days old)."""
    demo = db.query(User).filter(User.username == "demo").first()
    if not demo:
        demo = User(
            username="demo",
            password_hash=hash_password("demo-no-login"),
            is_demo=True,
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

    now = datetime.now(timezone.utc)
    newest = (
        db.query(Workout)
        .filter(Workout.user_id == demo.id)
        .order_by(Workout.logged_at.desc())
        .first()
    )

    if newest is not None:
        newest_dt = newest.logged_at
        if newest_dt.tzinfo is None:
            newest_dt = newest_dt.replace(tzinfo=timezone.utc)
        if (now - newest_dt).days < 30:
            return

    db.query(Workout).filter(Workout.user_id == demo.id).delete()
    db.commit()

    exercises = (
        db.query(ExerciseDef)
        .filter(ExerciseDef.user_id.is_(None))
        .limit(5)
        .all()
    )
    if not exercises:
        return

    ex_ids = [e.id for e in exercises]
    for week in range(8):
        for day_offset in [1, 3, 5]:
            days_ago = (7 * week) + day_offset
            workout_date = now - timedelta(days=days_ago)
            session = Workout(
                logged_at=workout_date,
                user_id=demo.id,
            )
            db.add(session)
            db.flush()

            for ex_id in ex_ids[:2]:
                base_weight = float(100 + (week * 5))
                for set_num in range(1, 4):
                    db.add(Exercise(
                        session_id=session.id,
                        exercise_id=ex_id,
                        set_number=set_num,
                        reps=5,
                        weight_lbs=base_weight,
                    ))

    db.commit()
```

- [ ] **Step 2: Call `seed_demo_data` in `app/main.py`**

Find the startup block (around line 16):

```python
if not os.getenv("TESTING"):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_exercises(db)
```

Change it to:

```python
if not os.getenv("TESTING"):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_exercises(db)
        seed_demo_data(db)
```

Also update the import at the top of `main.py`:

```python
from app.db.seed import seed_demo_data, seed_exercises
```

- [ ] **Step 3: Run the test suite**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS. `seed_demo_data` is never called in tests because `TESTING=1` env var skips the startup block.

- [ ] **Step 4: Commit**

```bash
git add app/db/seed.py app/main.py
git commit -m "feat: add seed_demo_data; call at startup to keep demo workouts current"
```

---

### Task 4: `GET /api/auth/demo` Endpoint + "Try Demo" Button

**Files:**
- Modify: `app/api/auth_routes.py`
- Modify: `app/static/login.html`

**Interfaces:**
- Consumes: `_make_token` (updated in Task 2); `get_user_by_username` from `user_service`
- Produces: `GET /api/auth/demo` returns `TokenResponse`

- [ ] **Step 1: Write the failing test in `tests/test_demo.py`**

Create `tests/test_demo.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app
from conftest import make_exercise, make_user


@pytest.fixture()
def demo_user(db):
    """Create and return a demo user."""
    user = make_user(db, username="demo", password="x")
    user.is_demo = True
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def demo_client(db, demo_user):
    """Return a TestClient authenticated as the demo user."""
    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(demo_user.id),
            "username": demo_user.username,
            "is_admin": False,
            "is_premium": False,
            "is_demo": True,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/auth/demo
# ---------------------------------------------------------------------------

def test_demo_login_returns_token(db, demo_user):
    """Assert GET /api/auth/demo returns a JWT when demo user exists."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/api/auth/demo")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_demo_login_503_when_no_demo_user(db):
    """Assert GET /api/auth/demo returns 503 when demo user is not seeded."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/api/auth/demo")
    app.dependency_overrides.clear()

    assert r.status_code == 503
```

- [ ] **Step 2: Run to confirm failure**

```bash
source .venv/bin/activate && pytest tests/test_demo.py::test_demo_login_returns_token tests/test_demo.py::test_demo_login_503_when_no_demo_user -v
```

Expected: FAIL — route does not exist yet.

- [ ] **Step 3: Add `GET /api/auth/demo` to `app/api/auth_routes.py`**

Add after the `register` route:

```python
@router.get("/auth/demo", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """Return a JWT for the demo user; 503 if demo user is not seeded."""
    user = get_user_by_username(db, "demo")
    if not user or not user.is_demo:
        raise HTTPException(
            status_code=503, detail="Demo unavailable"
        )
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && pytest tests/test_demo.py -v
```

Expected: the two auth tests PASS.

- [ ] **Step 5: Add "Try Demo" button to `app/static/login.html`**

Add a demo button style in the `<style>` block, after the `button:disabled` rule:

```css
    .demo-btn {
      width: 100%;
      background: transparent;
      color: #888;
      border: 1px solid #2a2a2a;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 500;
      padding: 12px;
      cursor: pointer;
      margin-top: 10px;
    }
    .demo-btn:hover { border-color: #555; color: #f0f0f0; }
```

After the `<button id="btn">Sign in</button>` line, add:

```html
    <button class="demo-btn" id="demo-btn">Try Demo</button>
```

In the `<script>` block, add after the `btn.addEventListener` lines:

```javascript
    document.getElementById('demo-btn').addEventListener('click', async function() {
      errorEl.textContent = '';
      try {
        const res = await fetch('/api/auth/demo');
        if (res.ok) {
          const data = await res.json();
          localStorage.setItem('access_token', data.access_token);
          window.location.replace('/');
        } else {
          errorEl.textContent = 'Demo is unavailable right now.';
        }
      } catch {
        errorEl.textContent = 'Something went wrong. Try again.';
      }
    });
```

- [ ] **Step 6: Run full test suite**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/api/auth_routes.py app/static/login.html tests/test_demo.py
git commit -m "feat: add GET /api/auth/demo endpoint and Try Demo button"
```

---

### Task 5: Block Mutations for Demo Users

**Files:**
- Modify: `app/api/workout_routes.py`
- Modify: `app/api/exercise_routes.py`
- Modify: `app/api/routine_routes.py`
- Modify: `app/api/chat_routes.py`

**Interfaces:**
- Consumes: `require_not_demo` from `auth_routes` (Task 2)

- [ ] **Step 1: Add tests to `tests/test_demo.py` for mutation blocking**

Append to `tests/test_demo.py`:

```python
# ---------------------------------------------------------------------------
# Read-only enforcement — demo user cannot mutate data
# ---------------------------------------------------------------------------

def test_demo_cannot_create_workout(demo_client, db):
    """Assert POST /api/workouts returns 403 for demo users."""
    ex = make_exercise(db)
    r = demo_client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5}]}]
    })
    assert r.status_code == 403


def test_demo_cannot_update_workout(demo_client, db, demo_user):
    """Assert PUT /api/workout/{id} returns 403 for demo users."""
    from app.model.models import Workout
    session = Workout(user_id=demo_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    ex = make_exercise(db)
    r = demo_client.put(f"/api/workout/{session.id}", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5}]}]
    })
    assert r.status_code == 403


def test_demo_cannot_delete_workout(demo_client, db, demo_user):
    """Assert DELETE /api/workout/{id} returns 403 for demo users."""
    from app.model.models import Workout
    session = Workout(user_id=demo_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    r = demo_client.delete(f"/api/workout/{session.id}")
    assert r.status_code == 403


def test_demo_can_read_workouts(demo_client):
    """Assert GET /api/workouts returns 200 for demo users."""
    r = demo_client.get("/api/workouts")
    assert r.status_code == 200


def test_demo_cannot_create_routine(demo_client):
    """Assert POST /api/routines returns 403 for demo users."""
    r = demo_client.post("/api/routines", json={
        "name": "My Routine", "exercises": []
    })
    assert r.status_code == 403


def test_demo_cannot_chat(demo_client):
    """Assert POST /api/chat returns 403 for demo users."""
    r = demo_client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "hello"}]
    })
    assert r.status_code == 403
```

- [ ] **Step 2: Run to confirm failures**

```bash
source .venv/bin/activate && pytest tests/test_demo.py -v
```

Expected: the mutation-blocking tests FAIL (currently return 200, not 403).

- [ ] **Step 3: Apply `require_not_demo` to `app/api/workout_routes.py`**

Update imports at the top:

```python
from app.api.auth_routes import get_current_user, require_not_demo
```

For the three mutation routes, add `require_not_demo` as an additional dependency. Replace each handler signature as follows:

`create_workout`:
```python
@router.post("/workouts", response_model=WorkoutResponse)
def create_workout(
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Log a new workout session and return a summary."""
    user_id = int(current_user["sub"])
```

`replace_workout`:
```python
@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(
    session_id: int,
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Replace all exercises in a workout; 404 if not found or not owned."""
    session = update_workout(
        db, session_id, workout, int(current_user["sub"])
    )
```

`remove_workout`:
```python
@router.delete("/workout/{session_id}")
def remove_workout(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Delete a workout and all its sets; 404 if not found or not owned."""
    if not delete_workout(db, session_id, int(current_user["sub"])):
```

Note: `batch_import_workouts` already checks `is_admin` which implicitly blocks demo (demo is not admin), so no change needed there.

- [ ] **Step 4: Apply `require_not_demo` to mutation routes in `app/api/exercise_routes.py`**

Update imports:

```python
from app.api.auth_routes import get_current_user, require_not_demo
```

The router uses a router-level auth dependency (`dependencies=[Depends(get_current_user)]`). Individual mutation handlers may or may not have an explicit `current_user` parameter. The approach differs:

- **If a handler already has** `current_user: dict = Depends(get_current_user)` — replace the dependency: `current_user: dict = Depends(require_not_demo)`
- **If a handler has no explicit `current_user` param** — add one: `current_user: dict = Depends(require_not_demo)` (you don't need to use it; FastAPI runs the dependency for its side-effect of raising 403)

Read `app/api/exercise_routes.py` in full, then apply the above pattern to `POST /exercises`, `PUT /exercise/{id}`, and `DELETE /exercise/{id}`.

- [ ] **Step 5: Apply `require_not_demo` to `app/api/routine_routes.py`**

Same pattern as Step 4: update imports, read the file, then add/replace `require_not_demo` on `POST /routines`, `PUT /routine/{id}`, `DELETE /routine/{id}`.

- [ ] **Step 6: Apply `require_not_demo` to `POST /api/chat` in `app/api/chat_routes.py`**

Update imports:

```python
from app.api.auth_routes import get_current_user, require_not_demo
```

Find the `chat` route handler and add `require_not_demo` as a dependency. The exact change depends on the current signature — read the file and replace `Depends(get_current_user)` on the chat handler with `Depends(require_not_demo)`.

- [ ] **Step 7: Run tests to confirm they pass**

```bash
source .venv/bin/activate && pytest tests/test_demo.py -v
```

Expected: all demo tests PASS.

- [ ] **Step 8: Run full test suite for regressions**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add app/api/workout_routes.py \
        app/api/exercise_routes.py \
        app/api/routine_routes.py \
        app/api/chat_routes.py \
        tests/test_demo.py
git commit -m "feat: block all mutations for demo users via require_not_demo"
```

---

### Task 6: Frontend — Hide Write Controls for Demo Users

**Files:**
- Modify: `app/static/dashboard.html`
- Modify: `app/static/workouts.html`
- Modify: `app/static/workout.html`
- Modify: `app/static/index.html`
- Modify: `app/static/routines.html`
- Modify: `app/static/exercises.html`

**Interfaces:**
- Consumes: `window.isDemo()` from `auth.js` (Task 2)

The pattern for every page is:

1. In the page's `<script>`, after `checkAuth()`, call `isDemo()`.
2. If `true`, hide mutation controls and optionally show a "Sign up" nudge.

Read each file in full before editing so you have the correct element IDs and structure.

- [ ] **Step 1: `app/static/dashboard.html` — add demo banner**

After `checkAuth()` in the script, add:

```javascript
if (isDemo()) {
  const banner = document.createElement('div');
  banner.style.cssText =
    'background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;' +
    'color:#888;font-size:0.85rem;padding:10px 14px;margin-bottom:16px;' +
    'text-align:center;';
  banner.innerHTML =
    'You\'re in demo mode. ' +
    '<a href="/register" style="color:#f0f0f0;">Sign up</a> to log workouts.';
  document.body.prepend(banner);
}
```

- [ ] **Step 2: `app/static/workouts.html` — hide "New Workout" / "Log Workout" button**

Read the file to identify the element ID of the "log workout" / "new workout" button. After `checkAuth()`:

```javascript
if (isDemo()) {
  const logBtn = document.getElementById('<actual-button-id>');
  if (logBtn) logBtn.style.display = 'none';
}
```

Replace `<actual-button-id>` with the real ID found in the file.

- [ ] **Step 3: `app/static/workout.html` — hide edit and delete buttons**

Read the file to find the edit and delete button element IDs. After `checkAuth()`:

```javascript
if (isDemo()) {
  ['<edit-btn-id>', '<delete-btn-id>'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}
```

Replace the IDs with the real ones from the file.

- [ ] **Step 4: `app/static/index.html` (workout log page) — redirect demo users**

This is the "Log Workout" page — a demo user navigating here should be redirected to `/workouts`. After `checkAuth()`:

```javascript
if (isDemo()) { window.location.replace('/workouts'); }
```

- [ ] **Step 5: `app/static/routines.html` — hide create/edit/delete controls**

Read the file to identify all mutation button IDs. After `checkAuth()`, hide them. Pattern:

```javascript
if (isDemo()) {
  ['<create-btn-id>'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  // Also hide any inline edit/delete buttons added dynamically:
  document.addEventListener('DOMContentLoaded', function() {
    if (!isDemo()) return;
    document.querySelectorAll(
      '.edit-btn, .delete-btn'   // replace with actual classes/selectors
    ).forEach(function(el) { el.style.display = 'none'; });
  });
}
```

Read the file to get the correct selectors before writing this code.

- [ ] **Step 6: `app/static/exercises.html` — hide custom exercise creation**

Read the file. If there's a "Create Exercise" button visible to regular users, hide it for demo:

```javascript
if (isDemo()) {
  var createBtn = document.getElementById('<create-exercise-btn-id>');
  if (createBtn) createBtn.style.display = 'none';
}
```

- [ ] **Step 7: Manually verify in browser**

Start the server:
```bash
docker compose up --build
```

1. Open `http://localhost:8000/login`
2. Click "Try Demo" — should land on dashboard with the demo banner
3. Navigate to `/workouts` — "New Workout" button should be gone
4. Try navigating to `/log` directly — should redirect to `/workouts`
5. Open a workout — edit/delete buttons should be hidden
6. Navigate to `/routines` — create/edit/delete controls hidden
7. Confirm read operations (viewing workouts, exercises, progression) all work normally

- [ ] **Step 8: Commit**

```bash
git add app/static/dashboard.html \
        app/static/workouts.html \
        app/static/workout.html \
        app/static/index.html \
        app/static/routines.html \
        app/static/exercises.html
git commit -m "feat: hide write controls and redirect demo users on log page"
```
