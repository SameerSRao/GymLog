# Multi-User Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user accounts with self-registration (signup-code gated), JWT auth, scoped data, exercise ownership permissions, and a premium flag gating the chatbot.

**Architecture:** Add a `users` table; add `user_id` FK to `workout_sessions` and `routines` (NOT NULL) and to `exercises` (nullable — NULL = global/seeded, non-NULL = custom/private). Auth switches from env-var admin password to DB-backed user lookup. JWT payload carries `user_id`, `username`, `is_admin`, `is_premium` for zero-query permission checks.

**Tech Stack:** SQLAlchemy 2.0, FastAPI 0.136, Pydantic v2, python-jose, bcrypt, Python 3.12+

## Global Constraints

- All Python must follow PEP 8 (max 79 chars/line) and PEP 257 (every function/method/class has a docstring)
- Tests use pytest with in-memory SQLite; run with `pytest` from repo root
- Every new or modified function must have a docstring
- Reset the database before first run: `rm data/gymlog.db`
- `ADMIN_PASSWORD` env var is removed; add `SIGNUP_CODE` to `.env` and `.env.example`

---

## File Map

**New files:**
- `app/services/user_service.py` — `create_user`, `get_user_by_username`
- `app/admin.py` — CLI: `python -m app.admin promote <username> --admin --premium`
- `app/static/register.html` — registration page (username + password + signup code)
- `tests/test_models.py` — model column assertions
- `tests/test_admin.py` — admin flag assertions
- `tests/test_chat.py` — premium gate assertions

**Modified files:**
- `app/model/models.py` — add `User` model; add `user_id` to `Workout`, `Routine`, `ExerciseDef`
- `app/services/auth_service.py` — remove `ADMIN_PASSWORD`; add `check_signup_code`
- `app/api/auth_routes.py` — update login (username+password); add register endpoint
- `app/api/schemas.py` — add `RegisterRequest`; update `LoginRequest`; add `user_id` to `ExerciseDefSchema`
- `app/services/workout_service.py` — all functions accept and filter by `user_id: int`
- `app/api/workout_routes.py` — extract `user_id` from JWT; pass to services
- `app/services/routine_service.py` — all functions accept `user_id`; name conflict scoped per user
- `app/api/routine_routes.py` — extract `user_id` from JWT; pass to services
- `app/services/exercise_service.py` — user-scoped reads; ownership checks; scoped progression
- `app/api/exercise_routes.py` — extract `user_id` + `is_admin`; raise 403 on "forbidden"
- `app/services/chat_service.py` — `run_chat` accepts `user_id`; passes to `execute_tool`
- `app/services/chat_tools.py` — `execute_tool` accepts `user_id`; scopes data tools
- `app/api/chat_routes.py` — 403 for non-premium non-admin; pass `user_id` to `run_chat`
- `app/main.py` — add `/register` route
- `app/static/login.html` — add username field; update JS
- `app/static/auth.js` — add `getTokenPayload`, `getUsername`, `isAdmin`, `isPremium`, `getCurrentUserId`
- `app/static/dashboard.html` — show username in nav; lock chat for non-premium
- `app/static/exercises.html` — hide edit/delete for non-editable exercises
- `app/static/*.html` (all other pages) — show username in nav
- `tests/conftest.py` — add `user` + `admin_client` fixtures; update `make_user`, `make_exercise`
- `tests/test_auth.py` — update for username login + register endpoint
- `tests/test_exercises.py` — switch edit/delete tests to `admin_client`; add permission tests
- `tests/test_workouts.py` — add user-scoping assertion test
- `tests/test_routines.py` — add user-scoping assertion test
- `.env.example` — swap `ADMIN_PASSWORD` for `SIGNUP_CODE`

---

### Task 1: User Model

**Files:**
- Modify: `app/model/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `User` ORM class with columns `id`, `username`, `password_hash`, `is_admin`, `is_premium`, `created_at`; `Workout.user_id` (int, NOT NULL FK → users.id); `Routine.user_id` (int, NOT NULL FK → users.id); `ExerciseDef.user_id` (int | None, nullable FK → users.id)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
def test_user_model_has_expected_columns():
    """Assert User has all required columns."""
    from app.model.models import User
    cols = {c.name for c in User.__table__.columns}
    assert {
        "id", "username", "password_hash",
        "is_admin", "is_premium", "created_at",
    }.issubset(cols)


def test_workout_has_user_id_column():
    """Assert Workout has a non-nullable user_id FK column."""
    from app.model.models import Workout
    col = next(c for c in Workout.__table__.columns if c.name == "user_id")
    assert not col.nullable


def test_routine_has_user_id_column():
    """Assert Routine has a non-nullable user_id FK column."""
    from app.model.models import Routine
    col = next(c for c in Routine.__table__.columns if c.name == "user_id")
    assert not col.nullable


def test_exercise_def_has_nullable_user_id():
    """Assert ExerciseDef has a nullable user_id column."""
    from app.model.models import ExerciseDef
    col = next(
        c for c in ExerciseDef.__table__.columns if c.name == "user_id"
    )
    assert col.nullable is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `User` not found, `user_id` columns missing

- [ ] **Step 3: Update `app/model/models.py`**

Add `Boolean` to the sqlalchemy import line:

```python
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Table,
)
```

Add the `User` class before `Workout`:

```python
class User(Base):
    """A registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
```

Add `user_id` to `Workout` (after `raw_input`):

```python
user_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("users.id"), nullable=False
)
```

Add `user_id` to `Routine` (after `created_at`):

```python
user_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("users.id"), nullable=False
)
```

Add `user_id` to `ExerciseDef` (after `instructions`):

```python
user_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("users.id"), nullable=True
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/model/models.py tests/test_models.py
git commit -m "feat: add User model and user_id FKs to Workout, Routine, ExerciseDef"
```

---

### Task 2: User Service + Auth Overhaul + Conftest

**Files:**
- Create: `app/services/user_service.py`
- Modify: `app/services/auth_service.py`
- Modify: `app/api/auth_routes.py`
- Modify: `app/api/schemas.py`
- Modify: `app/main.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_auth.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `create_user(db, username, password) -> User`; `get_user_by_username(db, username) -> User | None`; `check_signup_code(code) -> bool`; `get_current_user() -> dict` with keys `sub` (str user_id), `username`, `is_admin`, `is_premium`; `POST /api/auth/register` (201); updated `POST /api/auth/login` (username + password)

- [ ] **Step 1: Write failing tests (replace `tests/test_auth.py` entirely)**

```python
# tests/test_auth.py
import os
from datetime import timedelta

os.environ.setdefault("SIGNUP_CODE", "testcode")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.auth_service import (
    check_signup_code,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Auth service unit tests
# ---------------------------------------------------------------------------

def test_verify_password_correct():
    """Assert verify_password returns True when plain matches the hash."""
    assert verify_password("mysecret", hash_password("mysecret")) is True


def test_verify_password_wrong():
    """Assert verify_password returns False when plain does not match."""
    assert verify_password("wrong", hash_password("mysecret")) is False


def test_check_signup_code_correct():
    """Assert check_signup_code returns True for the configured code."""
    assert check_signup_code("testcode") is True


def test_check_signup_code_wrong():
    """Assert check_signup_code returns False for the wrong code."""
    assert check_signup_code("wrongcode") is False


def test_create_access_token_returns_jwt():
    """Assert create_access_token returns a non-empty string."""
    token = create_access_token({"sub": "1"}, timedelta(minutes=30))
    assert isinstance(token, str) and len(token) > 0


def test_decode_returns_correct_claims():
    """Assert decode_access_token returns the encoded payload."""
    token = create_access_token(
        {"sub": "1", "username": "alice"}, timedelta(minutes=30)
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "alice"


def test_decode_raises_401_on_tampered_token():
    """Assert decode_access_token raises HTTPException 401 on bad signature."""
    token = create_access_token({"sub": "1"}, timedelta(minutes=30))
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token[:-5] + "XXXXX")
    assert exc.value.status_code == 401


def test_decode_raises_401_on_expired_token():
    """Assert decode_access_token raises HTTPException 401 on expired token."""
    token = create_access_token({"sub": "1"}, timedelta(seconds=-1))
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

def test_register_correct_code_returns_201(client):
    """Assert POST /api/auth/register returns 201 and a JWT on valid code."""
    r = client.post("/api/auth/register", json={
        "username": "newuser",
        "password": "pass123",
        "signup_code": "testcode",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_wrong_code_returns_400(client):
    """Assert POST /api/auth/register returns 400 on wrong signup code."""
    r = client.post("/api/auth/register", json={
        "username": "newuser",
        "password": "pass123",
        "signup_code": "wrongcode",
    })
    assert r.status_code == 400


def test_register_duplicate_username_returns_409(client, db, user):
    """Assert POST /api/auth/register returns 409 when username is taken."""
    r = client.post("/api/auth/register", json={
        "username": user.username,
        "password": "pass123",
        "signup_code": "testcode",
    })
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

def test_login_correct_credentials_returns_200(client, db, user):
    """Assert POST /api/auth/login returns 200 and a JWT on valid credentials."""
    r = client.post("/api/auth/login", json={
        "username": user.username,
        "password": "testpass",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client, db, user):
    """Assert POST /api/auth/login returns 401 on wrong password."""
    r = client.post("/api/auth/login", json={
        "username": user.username,
        "password": "wrongpassword",
    })
    assert r.status_code == 401


def test_login_unknown_username_returns_401(client):
    """Assert POST /api/auth/login returns 401 for a non-existent username."""
    r = client.post("/api/auth/login", json={
        "username": "ghost",
        "password": "pass",
    })
    assert r.status_code == 401


def test_login_missing_fields_returns_422(client):
    """Assert POST /api/auth/login returns 422 when fields are absent."""
    assert client.post("/api/auth/login", json={}).status_code == 422


# ---------------------------------------------------------------------------
# Route protection
# ---------------------------------------------------------------------------

@pytest.fixture()
def unauth_client(db):
    """TestClient with get_db overridden but no get_current_user override."""
    def _override_get_db():
        yield db
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_protected_route_without_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with no Authorization header."""
    assert unauth_client.get("/api/workouts").status_code == 401


def test_protected_route_with_invalid_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with a bad token."""
    assert unauth_client.get(
        "/api/workouts",
        headers={"Authorization": "Bearer badtoken"},
    ).status_code == 401


def test_protected_route_with_valid_token_returns_200(unauth_client, db):
    """Assert GET /api/workouts returns 200 with a valid Bearer token."""
    from conftest import make_user
    u = make_user(db)
    token = create_access_token(
        {
            "sub": str(u.id),
            "username": u.username,
            "is_admin": False,
            "is_premium": False,
        },
        timedelta(minutes=30),
    )
    r = unauth_client.get(
        "/api/workouts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_protected_route_with_expired_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with an expired token."""
    token = create_access_token({"sub": "1"}, timedelta(seconds=-1))
    assert unauth_client.get(
        "/api/workouts",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL — `check_signup_code` not found; register endpoint missing; login rejects username field

- [ ] **Step 3: Replace `app/services/auth_service.py`**

```python
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException
from jose import JWTError, jwt

_JWT_SECRET = os.environ.get("JWT_SECRET", "")
_SIGNUP_CODE = os.environ.get("SIGNUP_CODE", "")
_ALGORITHM = "HS256"

if not _JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of plain."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed, False otherwise."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def check_signup_code(code: str) -> bool:
    """Return True if code matches the SIGNUP_CODE env var."""
    return bool(_SIGNUP_CODE) and code == _SIGNUP_CODE


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """Return a signed JWT encoding data with expiry now + expires_delta."""
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate token; raise HTTPException 401 if invalid or expired."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

- [ ] **Step 4: Create `app/services/user_service.py`**

```python
from sqlalchemy.orm import Session

from app.model.models import User
from app.services.auth_service import hash_password


def create_user(db: Session, username: str, password: str) -> User:
    """Create and persist a new user with a bcrypt-hashed password."""
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return a User by username, or None if not found."""
    return db.query(User).filter(User.username == username).first()
```

- [ ] **Step 5: Update `app/api/schemas.py`**

Add `RegisterRequest` after `TokenResponse`:

```python
class RegisterRequest(BaseModel):
    """Request schema for the register endpoint."""

    username: str
    password: str
    signup_code: str
```

Replace `LoginRequest`:

```python
class LoginRequest(BaseModel):
    """Request schema for the login endpoint."""

    username: str
    password: str
```

Add `user_id` to `ExerciseDefSchema`:

```python
class ExerciseDefSchema(BaseModel):
    """Response schema for an exercise definition."""

    id: int
    name: str
    equipment: str | None = None
    instructions: str | None = None
    user_id: int | None = None
    muscle_groups: list[MuscleGroupSchema]
```

- [ ] **Step 6: Replace `app/api/auth_routes.py`**

```python
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.db.database import get_db
from app.services.auth_service import (
    check_signup_code,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.services.user_service import create_user, get_user_by_username

router = APIRouter()

_TOKEN_EXPIRE_HOURS = 720
_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return its decoded payload; raise 401 on failure."""
    return decode_access_token(credentials.credentials)


def _make_token(user) -> str:
    """Return a signed JWT for user encoding id, username, is_admin, is_premium."""
    return create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
        },
        timedelta(hours=_TOKEN_EXPIRE_HOURS),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Verify credentials and return a JWT on success; 401 on failure."""
    user = get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail="Incorrect username or password"
        )
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create account and return a JWT; 400 on bad code, 409 on duplicate username."""
    if not check_signup_code(body.signup_code):
        raise HTTPException(status_code=400, detail="Invalid signup code")
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = create_user(db, body.username, body.password)
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )
```

- [ ] **Step 7: Add `/register` route to `app/main.py`**

After the existing `/login` handler:

```python
@app.get("/register")
def register_page():
    """Serve the registration page."""
    return FileResponse("app/static/register.html", headers=NO_CACHE)
```

- [ ] **Step 8: Replace `tests/conftest.py`**

```python
import os

os.environ["TESTING"] = "1"
os.environ.setdefault("SIGNUP_CODE", "testcode")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth_routes import get_current_user
from app.db.database import Base, get_db
from app.main import app
from app.model.models import ExerciseDef, MuscleGroup

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(
    bind=test_engine, autocommit=False, autoflush=False
)


def make_user(
    db,
    username="testuser",
    password="testpass",
    is_admin=False,
    is_premium=True,
):
    """Insert a User into the test database and return it."""
    from app.services.user_service import create_user
    user = create_user(db, username, password)
    user.is_admin = is_admin
    user.is_premium = is_premium
    db.commit()
    db.refresh(user)
    return user


def make_muscle_group(db, name="pectorals"):
    """Insert a MuscleGroup into the test database and return it."""
    mg = MuscleGroup(name=name)
    db.add(mg)
    db.commit()
    db.refresh(mg)
    return mg


def make_exercise(
    db,
    name="Bench Press",
    equipment="barbell",
    instructions="Press the bar up",
    muscle_groups=None,
    user_id=None,
):
    """Insert an ExerciseDef (global by default) into the test database."""
    ex = ExerciseDef(
        name=name,
        equipment=equipment,
        instructions=instructions,
        muscle_groups=muscle_groups or [],
        user_id=user_id,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    """Provide a clean SQLAlchemy session bound to the in-memory test database."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    """Create and return a standard (non-admin, premium) test user."""
    return make_user(db)


@pytest.fixture()
def client(db, user):
    """Return a TestClient authenticated as the standard test user."""
    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client(db):
    """Return a TestClient authenticated as an admin user."""
    admin = make_user(db, username="admin", is_admin=True, is_premium=True)

    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(admin.id),
            "username": admin.username,
            "is_admin": True,
            "is_premium": True,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 9: Update `.env.example`**

Replace `ADMIN_PASSWORD=yourpasswordhere` with:

```
SIGNUP_CODE=yoursignupcodehere
```

- [ ] **Step 10: Run auth tests**

```bash
pytest tests/test_auth.py -v
```

Expected: all PASS

- [ ] **Step 11: Commit**

```bash
git add app/services/auth_service.py app/services/user_service.py \
        app/api/auth_routes.py app/api/schemas.py app/main.py \
        tests/conftest.py tests/test_auth.py .env.example
git commit -m "feat: user-based login, register endpoint, updated auth service"
```

---

### Task 3: Admin CLI

**Files:**
- Create: `app/admin.py`
- Create: `tests/test_admin.py`

**Interfaces:**
- Produces: `python -m app.admin promote <username> --admin` and/or `--premium`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin.py
from app.model.models import User


def test_is_admin_flag_persists(db):
    """Assert setting is_admin=True on a User persists after commit."""
    from conftest import make_user
    user = make_user(db, username="alice", is_admin=False)
    user.is_admin = True
    db.commit()
    db.refresh(user)
    assert user.is_admin is True


def test_is_premium_flag_persists(db):
    """Assert setting is_premium=True on a User persists after commit."""
    from conftest import make_user
    user = make_user(db, username="bob", is_premium=False)
    user.is_premium = True
    db.commit()
    db.refresh(user)
    assert user.is_premium is True
```

- [ ] **Step 2: Run tests (they pass immediately — tests the model)**

```bash
pytest tests/test_admin.py -v
```

Expected: PASS

- [ ] **Step 3: Create `app/admin.py`**

```python
import argparse
import sys

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.model.models import User


def _get_db() -> Session:
    """Return a new database session."""
    return SessionLocal()


def promote(username: str, make_admin: bool, make_premium: bool) -> None:
    """Set is_admin or is_premium on the named user account."""
    db = _get_db()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            sys.exit(1)
        if make_admin:
            user.is_admin = True
        if make_premium:
            user.is_premium = True
        db.commit()
        flags = []
        if make_admin:
            flags.append("admin")
        if make_premium:
            flags.append("premium")
        print(
            f"Promoted '{username}': {', '.join(flags) or 'no changes'}."
        )
    finally:
        db.close()


def main() -> None:
    """Run the GymLog admin CLI."""
    parser = argparse.ArgumentParser(description="GymLog admin CLI")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("promote", help="Grant admin or premium to a user")
    p.add_argument("username", help="Username to promote")
    p.add_argument("--admin", action="store_true", help="Grant admin role")
    p.add_argument(
        "--premium", action="store_true", help="Grant premium role"
    )
    args = parser.parse_args()
    if args.command == "promote":
        promote(args.username, args.admin, args.premium)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add app/admin.py tests/test_admin.py
git commit -m "feat: add admin CLI for promoting users to admin or premium"
```

---

### Task 4: Workout Service User Scoping

**Files:**
- Modify: `app/services/workout_service.py`
- Modify: `app/api/workout_routes.py`
- Modify: `tests/test_workouts.py`

**Interfaces:**
- Consumes: `user_id: int` (from `int(current_user["sub"])` in route handlers)
- Produces: all workout service functions accept and filter by `user_id`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workouts.py`:

```python
def test_workouts_scoped_to_user(db):
    """Assert a user only sees their own workouts, not another user's."""
    from conftest import make_user, make_exercise
    from app.api.auth_routes import get_current_user
    from app.db.database import get_db
    from fastapi.testclient import TestClient
    from app.main import app

    user_a = make_user(db, username="alice")
    user_b = make_user(db, username="bob")
    ex = make_exercise(db, name="Curl")

    def db_override():
        """Yield the shared test db session."""
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_a.id), "username": "alice",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as ca:
        ca.post("/api/workouts", json={
            "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5}]}]
        })
        assert len(ca.get("/api/workouts").json()) == 1

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_b.id), "username": "bob",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as cb:
        assert len(cb.get("/api/workouts").json()) == 0

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_workouts.py::test_workouts_scoped_to_user -v
```

Expected: FAIL

- [ ] **Step 3: Replace `app/services/workout_service.py`**

```python
from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.api.schemas import WorkoutRequest
from app.model.models import Exercise, ExerciseDef, Workout


def build_workout_detailed(db: Session, session: Workout) -> dict:
    """Build the detailed workout dict used by WorkoutDetailed."""
    sets = (
        db.query(Exercise)
        .options(
            joinedload(Exercise.exercise_def).joinedload(
                ExerciseDef.muscle_groups
            )
        )
        .filter(Exercise.session_id == session.id)
        .order_by(Exercise.set_number)
        .all()
    )

    grouped: dict[int, list] = defaultdict(list)
    for ex_set in sets:
        grouped[ex_set.exercise_id].append(ex_set)

    exercises = [
        {
            "exercise_id": exercise_id,
            "name": set_list[0].exercise_def.name,
            "muscle_groups": [
                {"id": mg.id, "name": mg.name}
                for mg in set_list[0].exercise_def.muscle_groups
            ],
            "sets": [
                {"reps": s.reps, "weight_lbs": s.weight_lbs}
                for s in set_list
            ],
        }
        for exercise_id, set_list in grouped.items()
    ]

    return {
        "session_id": session.id,
        "logged_at": session.logged_at,
        "notes": session.raw_input,
        "exercises": exercises,
    }


def log_workout(
    db: Session, workout: WorkoutRequest, user_id: int
) -> Workout:
    """Persist a new workout session for user_id with all its sets."""
    session = (
        Workout(
            raw_input=workout.notes,
            logged_at=workout.logged_at,
            user_id=user_id,
        )
        if workout.logged_at
        else Workout(raw_input=workout.notes, user_id=user_id)
    )
    db.add(session)
    db.flush()

    for exercise in workout.exercises:
        for j, s in enumerate(exercise.sets):
            db.add(Exercise(
                session_id=session.id,
                exercise_id=exercise.exercise_id,
                set_number=j + 1,
                reps=s.reps,
                weight_lbs=s.weight_lbs,
            ))

    db.commit()
    db.refresh(session)
    return session


def get_workout(
    db: Session, session_id: int, user_id: int
) -> Workout | None:
    """Return a workout session owned by user_id, or None if not found."""
    return (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )


def get_all_workouts(db: Session, user_id: int) -> list[Workout]:
    """Return all workout sessions for user_id ordered by date descending."""
    return (
        db.query(Workout)
        .filter(Workout.user_id == user_id)
        .order_by(Workout.logged_at.desc())
        .all()
    )


def update_workout(
    db: Session,
    session_id: int,
    workout: WorkoutRequest,
    user_id: int,
) -> Workout | None:
    """Replace all sets in a workout owned by user_id; returns None if not found."""
    session = (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )
    if not session:
        return None

    session.raw_input = workout.notes
    db.query(Exercise).filter(Exercise.session_id == session_id).delete()

    for exercise in workout.exercises:
        for j, s in enumerate(exercise.sets):
            db.add(Exercise(
                session_id=session.id,
                exercise_id=exercise.exercise_id,
                set_number=j + 1,
                reps=s.reps,
                weight_lbs=s.weight_lbs,
            ))

    db.commit()
    db.refresh(session)
    return session


def delete_workout(
    db: Session, session_id: int, user_id: int
) -> bool:
    """Delete a workout owned by user_id; returns False if not found."""
    session = (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True
```

- [ ] **Step 4: Replace `app/api/workout_routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user
from app.api.schemas import WorkoutDetailed, WorkoutRequest, WorkoutResponse
from app.db.database import get_db
from app.services.workout_service import (
    build_workout_detailed,
    delete_workout,
    get_all_workouts,
    get_workout,
    log_workout,
    update_workout,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/workouts", response_model=WorkoutResponse)
def create_workout(
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Log a new workout session and return a summary."""
    user_id = int(current_user["sub"])
    session = log_workout(db, workout, user_id)
    return WorkoutResponse(
        session_id=session.id,
        logged_at=session.logged_at,
        exercises_logged=len(workout.exercises),
        sets_logged=sum(len(e.sets) for e in workout.exercises),
    )


@router.get("/workouts", response_model=list[WorkoutResponse])
def list_workouts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return all workout sessions for the current user, newest first."""
    user_id = int(current_user["sub"])
    sessions = get_all_workouts(db, user_id)
    return [
        WorkoutResponse(
            session_id=s.id,
            logged_at=s.logged_at,
            exercises_logged=len({ex.exercise_id for ex in s.sets}),
            sets_logged=len(s.sets),
        )
        for s in sessions
    ]


@router.get("/workout/{session_id}", response_model=WorkoutDetailed)
def fetch_workout(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return full detail for a single workout; 404 if not found or not owned."""
    session = get_workout(db, session_id, int(current_user["sub"]))
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(
    session_id: int,
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Replace all exercises in a workout; 404 if not found or not owned."""
    session = update_workout(
        db, session_id, workout, int(current_user["sub"])
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.delete("/workout/{session_id}")
def remove_workout(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a workout and all its sets; 404 if not found or not owned."""
    if not delete_workout(db, session_id, int(current_user["sub"])):
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"deleted": session_id}
```

- [ ] **Step 5: Run all workout tests**

```bash
pytest tests/test_workouts.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/workout_service.py app/api/workout_routes.py \
        tests/test_workouts.py
git commit -m "feat: scope workout queries to user_id"
```

---

### Task 5: Routine Service User Scoping

**Files:**
- Modify: `app/services/routine_service.py`
- Modify: `app/api/routine_routes.py`
- Modify: `tests/test_routines.py`

**Interfaces:**
- Consumes: `user_id: int` from JWT
- Produces: all routine service functions accept `user_id`; name conflict scoped per user

- [ ] **Step 1: Write the failing test**

Add to `tests/test_routines.py`:

```python
def test_routines_scoped_to_user(db):
    """Assert a user only sees their own routines, not another user's."""
    from conftest import make_user, make_exercise
    from app.api.auth_routes import get_current_user
    from app.db.database import get_db
    from fastapi.testclient import TestClient
    from app.main import app

    user_a = make_user(db, username="alice2")
    user_b = make_user(db, username="bob2")
    ex = make_exercise(db, name="Curl2")

    def db_override():
        """Yield the shared test db session."""
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_a.id), "username": "alice2",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as ca:
        ca.post("/api/routines", json={
            "name": "Alice Routine",
            "exercises": [
                {"exercise_id": ex.id, "position": 1, "num_sets": 3}
            ],
        })
        assert len(ca.get("/api/routines").json()) == 1

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_b.id), "username": "bob2",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as cb:
        assert len(cb.get("/api/routines").json()) == 0

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_routines.py::test_routines_scoped_to_user -v
```

Expected: FAIL

- [ ] **Step 3: Replace `app/services/routine_service.py`**

```python
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import RoutineCreate, RoutineUpdate
from app.model.models import Routine, RoutineExercise


def create_routine(
    db: Session, data: RoutineCreate, user_id: int
) -> Routine:
    """Create a new routine for user_id.

    Raises ValueError('name_conflict') if a routine with that name
    already belongs to the same user.
    """
    if db.query(Routine).filter(
        Routine.name == data.name, Routine.user_id == user_id
    ).first():
        raise ValueError("name_conflict")
    routine = Routine(name=data.name, user_id=user_id)
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


def get_all_routines(db: Session, user_id: int) -> list[Routine]:
    """Return all routines for user_id with exercises eager-loaded, by name."""
    return (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .filter(Routine.user_id == user_id)
        .order_by(Routine.name)
        .all()
    )


def get_routine(
    db: Session, routine_id: int, user_id: int
) -> Routine | None:
    """Return a routine owned by user_id with exercise definitions loaded, or None."""
    return (
        db.query(Routine)
        .options(
            joinedload(Routine.exercises).joinedload(
                RoutineExercise.exercise_def
            )
        )
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )


def update_routine(
    db: Session, routine_id: int, data: RoutineUpdate, user_id: int
) -> Routine | None:
    """Replace a routine's name and exercises for user_id; returns None if not found.

    Raises ValueError('name_conflict') if the new name is taken by another
    routine belonging to the same user.
    """
    routine = (
        db.query(Routine)
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )
    if not routine:
        return None
    conflict = db.query(Routine).filter(
        Routine.name == data.name,
        Routine.id != routine_id,
        Routine.user_id == user_id,
    ).first()
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


def delete_routine(
    db: Session, routine_id: int, user_id: int
) -> bool:
    """Delete a routine owned by user_id; returns False if not found."""
    routine = (
        db.query(Routine)
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )
    if not routine:
        return False
    db.delete(routine)
    db.commit()
    return True
```

- [ ] **Step 4: Replace `app/api/routine_routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user
from app.api.schemas import (
    RoutineCreate, RoutineDetail, RoutineExerciseDetail,
    RoutineListItem, RoutineUpdate,
)
from app.db.database import get_db
from app.model.models import ExerciseDef, Routine
from app.services.routine_service import (
    create_routine, delete_routine, get_all_routines,
    get_routine, update_routine,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _validate_exercise_ids(db: Session, exercises: list) -> list[int]:
    """Return exercise_ids from the request that do not exist in the DB."""
    requested = {ex.exercise_id for ex in exercises}
    found = {
        row.id
        for row in db.query(ExerciseDef)
        .filter(ExerciseDef.id.in_(requested))
        .all()
    }
    return [eid for eid in requested if eid not in found]


def _to_detail(routine: Routine) -> RoutineDetail:
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
def add_routine(
    data: RoutineCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new routine for the current user; 409 if name is already taken."""
    user_id = int(current_user["sub"])
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid exercise ids: {invalid}"
        )
    try:
        routine = create_routine(db, data, user_id)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    return _to_detail(get_routine(db, routine.id, user_id))


@router.get("/routines", response_model=list[RoutineListItem])
def list_routines(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return all routines for the current user ordered by name."""
    user_id = int(current_user["sub"])
    routines = get_all_routines(db, user_id)
    return [
        RoutineListItem(
            id=r.id, name=r.name, exercise_count=len(r.exercises)
        )
        for r in routines
    ]


@router.get("/routine/{routine_id}", response_model=RoutineDetail)
def fetch_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return full detail for a routine; 404 if not found or not owned."""
    routine = get_routine(db, routine_id, int(current_user["sub"]))
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(routine)


@router.put("/routine/{routine_id}", response_model=RoutineDetail)
def replace_routine(
    routine_id: int,
    data: RoutineUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Replace a routine's name and exercises; 404 if not owned, 409 on conflict."""
    user_id = int(current_user["sub"])
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid exercise ids: {invalid}"
        )
    try:
        routine = update_routine(db, routine_id, data, user_id)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(get_routine(db, routine.id, user_id))


@router.delete("/routine/{routine_id}")
def remove_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a routine owned by the current user; 404 if not found."""
    if not delete_routine(db, routine_id, int(current_user["sub"])):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"deleted": routine_id}
```

- [ ] **Step 5: Run all routine tests**

```bash
pytest tests/test_routines.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/routine_service.py app/api/routine_routes.py \
        tests/test_routines.py
git commit -m "feat: scope routine queries to user_id"
```

---

### Task 6: Exercise Service Permissions

**Files:**
- Modify: `app/services/exercise_service.py`
- Modify: `app/api/exercise_routes.py`
- Modify: `tests/test_exercises.py`

**Interfaces:**
- Consumes: `user_id: int`, `is_admin: bool` from JWT
- Produces: `get_all_exercises(db, user_id)` returns global + caller's custom; `create_exercise(db, data, user_id)` sets user_id; `update_exercise` and `delete_exercise` raise `ValueError("forbidden")` when not permitted; `get_exercise_progression(db, exercise_id, user_id)` filters sessions by user

- [ ] **Step 1: Write the failing permission tests**

Add to `tests/test_exercises.py`:

```python
def test_non_admin_cannot_edit_global_exercise(client, db):
    """Assert PUT /api/exercise/{id} returns 403 for a global exercise as non-admin."""
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "New Name"})
    assert r.status_code == 403


def test_non_admin_cannot_delete_global_exercise(client, db):
    """Assert DELETE /api/exercise/{id} returns 403 for a global exercise as non-admin."""
    ex = make_exercise(db)
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 403


def test_user_can_edit_own_custom_exercise(client, db):
    """Assert PUT /api/exercise/{id} succeeds for the user's own custom exercise."""
    r = client.post("/api/exercises", json={
        "name": "My Custom Press", "muscle_group_ids": []
    })
    exercise_id = r.json()["id"]
    r2 = client.put(
        f"/api/exercise/{exercise_id}", json={"name": "My Updated Press"}
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "My Updated Press"


def test_user_can_delete_own_custom_exercise(client, db):
    """Assert DELETE /api/exercise/{id} returns 204 for the user's own custom exercise."""
    r = client.post(
        "/api/exercises", json={"name": "To Delete", "muscle_group_ids": []}
    )
    exercise_id = r.json()["id"]
    assert client.delete(f"/api/exercise/{exercise_id}").status_code == 204


def test_user_cannot_edit_other_users_custom_exercise(client, db, user):
    """Assert PUT /api/exercise/{id} returns 403 for another user's custom exercise."""
    from app.model.models import ExerciseDef
    other_ex = ExerciseDef(name="Other Custom", user_id=user.id + 999)
    db.add(other_ex)
    db.commit()
    db.refresh(other_ex)
    r = client.put(f"/api/exercise/{other_ex.id}", json={"name": "Hijacked"})
    assert r.status_code == 403


def test_admin_can_edit_global_exercise(admin_client, db):
    """Assert PUT /api/exercise/{id} returns 200 when admin edits a global exercise."""
    ex = make_exercise(db)
    r = admin_client.put(f"/api/exercise/{ex.id}", json={"name": "Admin Renamed"})
    assert r.status_code == 200


def test_admin_can_delete_global_exercise(admin_client, db):
    """Assert DELETE /api/exercise/{id} returns 204 when admin deletes a global exercise."""
    ex = make_exercise(db)
    assert admin_client.delete(f"/api/exercise/{ex.id}").status_code == 204


def test_list_exercises_includes_own_custom(client, db):
    """Assert GET /api/exercises returns global + caller's custom exercises."""
    make_exercise(db, name="Global Squat")
    client.post("/api/exercises", json={
        "name": "My Curl", "muscle_group_ids": []
    })
    names = [e["name"] for e in client.get("/api/exercises").json()]
    assert "Global Squat" in names
    assert "My Curl" in names


def test_list_exercises_excludes_other_users_custom(client, db, user):
    """Assert GET /api/exercises does not include another user's custom exercise."""
    from app.model.models import ExerciseDef
    other_ex = ExerciseDef(name="Other User Curl", user_id=user.id + 999)
    db.add(other_ex)
    db.commit()
    names = [e["name"] for e in client.get("/api/exercises").json()]
    assert "Other User Curl" not in names
```

Also update these existing tests to use `admin_client` (they edit/delete global exercises):

```python
# Change signature from (client, db) to (admin_client, db) for:
# test_update_exercise_name
# test_update_exercise_muscle_groups
# test_update_exercise_multiple_fields
# test_update_exercise_not_found  → change to (admin_client,)
# test_update_exercise_name_conflict
# test_update_exercise_same_name_no_conflict
# test_update_exercise_invalid_muscle_group_id
# test_delete_exercise
# test_delete_exercise_not_found → change to (admin_client,)
# test_delete_exercise_with_history → use admin_client for both workout and delete
```

For `test_delete_exercise_with_history`, update to use `admin_client` throughout:

```python
def test_delete_exercise_with_history(admin_client, db):
    """Assert DELETE returns 409 and leaves exercise intact when it has logged history."""
    ex = make_exercise(db)
    admin_client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}
        ]
    })
    r = admin_client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 409
    assert admin_client.get(f"/api/exercise/{ex.id}/info").status_code == 200
```

- [ ] **Step 2: Run to confirm new tests fail**

```bash
pytest tests/test_exercises.py::test_non_admin_cannot_edit_global_exercise \
       tests/test_exercises.py::test_user_can_edit_own_custom_exercise -v
```

Expected: FAIL

- [ ] **Step 3: Replace `app/services/exercise_service.py`**

```python
from collections import defaultdict

from sqlalchemy.orm import Session

from app.api.schemas import CreateExerciseSchema, ExerciseUpdate
from app.model.models import Exercise, ExerciseDef, MuscleGroup, Workout


def get_all_exercises(db: Session, user_id: int) -> list[ExerciseDef]:
    """Return global exercises plus caller's custom exercises, alphabetically."""
    return (
        db.query(ExerciseDef)
        .filter(
            (ExerciseDef.user_id.is_(None)) |
            (ExerciseDef.user_id == user_id)
        )
        .order_by(ExerciseDef.name)
        .all()
    )


def get_exercise(db: Session, exercise_id: int) -> ExerciseDef | None:
    """Return a single exercise by ID, or None if not found."""
    return (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )


def get_all_muscle_groups(db: Session) -> list[MuscleGroup]:
    """Return all muscle groups ordered alphabetically by name."""
    return db.query(MuscleGroup).order_by(MuscleGroup.name).all()


def create_exercise(
    db: Session, data: CreateExerciseSchema, user_id: int
) -> ExerciseDef:
    """Create and persist a new custom exercise owned by user_id."""
    muscle_groups = (
        db.query(MuscleGroup)
        .filter(MuscleGroup.id.in_(data.muscle_group_ids))
        .all()
    )
    exercise = ExerciseDef(
        name=data.name,
        equipment=data.equipment,
        instructions=data.instructions,
        muscle_groups=muscle_groups,
        user_id=user_id,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def update_exercise(
    db: Session,
    exercise_id: int,
    data: ExerciseUpdate,
    user_id: int,
    is_admin: bool = False,
) -> ExerciseDef | None:
    """Partially update an exercise; returns None if not found.

    Raises ValueError('forbidden') if the caller lacks permission.
    Raises ValueError('name_conflict') if the new name is taken in the same scope.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return None

    if exercise.user_id is None and not is_admin:
        raise ValueError("forbidden")
    if (
        exercise.user_id is not None
        and exercise.user_id != user_id
        and not is_admin
    ):
        raise ValueError("forbidden")

    if data.name is not None and data.name != exercise.name:
        conflict = db.query(ExerciseDef).filter(
            ExerciseDef.name == data.name,
            ExerciseDef.id != exercise_id,
            ExerciseDef.user_id == exercise.user_id,
        ).first()
        if conflict:
            raise ValueError("name_conflict")
        exercise.name = data.name

    if data.equipment is not None:
        exercise.equipment = data.equipment
    if data.instructions is not None:
        exercise.instructions = data.instructions
    if data.muscle_group_ids is not None:
        exercise.muscle_groups = (
            db.query(MuscleGroup)
            .filter(MuscleGroup.id.in_(data.muscle_group_ids))
            .all()
        )

    db.commit()
    db.refresh(exercise)
    return exercise


def delete_exercise(
    db: Session,
    exercise_id: int,
    user_id: int,
    is_admin: bool = False,
) -> bool:
    """Delete an exercise; returns False if not found.

    Raises ValueError('forbidden') if the caller lacks permission.
    Raises ValueError('has_history') if the exercise has logged sets.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return False

    if exercise.user_id is None and not is_admin:
        raise ValueError("forbidden")
    if (
        exercise.user_id is not None
        and exercise.user_id != user_id
        and not is_admin
    ):
        raise ValueError("forbidden")

    if db.query(Exercise).filter(
        Exercise.exercise_id == exercise_id
    ).first():
        raise ValueError("has_history")

    db.delete(exercise)
    db.commit()
    return True


def get_exercise_progression(
    db: Session, exercise_id: int, user_id: int
):
    """Return (exercise, sessions) for caller's progression with this exercise.

    sessions is a list of dicts sorted chronologically, each with
    session_id, logged_at, sets, volume, and best_set_weight.
    Returns (None, []) if the exercise does not exist.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return None, []

    rows = (
        db.query(Exercise, Workout.logged_at)
        .join(Workout, Exercise.session_id == Workout.id)
        .filter(
            Exercise.exercise_id == exercise.id,
            Workout.user_id == user_id,
        )
        .order_by(Workout.logged_at.asc(), Exercise.set_number.asc())
        .all()
    )

    session_map: dict = defaultdict(lambda: {"logged_at": None, "sets": []})
    for ex_set, logged_at in rows:
        sid = ex_set.session_id
        session_map[sid]["logged_at"] = logged_at
        session_map[sid]["sets"].append(ex_set)

    sessions = []
    for sid, data in sorted(
        session_map.items(), key=lambda x: x[1]["logged_at"]
    ):
        s_sets = data["sets"]
        weights = [s.weight_lbs for s in s_sets if s.weight_lbs is not None]
        volume = (
            round(
                sum(
                    s.reps * s.weight_lbs
                    for s in s_sets
                    if s.weight_lbs is not None
                ),
                1,
            )
            if weights
            else None
        )
        sessions.append({
            "session_id": sid,
            "logged_at": data["logged_at"],
            "sets": [
                {
                    "set_number": s.set_number,
                    "reps": s.reps,
                    "weight_lbs": s.weight_lbs,
                }
                for s in s_sets
            ],
            "volume": volume,
            "best_set_weight": max(weights) if weights else None,
        })

    return exercise, sessions
```

- [ ] **Step 4: Replace `app/api/exercise_routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user
from app.api.schemas import (
    CreateExerciseSchema, ExerciseDefSchema, ExerciseProgressionSchema,
    ExerciseUpdate, MuscleGroupSchema, SessionSummary, SetDetail,
)
from app.db.database import get_db
from app.services.exercise_service import (
    create_exercise, delete_exercise, get_all_exercises,
    get_all_muscle_groups, get_exercise, get_exercise_progression,
    update_exercise,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/muscle-groups", response_model=list[MuscleGroupSchema])
def list_muscle_groups(db: Session = Depends(get_db)):
    """Return all muscle groups in alphabetical order."""
    return get_all_muscle_groups(db)


@router.get("/exercises", response_model=list[ExerciseDefSchema])
def list_exercises(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return global exercises plus the caller's custom exercises."""
    return get_all_exercises(db, int(current_user["sub"]))


@router.post("/exercises", response_model=ExerciseDefSchema, status_code=201)
def add_exercise(
    data: CreateExerciseSchema,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a custom exercise owned by the caller; 400 on invalid muscle group."""
    valid_ids = {mg.id for mg in get_all_muscle_groups(db)}
    invalid = [i for i in data.muscle_group_ids if i not in valid_ids]
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid muscle group ids: {invalid}"
        )
    return create_exercise(db, data, int(current_user["sub"]))


@router.get("/exercise/{exercise_id}/info", response_model=ExerciseDefSchema)
def get_exercise_info(exercise_id: int, db: Session = Depends(get_db)):
    """Return a single exercise by ID; 404 if not found."""
    exercise = get_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.put("/exercise/{exercise_id}", response_model=ExerciseDefSchema)
def edit_exercise(
    exercise_id: int,
    data: ExerciseUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Partially update an exercise; 403 if not permitted, 404 not found, 409 name conflict."""
    if data.muscle_group_ids is not None:
        valid_ids = {mg.id for mg in get_all_muscle_groups(db)}
        invalid = [i for i in data.muscle_group_ids if i not in valid_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid muscle group ids: {invalid}",
            )
    try:
        exercise = update_exercise(
            db,
            exercise_id,
            data,
            user_id=int(current_user["sub"]),
            is_admin=current_user.get("is_admin", False),
        )
    except ValueError as e:
        if str(e) == "forbidden":
            raise HTTPException(status_code=403, detail="Not permitted")
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="An exercise with that name already exists",
            )
        raise
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.delete("/exercise/{exercise_id}", status_code=204)
def remove_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete an exercise; 403 not permitted, 404 not found, 409 has history."""
    try:
        found = delete_exercise(
            db,
            exercise_id,
            user_id=int(current_user["sub"]),
            is_admin=current_user.get("is_admin", False),
        )
    except ValueError as e:
        if str(e) == "forbidden":
            raise HTTPException(status_code=403, detail="Not permitted")
        if str(e) == "has_history":
            raise HTTPException(
                status_code=409,
                detail="Exercise has logged history and cannot be deleted",
            )
        raise
    if not found:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return Response(status_code=204)


@router.get(
    "/exercise/{exercise_id}/progression",
    response_model=ExerciseProgressionSchema,
)
def get_progression(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return progression for caller's sessions with this exercise; 404 if not found."""
    exercise, sessions = get_exercise_progression(
        db, exercise_id, int(current_user["sub"])
    )
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ExerciseProgressionSchema(
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        sessions=[
            SessionSummary(
                session_id=s["session_id"],
                logged_at=s["logged_at"],
                sets=[SetDetail(**d) for d in s["sets"]],
                volume=s["volume"],
                best_set_weight=s["best_set_weight"],
            )
            for s in sessions
        ],
    )
```

- [ ] **Step 5: Run all exercise tests**

```bash
pytest tests/test_exercises.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/exercise_service.py app/api/exercise_routes.py \
        tests/test_exercises.py
git commit -m "feat: exercise ownership checks and user-scoped exercise reads"
```

---

### Task 7: Chat Premium Gate + User Scoping

**Files:**
- Modify: `app/api/chat_routes.py`
- Modify: `app/services/chat_service.py`
- Modify: `app/services/chat_tools.py`
- Create: `tests/test_chat.py`

**Interfaces:**
- Consumes: `current_user["is_premium"]`, `current_user["is_admin"]`, `current_user["sub"]`
- Produces: `run_chat(db, messages, user_id)`; `execute_tool(name, inputs, db, user_id)`; 403 for non-premium non-admin on `POST /api/chat`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chat.py
import pytest
from fastapi.testclient import TestClient

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app


@pytest.fixture()
def non_premium_client(db, user):
    """TestClient for a non-premium, non-admin user."""
    user.is_premium = False
    db.commit()

    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": False,
            "is_premium": False,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_returns_403_for_non_premium(non_premium_client):
    """Assert POST /api/chat returns 403 for a non-premium, non-admin user."""
    r = non_premium_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code == 403


def test_chat_not_403_for_premium(client):
    """Assert POST /api/chat is reachable for a premium user (client fixture is premium)."""
    r = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code != 403


def test_chat_not_403_for_admin(admin_client):
    """Assert POST /api/chat is reachable for an admin even without premium."""
    r = admin_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code != 403
```

- [ ] **Step 2: Run to confirm first test fails**

```bash
pytest tests/test_chat.py::test_chat_returns_403_for_non_premium -v
```

Expected: FAIL — no 403 returned yet

- [ ] **Step 3: Replace `app/api/chat_routes.py`**

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.services.chat_service import run_chat

router = APIRouter(dependencies=[Depends(get_current_user)])


class ChatMessage(BaseModel):
    """One turn in the conversation history sent from the client."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    messages: list[ChatMessage]


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Stream an AI response over SSE; 403 if caller is not premium or admin."""
    if not current_user.get("is_premium") and not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Premium subscription required"
        )
    user_id = int(current_user["sub"])
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def generate():
        """Yield SSE-formatted chunks from the agentic tool loop."""
        try:
            for chunk in run_chat(db, messages, user_id):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Update `app/services/chat_service.py`**

Change `run_chat` to accept and forward `user_id`. Only the signature and `execute_tool` call change; all other logic is unchanged:

```python
def run_chat(
    db: Session, messages: list[dict[str, str]], user_id: int
) -> Generator[str, None, None]:
    """Run the agentic tool loop for user_id; yield text chunks for SSE streaming."""
    # ... (existing context-building code unchanged) ...

    for _ in range(_MAX_TOOL_ROUNDS):
        # ... (existing retry/generate loop unchanged) ...

        result_parts = []
        for fc in func_calls:
            result = json.loads(
                execute_tool(fc.name, dict(fc.args), db, user_id)
            )
            result_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response=result,
                )
            )
        # ... rest unchanged ...
```

- [ ] **Step 5: Update `app/services/chat_tools.py`**

Change `execute_tool` signature and scope the three data tools:

```python
def execute_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a tool call by name for user_id; return the result as JSON."""
```

In the `get_recent_workouts` branch, replace `get_all_workouts(db)` with `get_all_workouts(db, user_id)`.

In the `get_routines` branch, add `Routine.user_id == user_id` to the filter:

```python
    if name == "get_routines":
        routines = (
            db.query(Routine)
            .options(
                joinedload(Routine.exercises).joinedload(
                    RoutineExercise.exercise_def
                )
            )
            .filter(Routine.user_id == user_id)
            .order_by(Routine.name)
            .all()
        )
        # ... result-building unchanged ...
```

In the `log_workout` branch, pass `user_id` to `_log_workout`:

```python
        session = _log_workout(db, req, user_id)
```

- [ ] **Step 6: Run chat tests**

```bash
pytest tests/test_chat.py -v
```

Expected: `test_chat_returns_403_for_non_premium` PASS; the other two may be 500 (no live API key) — acceptable

- [ ] **Step 7: Commit**

```bash
git add app/api/chat_routes.py app/services/chat_service.py \
        app/services/chat_tools.py tests/test_chat.py
git commit -m "feat: gate chat on premium flag and scope chat tools to user"
```

---

### Task 8: Frontend

**Files:**
- Create: `app/static/register.html`
- Modify: `app/static/login.html`
- Modify: `app/static/auth.js`
- Modify: `app/static/dashboard.html`
- Modify: `app/static/exercises.html`
- Modify: `app/static/index.html`, `workouts.html`, `workout.html`, `exercise.html`, `routines.html`

**Interfaces:**
- Consumes: JWT in `localStorage['access_token']`
- Produces: `window.getUsername()`, `window.isAdmin()`, `window.isPremium()`, `window.getCurrentUserId()`

- [ ] **Step 1: Update `app/static/auth.js`**

Add five new helpers inside the IIFE, after the existing `logout` function, and export them on `window`:

```javascript
  function getTokenPayload() {
    var token = getToken();
    if (!token) return null;
    try {
      return JSON.parse(atob(token.split('.')[1]));
    } catch (e) {
      return null;
    }
  }

  function getUsername() {
    var p = getTokenPayload();
    return p ? p.username : '';
  }

  function isAdmin() {
    var p = getTokenPayload();
    return p ? Boolean(p.is_admin) : false;
  }

  function isPremium() {
    var p = getTokenPayload();
    return p ? Boolean(p.is_premium) : false;
  }

  function getCurrentUserId() {
    var p = getTokenPayload();
    return p ? parseInt(p.sub, 10) : null;
  }

  window.getTokenPayload = getTokenPayload;
  window.getUsername = getUsername;
  window.isAdmin = isAdmin;
  window.isPremium = isPremium;
  window.getCurrentUserId = getCurrentUserId;
```

- [ ] **Step 2: Update `app/static/login.html`**

Add CSS for `input[type="text"]` identical to the existing `input[type="password"]` rule.

Replace the password-only form with:

```html
<label for="username">Username</label>
<input type="text" id="username" placeholder="Enter username" autofocus />
<label for="password">Password</label>
<input type="password" id="password" placeholder="Enter password" />
<button id="btn">Sign in</button>
<div class="error" id="error"></div>
<div class="register-link">
  No account? <a href="/register">Register →</a>
</div>
```

Add CSS for `.register-link`:

```css
.register-link {
  margin-top: 16px;
  text-align: center;
  font-size: 0.85rem;
  color: #555;
}
.register-link a { color: #888; }
```

Update the JS `login()` function to read both fields and send `{ username, password }`:

```javascript
async function login() {
  var username = document.getElementById('username').value.trim();
  var password = document.getElementById('password').value.trim();
  if (!username || !password) return;
  btn.disabled = true;
  errorEl.textContent = '';
  try {
    var res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password }),
    });
    if (res.ok) {
      var data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.replace('/');
    } else {
      errorEl.textContent = 'Incorrect username or password.';
      document.getElementById('password').select();
    }
  } catch (e) {
    errorEl.textContent = 'Something went wrong. Try again.';
  } finally {
    btn.disabled = false;
  }
}
```

- [ ] **Step 3: Create `app/static/register.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GymLog — Register</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0f; color: #f0f0f0;
      font-family: system-ui, sans-serif;
      min-height: 100vh; display: flex;
      align-items: center; justify-content: center;
      padding: 24px 16px;
    }
    .card { width: 100%; max-width: 360px; }
    .logo {
      font-size: 1.1rem; font-weight: 700;
      letter-spacing: 0.05em; margin-bottom: 32px; text-align: center;
    }
    label {
      display: block; font-size: 0.78rem; color: #555;
      text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;
    }
    input {
      width: 100%; background: #1a1a1a; border: 1px solid #2a2a2a;
      border-radius: 8px; color: #f0f0f0; font-size: 1rem;
      padding: 12px 14px; outline: none; margin-bottom: 16px;
    }
    input:focus { border-color: #444; }
    button {
      width: 100%; background: #f0f0f0; color: #0f0f0f;
      border: none; border-radius: 8px; font-size: 1rem;
      font-weight: 600; padding: 14px; cursor: pointer;
    }
    button:hover { background: #ccc; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .error {
      color: #e05555; font-size: 0.85rem;
      margin-top: 12px; text-align: center; min-height: 20px;
    }
    .login-link {
      margin-top: 16px; text-align: center;
      font-size: 0.85rem; color: #555;
    }
    .login-link a { color: #888; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">GymLog</div>
    <label for="username">Username</label>
    <input type="text" id="username" placeholder="Choose a username" autofocus />
    <label for="password">Password</label>
    <input type="password" id="password" placeholder="Choose a password" />
    <label for="code">Signup Code</label>
    <input type="text" id="code" placeholder="Enter signup code" />
    <button id="btn">Create account</button>
    <div class="error" id="error"></div>
    <div class="login-link">Already have an account? <a href="/login">Sign in →</a></div>
  </div>

  <script>
    if (localStorage.getItem('access_token')) {
      window.location.replace('/');
    }

    var btn = document.getElementById('btn');
    var errorEl = document.getElementById('error');

    async function register() {
      var username = document.getElementById('username').value.trim();
      var password = document.getElementById('password').value.trim();
      var signup_code = document.getElementById('code').value.trim();
      if (!username || !password || !signup_code) return;
      btn.disabled = true;
      errorEl.textContent = '';
      try {
        var res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: username,
            password: password,
            signup_code: signup_code,
          }),
        });
        if (res.ok) {
          var data = await res.json();
          localStorage.setItem('access_token', data.access_token);
          window.location.replace('/');
        } else if (res.status === 400) {
          errorEl.textContent = 'Invalid signup code.';
        } else if (res.status === 409) {
          errorEl.textContent = 'Username already taken.';
        } else {
          errorEl.textContent = 'Something went wrong. Try again.';
        }
      } catch (e) {
        errorEl.textContent = 'Something went wrong. Try again.';
      } finally {
        btn.disabled = false;
      }
    }

    btn.addEventListener('click', register);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') register();
    });
  </script>
</body>
</html>
```

- [ ] **Step 4: Add username display to nav in all pages**

For every page that has a nav header, add a `<span id="nav-username">` next to the existing nav links.

CSS to add to each page (or a shared style):

```css
.nav-user {
  font-size: 0.78rem;
  color: #555;
  padding: 7px 4px;
}
.nav-user[data-admin]::after {
  content: ' · admin';
  color: #888;
}
```

HTML addition in each nav:

```html
<span id="nav-username" class="nav-user"></span>
```

JS to add after `checkAuth()` in each page's script:

```javascript
var navUser = document.getElementById('nav-username');
if (navUser) {
  navUser.textContent = getUsername();
  if (isAdmin()) navUser.setAttribute('data-admin', '');
}
```

Apply to: `dashboard.html`, `index.html`, `workouts.html`, `workout.html`, `exercises.html`, `exercise.html`, `routines.html`

- [ ] **Step 5: Lock chatbot panel in `dashboard.html` for non-premium**

Find the chat input container element (e.g. `id="chat-input-area"`) and add this after `checkAuth()` in the page script:

```javascript
if (!isPremium() && !isAdmin()) {
  var chatArea = document.getElementById('chat-input-area');
  if (chatArea) {
    chatArea.innerHTML =
      '<p class="chat-locked">Chat is available for premium members.</p>';
  }
}
```

Add CSS:

```css
.chat-locked {
  color: #555;
  font-size: 0.9rem;
  padding: 16px;
  text-align: center;
  border: 1px solid #222;
  border-radius: 8px;
}
```

- [ ] **Step 6: Update `exercises.html` to conditionally show edit/delete buttons**

When rendering each exercise row, check editability before emitting action buttons:

```javascript
var myId = getCurrentUserId();
exercises.forEach(function (ex) {
  var editable = isAdmin() || (ex.user_id !== null && ex.user_id === myId);
  var actions = editable
    ? '<button class="edit-btn" data-id="' + ex.id + '">Edit</button>' +
      '<button class="delete-btn" data-id="' + ex.id + '">Delete</button>'
    : '';
  // use `actions` when building the row HTML
});
```

- [ ] **Step 7: Run full test suite**

```bash
pytest -v
```

Expected: all PASS (frontend changes have no automated tests — verify manually by starting the app)

- [ ] **Step 8: Commit**

```bash
git add app/static/register.html app/static/login.html app/static/auth.js \
        app/static/dashboard.html app/static/exercises.html \
        app/static/index.html app/static/workouts.html app/static/workout.html \
        app/static/exercise.html app/static/routines.html
git commit -m "feat: register page, username in nav, chatbot lock for non-premium"
```
