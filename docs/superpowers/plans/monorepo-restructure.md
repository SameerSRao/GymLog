# Monorepo Restructure — Three-Service Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize GymLog from a single FastAPI container into a monorepo
with three independently deployable services: `api`, `chat`, and `frontend`.

**Architecture:** The `api` service owns all DB logic under domain modules
(`auth/`, `workouts/`, `exercises/`, `routines/`). The `chat` service calls
the core API over HTTP using `httpx`; it never touches the database or JWT
secret. The `frontend` service is an Nginx container that proxies `/api/*`
to the backends and serves static HTML — structured so swapping to React
requires only a Dockerfile + nginx.conf change.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, httpx, google-genai,
Nginx, Docker Compose, pytest

## Global Constraints

- Max line length: 79 characters for code, 72 for docstrings
- Every function, method, and class must have a PEP 257 docstring
- Two blank lines between top-level definitions
- Imports: stdlib, then third-party, then local — each group separated by
  a blank line
- `MuscleGroupSchema` lives in `exercises/schemas.py`; `workouts/schemas.py`
  imports it from there — the only cross-domain schema import
- `auth/service.py` absorbs `user_service.py` functions (`create_user`,
  `get_user_by_username`)
- All test files import from `app.*` — tests run from their service root
  (e.g. `cd services/api && pytest`)

---

## Phase 1: API Service

### Task 1: Monorepo Scaffold + Makefile

**Files:**
- Create: `services/api/app/__init__.py`
- Create: `services/api/app/auth/__init__.py`
- Create: `services/api/app/workouts/__init__.py`
- Create: `services/api/app/exercises/__init__.py`
- Create: `services/api/app/routines/__init__.py`
- Create: `services/api/app/db/__init__.py`
- Create: `services/chat/app/__init__.py`
- Create: `services/chat/app/chat/__init__.py`
- Create: `services/chat/app/tools/__init__.py`
- Create: `services/chat/app/client/__init__.py`
- Create: `services/frontend/src/` (directory)
- Create: `Makefile`

**Interfaces:**
- Produces: empty `__init__.py` files in all new directories; `Makefile`
  with `test` and `up` targets

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p services/api/app/{auth,workouts,exercises,routines,db}
mkdir -p services/api/tests
mkdir -p services/chat/app/{chat,tools,client}
mkdir -p services/chat/tests
mkdir -p services/frontend/src
touch services/api/app/__init__.py
touch services/api/app/auth/__init__.py
touch services/api/app/workouts/__init__.py
touch services/api/app/exercises/__init__.py
touch services/api/app/routines/__init__.py
touch services/api/app/db/__init__.py
touch services/chat/app/__init__.py
touch services/chat/app/chat/__init__.py
touch services/chat/app/tools/__init__.py
touch services/chat/app/client/__init__.py
```

- [ ] **Step 2: Create Makefile at repo root**

```makefile
.PHONY: test up down

test:
	cd services/api  && pytest tests/ -v
	cd services/chat && pytest tests/ -v

up:
	docker compose up --build

down:
	docker compose down
```

- [ ] **Step 3: Commit**

```bash
git add services/ Makefile
git commit -m "chore: scaffold monorepo services directory structure"
```

---

### Task 2: API Service — DB Module

**Files:**
- Create: `services/api/app/db/database.py`
- Create: `services/api/app/db/models.py`
- Create: `services/api/app/db/seed.py`

**Interfaces:**
- Consumes: nothing (source of truth for DB layer)
- Produces:
  - `database.py`: `Base`, `engine`, `SessionLocal`, `get_db()`
  - `models.py`: `User`, `ExerciseDef`, `MuscleGroup`, `Workout`,
    `Exercise`, `Routine`, `RoutineExercise`, `exercise_muscle_groups`
  - `seed.py`: `seed_exercises(db)`, `seed_demo_data(db)`

- [ ] **Step 1: Copy database.py**

Copy `app/db/database.py` to `services/api/app/db/database.py` verbatim —
no import changes needed (it has no local imports).

- [ ] **Step 2: Copy models.py**

Copy `app/model/models.py` to `services/api/app/db/models.py`. Change one
import:

```python
# old
from app.db.database import Base
# new (same — app.db.database still resolves from services/api root)
from app.db.database import Base
```

No change needed; the relative package structure stays the same.

- [ ] **Step 3: Copy seed.py**

Copy `app/db/seed.py` to `services/api/app/db/seed.py`. Update imports:

```python
# old
from app.model.models import ExerciseDef, MuscleGroup, User, Workout
# new
from app.db.models import ExerciseDef, MuscleGroup, User, Workout
```

- [ ] **Step 4: Commit**

```bash
git add services/api/app/db/
git commit -m "feat(api): add db module — database, models, seed"
```

---

### Task 3: API Service — Auth Domain

**Files:**
- Create: `services/api/app/auth/schemas.py`
- Create: `services/api/app/auth/service.py`
- Create: `services/api/app/auth/routes.py`

**Interfaces:**
- Consumes: `app.db.database.get_db`, `app.db.models.User`
- Produces:
  - `schemas.py`: `LoginRequest`, `RegisterRequest`, `TokenResponse`
  - `service.py`: `hash_password(plain)`, `verify_password(plain, hashed)`,
    `check_signup_code(code)`, `create_access_token(data, expires_delta)`,
    `decode_access_token(token)`, `create_user(db, username, password)`,
    `get_user_by_username(db, username)`
  - `routes.py`: `router`, `get_current_user(credentials)`,
    `require_not_demo(current_user)`; endpoints: POST `/auth/login`,
    POST `/auth/register`, GET `/auth/demo`, GET `/auth/me`

- [ ] **Step 1: Create auth/schemas.py**

Copy `LoginRequest`, `RegisterRequest`, `TokenResponse` (and their validators
and the two compiled regexes) from `app/api/schemas.py` verbatim:

```python
import re

from pydantic import BaseModel, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,30}$")
_PASSWORD_RE = re.compile(r"^[\x20-\x7E]{3,72}$")


class LoginRequest(BaseModel):
    """Request schema for the login endpoint."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request schema for the register endpoint."""

    username: str
    password: str
    signup_code: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Reject usernames that don't match [a-zA-Z0-9_-]{3,30}."""
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3–30 characters and contain only "
                "letters, numbers, underscores, and hyphens."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Reject passwords outside printable ASCII or outside 8–72 chars."""
        if not _PASSWORD_RE.match(v):
            raise ValueError(
                "Password must be 3–72 printable characters."
            )
        return v


class TokenResponse(BaseModel):
    """Response schema returned after a successful login."""

    access_token: str
    token_type: str
```

- [ ] **Step 2: Create auth/service.py**

Merge `app/services/auth_service.py` and `app/services/user_service.py`
into one file:

```python
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.db.models import User

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
    """Decode and validate token; raise HTTPException 401 if invalid."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        )


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

- [ ] **Step 3: Create auth/routes.py**

Copy `app/api/auth_routes.py` with updated imports. Also add `GET /auth/me`
endpoint (used by chat service to check premium/demo flags without the JWT
secret):

```python
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.auth.service import (
    check_signup_code,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_username,
    verify_password,
)
from app.db.database import get_db

router = APIRouter()

_TOKEN_EXPIRE_HOURS = 720
_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return its decoded payload; raise 401."""
    return decode_access_token(credentials.credentials)


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


@router.post(
    "/auth/register", response_model=TokenResponse, status_code=201
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create account and return JWT; 400 bad code, 409 duplicate user."""
    if not check_signup_code(body.signup_code):
        raise HTTPException(status_code=400, detail="Invalid signup code")
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = create_user(db, body.username, body.password)
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.get("/auth/demo", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """Return a JWT for the demo user; 503 if demo user is not seeded."""
    user = get_user_by_username(db, "demo")
    if not user or not user.is_demo:
        raise HTTPException(status_code=503, detail="Demo unavailable")
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    """Return current user's profile flags; used by chat service."""
    return {
        "id": int(current_user["sub"]),
        "username": current_user["username"],
        "is_admin": current_user.get("is_admin", False),
        "is_premium": current_user.get("is_premium", False),
        "is_demo": current_user.get("is_demo", False),
    }
```

- [ ] **Step 4: Commit**

```bash
git add services/api/app/auth/
git commit -m "feat(api): add auth domain — schemas, service, routes"
```

---

### Task 4: API Service — Exercises Domain

**Files:**
- Create: `services/api/app/exercises/schemas.py`
- Create: `services/api/app/exercises/service.py`
- Create: `services/api/app/exercises/routes.py`

**Interfaces:**
- Consumes: `app.db.database.get_db`, `app.db.models.*`,
  `app.auth.routes.get_current_user`, `app.auth.routes.require_not_demo`
- Produces:
  - `schemas.py`: `MuscleGroupSchema`, `ExerciseDefSchema`,
    `CreateExerciseSchema`, `ExerciseUpdate`, `ExerciseProgressionSchema`,
    `SessionSummary`, `SetDetail`
  - `service.py`: `get_all_exercises`, `get_exercise`, `create_exercise`,
    `update_exercise`, `delete_exercise`, `get_all_muscle_groups`,
    `get_exercise_progression`
  - `routes.py`: router with GET `/exercises`, POST `/exercises`,
    GET `/exercise/{id}/info`, PUT `/exercise/{id}`,
    DELETE `/exercise/{id}`, GET `/exercise/{id}/progression`,
    GET `/muscle-groups`

- [ ] **Step 1: Create exercises/schemas.py**

`MuscleGroupSchema` must be defined here (canonical owner). Copy all
exercise-related schemas from `app/api/schemas.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class MuscleGroupSchema(BaseModel):
    """Response schema for a muscle group."""

    id: int
    name: str


class ExerciseDefSchema(BaseModel):
    """Response schema for an exercise definition."""

    id: int
    name: str
    equipment: str | None = None
    instructions: str | None = None
    user_id: int | None = None
    muscle_groups: list[MuscleGroupSchema]


class CreateExerciseSchema(BaseModel):
    """Request schema for creating a new exercise."""

    name: str
    equipment: str | None = None
    instructions: str | None = None
    muscle_group_ids: list[int]


class ExerciseUpdate(BaseModel):
    """Request schema for partially updating an exercise; all optional."""

    name: str | None = None
    equipment: str | None = None
    instructions: str | None = None
    muscle_group_ids: list[int] | None = None


class SetDetail(BaseModel):
    """One set with its set number, used in progression responses."""

    set_number: int
    reps: int
    weight_lbs: float | None = None


class SessionSummary(BaseModel):
    """Aggregated summary of one session for a single exercise's progression."""

    session_id: int
    logged_at: datetime
    sets: list[SetDetail]
    volume: float | None = None
    best_set_weight: float | None = None


class ExerciseProgressionSchema(BaseModel):
    """Response schema for an exercise's progression history."""

    exercise_id: int
    exercise_name: str
    sessions: list[SessionSummary]
```

- [ ] **Step 2: Create exercises/service.py**

Copy `app/services/exercise_service.py` verbatim, then update the one
import that changes:

```python
# old
from app.model.models import ExerciseDef, MuscleGroup
# new
from app.db.models import ExerciseDef, MuscleGroup
```

- [ ] **Step 3: Create exercises/routes.py**

Copy `app/api/exercise_routes.py` and update imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user, require_not_demo
from app.db.database import get_db
from app.exercises.schemas import (
    CreateExerciseSchema,
    ExerciseDefSchema,
    ExerciseProgressionSchema,
    ExerciseUpdate,
    MuscleGroupSchema,
    SessionSummary,
    SetDetail,
)
from app.exercises.service import (
    create_exercise,
    delete_exercise,
    get_all_exercises,
    get_all_muscle_groups,
    get_exercise,
    get_exercise_progression,
    update_exercise,
)
```

Route bodies are unchanged from `app/api/exercise_routes.py`.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/exercises/
git commit -m "feat(api): add exercises domain — schemas, service, routes"
```

---

### Task 5: API Service — Workouts Domain

**Files:**
- Create: `services/api/app/workouts/schemas.py`
- Create: `services/api/app/workouts/service.py`
- Create: `services/api/app/workouts/routes.py`

**Interfaces:**
- Consumes: `app.db.database.get_db`, `app.db.models.*`,
  `app.auth.routes.get_current_user`, `app.auth.routes.require_not_demo`,
  `app.exercises.schemas.MuscleGroupSchema` (cross-domain import)
- Produces:
  - `schemas.py`: `SetSchema`, `ExerciseLogRequest`, `WorkoutRequest`,
    `ExerciseSchema`, `WorkoutResponse`, `WorkoutDetailed`,
    `WorkoutImportRequest`, `ImportError`, `ImportResponse`
  - `service.py`: `log_workout`, `get_all_workouts`, `get_workout`,
    `update_workout`, `delete_workout`, `build_workout_detailed`,
    `import_workouts`
  - `routes.py`: router with all workout CRUD + import endpoints

- [ ] **Step 1: Create workouts/schemas.py**

Note the cross-domain import of `MuscleGroupSchema` from exercises:

```python
from datetime import datetime

from pydantic import BaseModel

from app.exercises.schemas import MuscleGroupSchema


class SetSchema(BaseModel):
    """One set in a workout log request or response."""

    reps: int
    weight_lbs: float | None = None


class ExerciseLogRequest(BaseModel):
    """One exercise entry (with sets) inside a workout log request."""

    exercise_id: int
    sets: list[SetSchema]


class WorkoutRequest(BaseModel):
    """Request schema for creating or replacing a workout session."""

    exercises: list[ExerciseLogRequest]
    notes: str | None = None
    logged_at: datetime | None = None


class ExerciseSchema(BaseModel):
    """One exercise with sets, as returned in a detailed workout response."""

    exercise_id: int
    name: str
    muscle_groups: list[MuscleGroupSchema]
    sets: list[SetSchema]


class WorkoutResponse(BaseModel):
    """Summary response for creating or listing workout sessions."""

    session_id: int
    logged_at: datetime
    exercises_logged: int
    sets_logged: int


class WorkoutDetailed(BaseModel):
    """Full workout detail response including all exercises and sets."""

    session_id: int
    logged_at: datetime
    notes: str | None = None
    exercises: list[ExerciseSchema]


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

- [ ] **Step 2: Create workouts/service.py**

Copy `app/services/workout_service.py` and update imports:

```python
# old
from app.api.schemas import (
    ExerciseLogRequest, ExerciseSchema, ImportError, ImportResponse,
    MuscleGroupSchema, SetSchema, WorkoutImportRequest, WorkoutRequest,
)
from app.model.models import Exercise, ExerciseDef, MuscleGroup, Workout
# new
from app.db.models import Exercise, ExerciseDef, MuscleGroup, Workout
from app.workouts.schemas import (
    ExerciseLogRequest, ExerciseSchema, ImportError, ImportResponse,
    SetSchema, WorkoutImportRequest, WorkoutRequest,
)
from app.exercises.schemas import MuscleGroupSchema
```

All function bodies are unchanged.

- [ ] **Step 3: Create workouts/routes.py**

Copy `app/api/workout_routes.py` and update imports:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user, require_not_demo
from app.db.database import get_db
from app.workouts.schemas import (
    ImportResponse,
    WorkoutDetailed,
    WorkoutImportRequest,
    WorkoutRequest,
    WorkoutResponse,
)
from app.workouts.service import (
    build_workout_detailed,
    delete_workout,
    get_all_workouts,
    get_workout,
    import_workouts,
    log_workout,
    update_workout,
)
```

Route bodies are unchanged.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/workouts/
git commit -m "feat(api): add workouts domain — schemas, service, routes"
```

---

### Task 6: API Service — Routines Domain

**Files:**
- Create: `services/api/app/routines/schemas.py`
- Create: `services/api/app/routines/service.py`
- Create: `services/api/app/routines/routes.py`

**Interfaces:**
- Consumes: `app.db.database.get_db`, `app.db.models.*`,
  `app.auth.routes.get_current_user`, `app.auth.routes.require_not_demo`
- Produces:
  - `schemas.py`: `RoutineExerciseRequest`, `RoutineCreate`, `RoutineUpdate`,
    `RoutineExerciseDetail`, `RoutineListItem`, `RoutineDetail`
  - `service.py`: `get_all_routines`, `get_routine`, `create_routine`,
    `update_routine`, `delete_routine`
  - `routes.py`: router with full routine CRUD

- [ ] **Step 1: Create routines/schemas.py**

```python
from datetime import datetime

from pydantic import BaseModel


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
    created_at: datetime


class RoutineDetail(BaseModel):
    """Full routine response with ordered exercises."""

    id: int
    name: str
    created_at: datetime
    exercises: list[RoutineExerciseDetail]
```

- [ ] **Step 2: Create routines/service.py**

Copy `app/services/routine_service.py` and update one import:

```python
# old
from app.model.models import Routine, RoutineExercise
# new
from app.db.models import Routine, RoutineExercise
```

- [ ] **Step 3: Create routines/routes.py**

Copy `app/api/routine_routes.py` and update imports:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user, require_not_demo
from app.db.database import get_db
from app.db.models import ExerciseDef, Routine
from app.routines.schemas import (
    RoutineCreate,
    RoutineDetail,
    RoutineExerciseDetail,
    RoutineListItem,
    RoutineUpdate,
)
from app.routines.service import (
    create_routine,
    delete_routine,
    get_all_routines,
    get_routine,
    update_routine,
)
```

All helper functions (`_validate_exercise_ids`, `_to_detail`) and route
bodies are unchanged.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/routines/
git commit -m "feat(api): add routines domain — schemas, service, routes"
```

---

### Task 7: API Service — main.py, admin.py, Dockerfile, requirements.txt, pytest.ini

**Files:**
- Create: `services/api/app/main.py`
- Create: `services/api/app/admin.py`
- Create: `services/api/Dockerfile`
- Create: `services/api/requirements.txt`
- Create: `services/api/pytest.ini`

**Interfaces:**
- Consumes: all domain routers from Tasks 3–6
- Produces: runnable FastAPI app at `services/api/`; `admin.py` CLI for
  user promotion

- [ ] **Step 1: Create services/api/app/main.py**

```python
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_demo_data, seed_exercises
from app.exercises.routes import router as exercise_router
from app.routines.routes import router as routine_router
from app.workouts.routes import router as workout_router

if not os.getenv("TESTING"):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_exercises(db)
        seed_demo_data(db)

_dev = os.getenv("ENVIRONMENT") == "development"
app = FastAPI(
    docs_url="/docs" if _dev else None,
    redoc_url="/redoc" if _dev else None,
)

_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(workout_router, prefix="/api")
app.include_router(exercise_router, prefix="/api")
app.include_router(routine_router, prefix="/api")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
```

Note: chat router is not included — it lives in the chat service.

- [ ] **Step 2: Create services/api/app/admin.py**

Copy `app/admin.py` and update imports:

```python
# old
from app.db.database import SessionLocal
from app.model.models import User
# new
from app.db.database import SessionLocal
from app.db.models import User
```

All function bodies are unchanged.

- [ ] **Step 3: Create services/api/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Create services/api/requirements.txt**

Copy the relevant lines from the root `requirements.txt`. Exclude
`google-genai` and `httpx` (those belong to chat service):

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic[email]
python-jose[cryptography]
bcrypt
python-multipart
pytest
httpx
pytest-asyncio
```

Note: `httpx` is needed for `TestClient` in tests.

- [ ] **Step 5: Create services/api/pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .

markers =
    slow: marks tests as slow (run with -m slow)
```

- [ ] **Step 6: Commit**

```bash
git add services/api/
git commit -m "feat(api): add main.py, admin.py, Dockerfile, requirements, pytest.ini"
```

---

### Task 8: API Service — Tests Migration

**Files:**
- Create: `services/api/tests/conftest.py`
- Create: `services/api/tests/test_auth.py`
- Create: `services/api/tests/test_demo.py`
- Create: `services/api/tests/test_exercises.py`
- Create: `services/api/tests/test_import.py`
- Create: `services/api/tests/test_routines.py`
- Create: `services/api/tests/test_seed.py`
- Create: `services/api/tests/test_workouts.py`
- Create: `services/api/tests/test_models.py`
- Create: `services/api/tests/test_admin.py`

**Interfaces:**
- Consumes: `services/api/app/main.py` via TestClient
- Produces: passing test suite at `services/api/`

- [ ] **Step 1: Copy conftest.py with updated imports**

Copy `tests/conftest.py` to `services/api/tests/conftest.py`. Update all
import paths (old `app.api.*` → new domain paths):

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

from app.auth.routes import get_current_user
from app.db.database import Base, get_db
from app.db.models import ExerciseDef, MuscleGroup
from app.main import app

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
    from app.auth.service import create_user
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
    """Provide a clean SQLAlchemy session for the in-memory test database."""
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

- [ ] **Step 2: Copy remaining test files**

For each file, copy verbatim and apply the same import substitutions.
The pattern is consistent throughout:

| Old import | New import |
|---|---|
| `from app.api.auth_routes import ...` | `from app.auth.routes import ...` |
| `from app.api.schemas import ...` | `from app.<domain>.schemas import ...` |
| `from app.db.database import ...` | `from app.db.database import ...` |
| `from app.model.models import ...` | `from app.db.models import ...` |
| `from app.services.auth_service import ...` | `from app.auth.service import ...` |
| `from app.services.workout_service import ...` | `from app.workouts.service import ...` |
| `from app.services.exercise_service import ...` | `from app.exercises.service import ...` |
| `from app.services.routine_service import ...` | `from app.routines.service import ...` |
| `from app.services.user_service import ...` | `from app.auth.service import ...` |
| `from app.main import app` | `from app.main import app` |

Schema imports are split by domain. Examples:
- `ExerciseDefSchema`, `MuscleGroupSchema`, `CreateExerciseSchema`,
  `ExerciseUpdate`, `ExerciseProgressionSchema`, `SessionSummary`,
  `SetDetail` → `from app.exercises.schemas import ...`
- `WorkoutRequest`, `WorkoutResponse`, `WorkoutDetailed`,
  `ExerciseLogRequest`, `SetSchema`, `ImportResponse`,
  `WorkoutImportRequest`, `ImportError` → `from app.workouts.schemas import ...`
- `RoutineCreate`, `RoutineUpdate`, `RoutineDetail`, `RoutineListItem`,
  `RoutineExerciseRequest`, `RoutineExerciseDetail`
  → `from app.routines.schemas import ...`
- `LoginRequest`, `RegisterRequest`, `TokenResponse`
  → `from app.auth.schemas import ...`

Do NOT copy `tests/test_chat.py` — it tests the chat endpoint which moves
to the chat service in Phase 2.

- [ ] **Step 3: Run tests from services/api to verify**

```bash
cd services/api && pytest tests/ -v
```

Expected: all tests pass (same count as root test suite minus test_chat).
If any imports fail, fix them by tracing to the correct domain schema.

- [ ] **Step 4: Commit**

```bash
git add services/api/tests/
git commit -m "feat(api): migrate tests to services/api/tests with updated imports"
```

---

## Phase 2: Chat Service

### Task 9: Chat Service — API Client + Base Helpers

**Files:**
- Create: `services/chat/app/client/api_client.py`
- Create: `services/chat/app/tools/base.py`

**Interfaces:**
- Produces:
  - `api_client.py`: `ApiClient` class with sync `httpx.Client`; methods:
    `get_exercises`, `get_workouts`, `get_workout`, `post_workout`,
    `put_workout`, `delete_workout`, `get_exercise_progression`,
    `post_exercise`, `put_exercise`, `delete_exercise`, `get_routines`,
    `post_routine`, `put_routine`, `delete_routine`, `get_me`
  - `tools/base.py`: pure functions on plain dicts (no DB, no HTTP):
    `_best_exercise_match`, `_resolve_muscle_groups`, `_resolve_routine`

- [ ] **Step 1: Create services/chat/app/client/api_client.py**

```python
import os

import httpx

_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def _auth(token: str) -> dict:
    """Return Authorization header dict for token."""
    return {"Authorization": f"Bearer {token}"}


class ApiClient:
    """Sync httpx client for calling the core API service."""

    def __init__(self, base_url: str = _API_BASE_URL) -> None:
        """Initialise the client with the core API base URL."""
        self._client = httpx.Client(
            base_url=base_url, timeout=30.0
        )

    def get_me(self, token: str) -> dict:
        """Return current user's profile flags from GET /api/auth/me."""
        r = self._client.get("/api/auth/me", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def get_exercises(self, token: str) -> list[dict]:
        """Return all exercises visible to user from GET /api/exercises."""
        r = self._client.get("/api/exercises", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def post_exercise(self, token: str, data: dict) -> dict:
        """Create an exercise via POST /api/exercises."""
        r = self._client.post(
            "/api/exercises", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_exercise(
        self, token: str, exercise_id: int, data: dict
    ) -> dict:
        """Update an exercise via PUT /api/exercise/{id}."""
        r = self._client.put(
            f"/api/exercise/{exercise_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_exercise(self, token: str, exercise_id: int) -> bool:
        """Delete an exercise via DELETE /api/exercise/{id}."""
        r = self._client.delete(
            f"/api/exercise/{exercise_id}", headers=_auth(token)
        )
        return r.status_code == 204

    def get_exercise_progression(
        self, token: str, exercise_id: int
    ) -> dict:
        """Return progression data from GET /api/exercise/{id}/progression."""
        r = self._client.get(
            f"/api/exercise/{exercise_id}/progression",
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def get_workouts(
        self,
        token: str,
        year: int | None = None,
        month: int | None = None,
    ) -> list[dict]:
        """Return workout summaries from GET /api/workouts."""
        params = {}
        if year is not None:
            params["year"] = year
        if month is not None:
            params["month"] = month
        r = self._client.get(
            "/api/workouts", params=params, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def post_workout(self, token: str, data: dict) -> dict:
        """Log a workout via POST /api/workouts."""
        r = self._client.post(
            "/api/workouts", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_workout(
        self, token: str, session_id: int, data: dict
    ) -> dict:
        """Replace a workout via PUT /api/workout/{id}."""
        r = self._client.put(
            f"/api/workout/{session_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_workout(self, token: str, session_id: int) -> bool:
        """Delete a workout via DELETE /api/workout/{id}."""
        r = self._client.delete(
            f"/api/workout/{session_id}", headers=_auth(token)
        )
        return r.status_code == 200

    def get_routines(self, token: str) -> list[dict]:
        """Return all routines from GET /api/routines."""
        r = self._client.get("/api/routines", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def post_routine(self, token: str, data: dict) -> dict:
        """Create a routine via POST /api/routines."""
        r = self._client.post(
            "/api/routines", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_routine(
        self, token: str, routine_id: int, data: dict
    ) -> dict:
        """Replace a routine via PUT /api/routine/{id}."""
        r = self._client.put(
            f"/api/routine/{routine_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_routine(self, token: str, routine_id: int) -> bool:
        """Delete a routine via DELETE /api/routine/{id}."""
        r = self._client.delete(
            f"/api/routine/{routine_id}", headers=_auth(token)
        )
        return r.status_code == 200

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()


api_client = ApiClient()
```

- [ ] **Step 2: Create services/chat/app/tools/base.py**

Pure helper functions that work on plain dicts from API responses (no DB,
no imports from the API service):

```python


def _best_exercise_match(
    query_words: list[str], exercises: list[dict]
) -> dict | None:
    """Return the best matching exercise dict, or None if no match.

    Prefers full-word match over substring match.
    """
    q_set = set(query_words)
    word_matches = [
        e for e in exercises
        if q_set.issubset(set(e["name"].lower().split()))
    ]
    if word_matches:
        return word_matches[0]
    query_str = " ".join(query_words)
    sub_matches = [e for e in exercises if query_str in e["name"].lower()]
    return sub_matches[0] if sub_matches else None


def _resolve_muscle_groups(
    names: list[str], all_exercises: list[dict]
) -> tuple[list[int], list[str]]:
    """Resolve muscle group name strings to IDs using exercise data.

    Returns (matched_ids, unresolved_names). Extracts unique muscle
    groups from the exercises list (each exercise has muscle_groups list
    with id and name).
    """
    seen: dict[str, int] = {}
    for ex in all_exercises:
        for mg in ex.get("muscle_groups", []):
            seen[mg["name"].lower()] = mg["id"]

    matched_ids: list[int] = []
    unresolved: list[str] = []
    for name in names:
        q = name.lower()
        match_id = next(
            (mid for mname, mid in seen.items() if q in mname), None
        )
        if match_id is not None:
            matched_ids.append(match_id)
        else:
            unresolved.append(name)
    return matched_ids, unresolved


def _resolve_routine(
    name: str, routines: list[dict]
) -> dict:
    """Return matching routine dict or an error dict.

    Returns error dict if zero or multiple routines match.
    """
    q = name.lower()
    matches = [r for r in routines if q in r["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {
            "error": (
                f"Multiple routines match '{name}': "
                f"{[r['name'] for r in matches]}. Be more specific."
            )
        }
    names = [r["name"] for r in routines]
    return {
        "error": (
            f"No routine found matching '{name}'. "
            f"Your routines: {names}"
        )
    }
```

- [ ] **Step 3: Commit**

```bash
git add services/chat/app/client/ services/chat/app/tools/base.py
git commit -m "feat(chat): add api_client and pure base helpers"
```

---

### Task 10: Chat Service — Tool Handlers

**Files:**
- Create: `services/chat/app/tools/workouts.py`
- Create: `services/chat/app/tools/exercises.py`
- Create: `services/chat/app/tools/routines.py`
- Modify: `services/chat/app/tools/__init__.py`

**Interfaces:**
- Consumes: `app.client.api_client.api_client` (singleton),
  `app.tools.base._best_exercise_match`, `app.tools.base._resolve_muscle_groups`,
  `app.tools.base._resolve_routine`
- Produces:
  - `workouts.py`: `WORKOUT_DECLARATIONS`, `handle_workout_tool(name, inputs, token, local_time)`
  - `exercises.py`: `EXERCISE_DECLARATIONS`, `handle_exercise_tool(name, inputs, token)`
  - `routines.py`: `ROUTINE_DECLARATIONS`, `handle_routine_tool(name, inputs, token)`
  - `__init__.py`: `TOOLS`, `execute_tool(name, inputs, token, local_time)`

Note: tool handler signatures change from `(name, inputs, db, user_id)` to
`(name, inputs, token)` — the token is forwarded to api_client calls.

- [ ] **Step 1: Create tools/workouts.py**

Copy `app/services/chat_tools/workouts.py`. Remove all SQLAlchemy/DB
imports. Replace DB calls with `api_client.*` calls. Key changes:

```python
import json
from datetime import datetime, timedelta, timezone

from google.genai import types

from app.client.api_client import api_client
from app.tools.base import _best_exercise_match

WORKOUT_DECLARATIONS = [
    # Copy WORKOUT_DECLARATIONS verbatim from old workouts.py
    # (FunctionDeclaration objects — no imports change here)
]


def _resolve_exercise_inputs(
    exercise_inputs: list[dict],
    ex_by_name: dict[str, dict],
    all_ex: list[dict],
) -> tuple[list[dict], list[str]]:
    """Resolve exercise name dicts to exercise_id request dicts.

    Returns (exercise_log_dicts, not_found_names).
    Each exercise_log_dict has keys: exercise_id, sets.
    """
    logged: list[dict] = []
    not_found: list[str] = []
    for ex in exercise_inputs:
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        sets = [
            {"reps": s["reps"], "weight_lbs": s.get("weight_lbs")}
            for s in ex["sets"]
        ]
        logged.append({"exercise_id": match["id"], "sets": sets})
    return logged, not_found


def handle_workout_tool(
    name: str,
    inputs: dict,
    token: str,
    local_time: str | None = None,
) -> str:
    """Dispatch a workout tool call; return result as a JSON string."""
    if name == "get_recent_workouts":
        days = inputs.get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        workouts = api_client.get_workouts(token)
        recent = []
        for w in workouts:
            logged_str = w["logged_at"]
            logged = datetime.fromisoformat(logged_str)
            if logged.tzinfo is None:
                logged = logged.replace(tzinfo=timezone.utc)
            if logged < cutoff:
                continue
            recent.append({
                "session_id": w["session_id"],
                "date": logged.strftime("%Y-%m-%d"),
                "total_sets": w["sets_logged"],
                "exercises_count": w["exercises_logged"],
            })
        return json.dumps({"workouts": recent, "count": len(recent)})

    if name == "log_workout":
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
        logged, not_found = _resolve_exercise_inputs(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        raw_ts = inputs.get("logged_at") or local_time
        logged_at = None
        if raw_ts:
            try:
                logged_at = datetime.fromisoformat(raw_ts).isoformat()
            except ValueError:
                pass
        data = {"exercises": logged, "notes": inputs.get("notes")}
        if logged_at:
            data["logged_at"] = logged_at
        try:
            result = api_client.post_workout(token, data)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({
            "success": True,
            "session_id": result["session_id"],
            "logged_at": result["logged_at"],
            "exercises_logged": result["exercises_logged"],
        })

    if name == "delete_workout":
        session_id = inputs["session_id"]
        try:
            found = api_client.delete_workout(token, session_id)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        if not found:
            return json.dumps({
                "error": f"Workout session {session_id} not found."
            })
        return json.dumps({
            "success": True,
            "deleted_session_id": session_id,
        })

    if name == "update_workout":
        session_id = inputs["session_id"]
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
        logged, not_found = _resolve_exercise_inputs(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        data = {"exercises": logged, "notes": inputs.get("notes")}
        try:
            result = api_client.put_workout(token, session_id, data)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({
            "success": True,
            "session_id": result["session_id"],
            "exercises_updated": result["exercises_logged"],
        })

    return json.dumps({"error": f"Unknown workout tool: {name}"})
```

- [ ] **Step 2: Create tools/exercises.py**

```python
import json

from google.genai import types

from app.client.api_client import api_client
from app.tools.base import _best_exercise_match, _resolve_muscle_groups

EXERCISE_DECLARATIONS = [
    # Copy EXERCISE_DECLARATIONS verbatim from old exercises.py
]


def handle_exercise_tool(
    name: str, inputs: dict, token: str
) -> str:
    """Dispatch an exercise tool call; return result as a JSON string."""
    if name == "search_exercises":
        query = inputs["query"].lower()
        exercises = api_client.get_exercises(token)
        matches = [
            {
                "id": e["id"],
                "name": e["name"],
                "equipment": e.get("equipment"),
                "muscle_groups": [
                    mg["name"] for mg in e.get("muscle_groups", [])
                ],
            }
            for e in exercises
            if query in e["name"].lower()
            or any(
                query in mg["name"].lower()
                for mg in e.get("muscle_groups", [])
            )
        ][:20]
        return json.dumps({"matches": matches, "count": len(matches)})

    if name == "get_exercise_progression":
        raw_name = inputs["exercise_name"]
        query_words = raw_name.lower().split()
        exercises = api_client.get_exercises(token)
        q_set = set(query_words)
        candidates = [
            e for e in exercises
            if q_set.issubset(set(e["name"].lower().split()))
        ]
        if not candidates:
            candidates = [
                e for e in exercises
                if " ".join(query_words) in e["name"].lower()
            ]
        if not candidates:
            return json.dumps({
                "error": (
                    f"No exercise found matching '{raw_name}'."
                    " Try search_exercises to find the correct name."
                )
            })
        best = None
        best_sessions: list = []
        for candidate in candidates[:5]:
            try:
                data = api_client.get_exercise_progression(
                    token, candidate["id"]
                )
                sessions = data.get("sessions", [])
            except Exception:
                sessions = []
            if len(sessions) > len(best_sessions):
                best = candidate
                best_sessions = sessions
        if not best or not best_sessions:
            names = ", ".join(c["name"] for c in candidates[:5])
            return json.dumps({
                "error": (
                    f"No logged data found for '{raw_name}'."
                    f" Matching exercises: {names}."
                    " Have you logged any of these?"
                )
            })
        return json.dumps({
            "exercise": best["name"],
            "sessions": [
                {
                    "date": s["logged_at"][:10],
                    "sets": len(s.get("sets", [])),
                    "volume": s.get("volume"),
                    "best_set_weight": s.get("best_set_weight"),
                }
                for s in best_sessions[-10:]
            ],
        })

    if name == "create_exercise":
        mg_names = inputs.get("muscle_group_names", [])
        exercises = api_client.get_exercises(token)
        mg_ids, unresolved = _resolve_muscle_groups(mg_names, exercises)
        if unresolved:
            return json.dumps({
                "error": (
                    f"Unknown muscle groups: {unresolved}."
                    " Try search_exercises to find valid muscle group names."
                )
            })
        data = {
            "name": inputs["name"],
            "equipment": inputs.get("equipment"),
            "instructions": None,
            "muscle_group_ids": mg_ids,
        }
        try:
            result = api_client.post_exercise(token, data)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({
            "success": True,
            "exercise_id": result["id"],
            "name": result["name"],
        })

    if name == "update_exercise":
        raw_name = inputs["exercise_name"]
        exercises = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in exercises}
        match = ex_by_name.get(raw_name.lower()) or _best_exercise_match(
            raw_name.lower().split(), exercises
        )
        if not match:
            return json.dumps({
                "error": (
                    f"No exercise found matching '{raw_name}'."
                    " Use search_exercises to find the correct name."
                )
            })
        mg_ids = None
        if inputs.get("muscle_group_names"):
            mg_ids, unresolved = _resolve_muscle_groups(
                inputs["muscle_group_names"], exercises
            )
            if unresolved:
                return json.dumps({
                    "error": f"Unknown muscle groups: {unresolved}."
                })
        data = {
            "name": inputs.get("new_name"),
            "equipment": inputs.get("equipment"),
            "muscle_group_ids": mg_ids,
        }
        try:
            result = api_client.put_exercise(token, match["id"], data)
        except Exception as exc:
            err = str(exc)
            if "403" in err:
                return json.dumps({
                    "error": (
                        f"You don't have permission to edit '{match['name']}'."
                        " You can only edit exercises you created."
                    )
                })
            if "409" in err:
                return json.dumps({
                    "error": (
                        f"An exercise named '{inputs.get('new_name')}'"
                        " already exists."
                    )
                })
            return json.dumps({"error": err})
        return json.dumps({
            "success": True,
            "exercise_id": result["id"],
            "name": result["name"],
        })

    if name == "delete_exercise":
        raw_name = inputs["exercise_name"]
        exercises = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in exercises}
        match = ex_by_name.get(raw_name.lower()) or _best_exercise_match(
            raw_name.lower().split(), exercises
        )
        if not match:
            return json.dumps({
                "error": f"No exercise found matching '{raw_name}'."
            })
        try:
            api_client.delete_exercise(token, match["id"])
        except Exception as exc:
            err = str(exc)
            if "403" in err:
                return json.dumps({
                    "error": (
                        f"You don't have permission to delete"
                        f" '{match['name']}'."
                    )
                })
            if "409" in err:
                return json.dumps({
                    "error": (
                        f"'{match['name']}' has logged workout history"
                        " and cannot be deleted."
                    )
                })
            return json.dumps({"error": err})
        return json.dumps({"success": True, "deleted": match["name"]})

    return json.dumps({"error": f"Unknown exercise tool: {name}"})
```

- [ ] **Step 3: Create tools/routines.py**

```python
import json

from google.genai import types

from app.client.api_client import api_client
from app.tools.base import _best_exercise_match, _resolve_routine

ROUTINE_DECLARATIONS = [
    # Copy ROUTINE_DECLARATIONS verbatim from old routines.py
]


def _resolve_routine_exercises(
    exercise_inputs: list[dict],
    ex_by_name: dict,
    all_ex: list[dict],
) -> tuple[list[dict], list[str]]:
    """Resolve exercise name dicts to routine exercise request dicts.

    Returns (request_dicts, not_found_names). Each dict has keys:
    exercise_id, position, num_sets.
    """
    requests: list[dict] = []
    not_found: list[str] = []
    for i, ex in enumerate(exercise_inputs):
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        requests.append({
            "exercise_id": match["id"],
            "position": i + 1,
            "num_sets": ex["sets"],
        })
    return requests, not_found


def handle_routine_tool(
    name: str, inputs: dict, token: str
) -> str:
    """Dispatch a routine tool call; return result as a JSON string."""
    if name == "get_routines":
        try:
            routines = api_client.get_routines(token)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"routines": routines, "count": len(routines)})

    if name == "create_routine":
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
        exercise_reqs, not_found = _resolve_routine_exercises(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        data = {"name": inputs["name"], "exercises": exercise_reqs}
        try:
            result = api_client.post_routine(token, data)
        except Exception as exc:
            err = str(exc)
            if "409" in err:
                return json.dumps({
                    "error": (
                        f"You already have a routine named '{inputs['name']}'."
                    )
                })
            return json.dumps({"error": err})
        return json.dumps({
            "success": True,
            "routine_id": result["id"],
            "name": result["name"],
            "exercises": len(exercise_reqs),
        })

    if name == "update_routine":
        routines = api_client.get_routines(token)
        routine_or_err = _resolve_routine(inputs["routine_name"], routines)
        if "error" in routine_or_err:
            return json.dumps(routine_or_err)
        routine = routine_or_err
        new_name = inputs.get("new_name") or routine["name"]
        if inputs.get("exercises"):
            all_ex = api_client.get_exercises(token)
            ex_by_name = {e["name"].lower(): e for e in all_ex}
            exercise_reqs, not_found = _resolve_routine_exercises(
                inputs["exercises"], ex_by_name, all_ex
            )
            if not_found:
                return json.dumps({
                    "error": (
                        f"Exercises not found: {', '.join(not_found)}."
                    )
                })
        else:
            exercise_reqs = [
                {
                    "exercise_id": ex["exercise_id"],
                    "position": ex["position"],
                    "num_sets": ex["num_sets"],
                }
                for ex in sorted(
                    routine.get("exercises", []),
                    key=lambda x: x["position"],
                )
            ]
        data = {"name": new_name, "exercises": exercise_reqs}
        try:
            result = api_client.put_routine(token, routine["id"], data)
        except Exception as exc:
            err = str(exc)
            if "409" in err:
                return json.dumps({
                    "error": f"You already have a routine named '{new_name}'."
                })
            return json.dumps({"error": err})
        return json.dumps({
            "success": True,
            "routine_id": result["id"],
            "name": result["name"],
        })

    if name == "delete_routine":
        routines = api_client.get_routines(token)
        routine_or_err = _resolve_routine(inputs["routine_name"], routines)
        if "error" in routine_or_err:
            return json.dumps(routine_or_err)
        routine = routine_or_err
        try:
            api_client.delete_routine(token, routine["id"])
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "deleted": routine["name"]})

    return json.dumps({"error": f"Unknown routine tool: {name}"})
```

- [ ] **Step 4: Update tools/__init__.py**

```python
import json

from google.genai import types

from app.tools.exercises import EXERCISE_DECLARATIONS, handle_exercise_tool
from app.tools.routines import ROUTINE_DECLARATIONS, handle_routine_tool
from app.tools.workouts import WORKOUT_DECLARATIONS, handle_workout_tool

TOOLS = types.Tool(
    function_declarations=(
        WORKOUT_DECLARATIONS + EXERCISE_DECLARATIONS + ROUTINE_DECLARATIONS
    )
)

_WORKOUT_NAMES = {d.name for d in WORKOUT_DECLARATIONS}
_EXERCISE_NAMES = {d.name for d in EXERCISE_DECLARATIONS}
_ROUTINE_NAMES = {d.name for d in ROUTINE_DECLARATIONS}


def execute_tool(
    name: str,
    inputs: dict,
    token: str,
    local_time: str | None = None,
) -> str:
    """Dispatch a tool call by name with user token; return result as JSON."""
    if name in _WORKOUT_NAMES:
        return handle_workout_tool(name, inputs, token, local_time=local_time)
    if name in _EXERCISE_NAMES:
        return handle_exercise_tool(name, inputs, token)
    if name in _ROUTINE_NAMES:
        return handle_routine_tool(name, inputs, token)
    return json.dumps({"error": f"Unknown tool: {name}"})
```

- [ ] **Step 5: Commit**

```bash
git add services/chat/app/tools/
git commit -m "feat(chat): rewrite tool handlers to use HTTP api_client"
```

---

### Task 11: Chat Service — Service, Routes, Schemas, Main

**Files:**
- Create: `services/chat/app/chat/schemas.py`
- Create: `services/chat/app/chat/service.py`
- Create: `services/chat/app/chat/routes.py`
- Create: `services/chat/app/main.py`
- Move: `app/context/` → `services/chat/app/context/`

**Interfaces:**
- Consumes: `app.tools.execute_tool`, `app.tools.TOOLS`,
  `app.client.api_client.api_client`
- Produces: runnable FastAPI chat service on port 8000 (internal)

- [ ] **Step 1: Copy app/context/ to services/chat/app/context/**

```bash
cp -r app/context services/chat/app/context
```

- [ ] **Step 2: Create chat/schemas.py**

```python
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """One turn in the conversation history sent from the client."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    messages: list[ChatMessage]
    local_time: str | None = None
```

- [ ] **Step 3: Create chat/service.py**

The main change from the original: takes `token` instead of `(db, user_id)`.
`_build_dynamic_context` is simplified (no per-exercise frequency — that
would require N+1 HTTP calls). The `execute_tool` call passes `token`
instead of `db + user_id`.

```python
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Generator

from google import genai
from google.genai import types

from app.client.api_client import api_client
from app.tools import TOOLS, execute_tool

_client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
_MODEL = "gemini-2.0-flash"

_CONTEXT_DIR = Path(__file__).parent.parent / "context"
_SYSTEM_PROMPT = (_CONTEXT_DIR / "system_prompt.md").read_text()
_KNOWLEDGE = (_CONTEXT_DIR / "knowledge.md").read_text()

_MAX_HISTORY = 20
_MAX_TOOL_ROUNDS = 10


def _build_dynamic_context(token: str) -> str:
    """Return a short string summarising the user's data for the system prompt."""
    workouts = api_client.get_workouts(token)
    total = len(workouts)
    last_logged = (
        workouts[0]["logged_at"][:10] if workouts else "never"
    )
    routines = api_client.get_routines(token)
    routine_names = [r["name"] for r in routines]

    lines = [
        "## Your User's Training Data",
        f"Total workouts logged: {total}",
        f"Last workout: {last_logged}",
    ]
    if routine_names:
        lines.append(f"Saved routines: {', '.join(routine_names)}")
    return "\n".join(lines)


def run_chat(
    token: str,
    messages: list[dict[str, str]],
    local_time: str | None = None,
) -> Generator[str, None, None]:
    """Run the agentic tool loop for the given JWT token; yield SSE chunks."""
    dynamic_context = _build_dynamic_context(token)
    parts = [_SYSTEM_PROMPT, _KNOWLEDGE, dynamic_context]
    if local_time:
        parts.append(f"User's current local time: {local_time}")
    system_content = "\n\n".join(parts)

    recent = messages[-_MAX_HISTORY:]
    contents: list[types.Content] = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in recent
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_content,
        tools=[TOOLS],
    )

    for _ in range(_MAX_TOOL_ROUNDS):
        for attempt in range(4):
            try:
                response = _client.models.generate_content(
                    model=_MODEL,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                if "429" in str(exc) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise

        candidate = response.candidates[0]
        func_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call is not None
        ]

        if not func_calls:
            yield response.text or ""
            break

        contents.append(candidate.content)

        result_parts = []
        for fc in func_calls:
            result = json.loads(
                execute_tool(
                    fc.name, dict(fc.args), token, local_time=local_time,
                )
            )
            result_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response=result,
                )
            )

        contents.append(types.Content(role="user", parts=result_parts))
    else:
        yield "Sorry, I wasn't able to complete that request. Please try again."
```

- [ ] **Step 4: Create chat/routes.py**

The route no longer takes `db`. It reads the raw token from the
`Authorization` header, calls `GET /api/auth/me` to validate and check
premium status, then calls `run_chat(token, ...)`.

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.chat.schemas import ChatRequest
from app.chat.service import run_chat
from app.client.api_client import api_client

router = APIRouter()
_bearer = HTTPBearer()


@router.post("/chat")
def chat(
    body: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """Stream AI response over SSE; 401/403 propagated from core API."""
    token = credentials.credentials
    try:
        user = api_client.get_me(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if user.get("is_demo"):
        raise HTTPException(
            status_code=403,
            detail="Demo accounts cannot perform this action",
        )
    if not user.get("is_premium") and not user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Premium subscription required"
        )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def generate():
        """Yield SSE-formatted chunks from the agentic tool loop."""
        try:
            for chunk in run_chat(token, messages, local_time=body.local_time):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 5: Create services/chat/app/main.py**

```python
from fastapi import FastAPI

from app.chat.routes import router as chat_router

app = FastAPI(docs_url=None, redoc_url=None)
app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
```

- [ ] **Step 6: Commit**

```bash
git add services/chat/app/
git commit -m "feat(chat): add service, routes, schemas, main.py"
```

---

### Task 12: Chat Service — Dockerfile, requirements.txt, Tests

**Files:**
- Create: `services/chat/Dockerfile`
- Create: `services/chat/requirements.txt`
- Create: `services/chat/pytest.ini`
- Create: `services/chat/tests/conftest.py`
- Create: `services/chat/tests/test_chat.py`

**Interfaces:**
- Consumes: `app.chat.routes`, `app.client.api_client.api_client`
- Produces: runnable chat container; test suite that mocks `api_client`
  and `run_chat` — never hits real API or Gemini

- [ ] **Step 1: Create services/chat/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create services/chat/requirements.txt**

```
fastapi
uvicorn[standard]
httpx
google-genai
python-jose[cryptography]
pytest
```

- [ ] **Step 3: Create services/chat/pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Create services/chat/tests/conftest.py**

```python
import os

os.environ.setdefault("JWT_SECRET", "testsecret123")
os.environ.setdefault("GOOGLE_API_KEY", "fake-key")
os.environ.setdefault("API_BASE_URL", "http://testapi:8000")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """Return a TestClient for the chat service."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    """Return Authorization headers with a fake JWT token."""
    return {"Authorization": "Bearer fake-token"}
```

- [ ] **Step 5: Write failing test for premium check**

Create `services/chat/tests/test_chat.py`:

```python
import pytest
from unittest.mock import patch


def test_chat_returns_401_for_invalid_token(client, auth_headers):
    """Assert POST /api/chat returns 401 when api_client.get_me raises."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.side_effect = Exception("401 Unauthorized")
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 401


def test_chat_returns_403_for_non_premium(client, auth_headers):
    """Assert POST /api/chat returns 403 for non-premium, non-admin user."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.return_value = {
            "is_premium": False,
            "is_admin": False,
            "is_demo": False,
        }
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 403
    assert "Premium" in r.json()["detail"]


def test_chat_returns_403_for_demo_user(client, auth_headers):
    """Assert POST /api/chat returns 403 for demo account."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.return_value = {
            "is_premium": True,
            "is_admin": False,
            "is_demo": True,
        }
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 403


def test_chat_streams_for_premium_user(client, auth_headers):
    """Assert POST /api/chat returns 200 and streams SSE for premium user."""
    with patch("app.chat.routes.api_client") as mock_api, \
         patch("app.chat.routes.run_chat") as mock_run:
        mock_api.get_me.return_value = {
            "is_premium": True,
            "is_admin": False,
            "is_demo": False,
        }
        mock_run.return_value = iter(["Hello! ", "How can I help?"])
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_chat_streams_for_admin_user(client, auth_headers):
    """Assert POST /api/chat returns 200 for non-premium admin user."""
    with patch("app.chat.routes.api_client") as mock_api, \
         patch("app.chat.routes.run_chat") as mock_run:
        mock_api.get_me.return_value = {
            "is_premium": False,
            "is_admin": True,
            "is_demo": False,
        }
        mock_run.return_value = iter(["Sure thing!"])
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
    assert r.status_code == 200
```

- [ ] **Step 6: Run tests to verify they fail (routes not yet complete)**

```bash
cd services/chat && pytest tests/ -v
```

Expected: tests import successfully; some may pass if routes.py is correct.

- [ ] **Step 7: Fix any test failures, then re-run**

```bash
cd services/chat && pytest tests/ -v
```

Expected: all 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add services/chat/
git commit -m "feat(chat): add Dockerfile, requirements, tests"
```

---

## Phase 3: Frontend Service + Final Wiring

### Task 13: Frontend Service

**Files:**
- Create: `services/frontend/Dockerfile`
- Create: `services/frontend/nginx.conf`
- Create: `services/frontend/src/` (move from `app/static/`)

**Interfaces:**
- Produces: Nginx container serving static HTML and proxying `/api/*`

- [ ] **Step 1: Move static files**

```bash
cp -r app/static/. services/frontend/src/
```

- [ ] **Step 2: Create services/frontend/nginx.conf**

The `/api/chat` location must appear before `/api/` because Nginx uses
longest-prefix matching — `/api/chat` needs to route to the chat service,
not the core API:

```nginx
server {
    listen 80;

    location /static/ {
        root /usr/share/nginx/html;
        expires 1h;
        add_header Cache-Control "public";
    }

    location /api/chat {
        proxy_pass         http://chat:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }

    location /api/ {
        proxy_pass         http://api:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
    }

    location = / {
        try_files /static/dashboard.html =404;
    }

    location = /workouts {
        try_files /static/workouts.html =404;
    }

    location = /import {
        try_files /static/import.html =404;
    }

    location = /exercises {
        try_files /static/exercises.html =404;
    }

    location = /routines {
        try_files /static/routines.html =404;
    }

    location = /register {
        try_files /static/register.html =404;
    }

    location = /login {
        try_files /static/login.html =404;
    }

    location = /chat {
        try_files /static/chat.html =404;
    }

    location ~ ^/workout/[0-9]+$ {
        try_files /static/workout.html =404;
    }

    location ~ ^/exercise/[0-9]+$ {
        try_files /static/exercise.html =404;
    }

    location ~ ^/routine/[0-9]+$ {
        try_files /static/routine.html =404;
    }
}
```

Verify the listed HTML pages match every file in `services/frontend/src/`.
Add any missing `location =` blocks.

- [ ] **Step 3: Create services/frontend/Dockerfile**

```dockerfile
FROM nginx:alpine
COPY src/ /usr/share/nginx/html/static/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 4: Commit**

```bash
git add services/frontend/
git commit -m "feat(frontend): add Nginx service with src/, nginx.conf, Dockerfile"
```

---

### Task 14: Docker Compose + Makefile

**Files:**
- Modify: `docker-compose.yml` (root)
- Modify: `Makefile` (root)

**Interfaces:**
- Produces: `docker compose up --build` starts all three services;
  `make test` runs both service test suites

- [ ] **Step 1: Rewrite docker-compose.yml**

```yaml
services:
  frontend:
    build: services/frontend
    ports:
      - "8000:80"
    depends_on:
      - api
      - chat

  api:
    build: services/api
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    environment:
      - ALLOWED_ORIGINS=http://localhost:8000

  chat:
    build: services/chat
    env_file:
      - .env
    environment:
      - API_BASE_URL=http://api:8000
    depends_on:
      - api
```

- [ ] **Step 2: Update .env.example**

Add `API_BASE_URL` for chat service documentation:

```
DATABASE_URL=sqlite:////app/data/gymlog.db
SIGNUP_CODE=yoursignupcodehere
JWT_SECRET=some-long-random-string
ENVIRONMENT=development
GOOGLE_API_KEY=enter-api-key
ALLOWED_ORIGINS=http://localhost:8000
API_BASE_URL=http://api:8000
```

- [ ] **Step 3: Update Makefile**

```makefile
.PHONY: test up down build

test:
	cd services/api  && pytest tests/ -v
	cd services/chat && pytest tests/ -v

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example Makefile
git commit -m "feat: update docker-compose for three-service architecture"
```

---

### Task 15: Delete Old Files + End-to-End Smoke Test

**Files:**
- Delete: `app/api/` directory
- Delete: `app/services/` directory
- Delete: `app/model/` directory
- Delete: `app/db/` directory
- Delete: `app/static/` directory
- Delete: `app/context/` directory
- Delete: `app/main.py`, `app/admin.py`, `app/__init__.py`
- Delete: `app/` directory
- Delete: root `tests/` directory
- Delete: root `nginx.conf` (replaced by `services/frontend/nginx.conf`)
- Delete: root `Dockerfile.frontend`
- Delete: root `Dockerfile` (old monolith Dockerfile)
- Delete: root `requirements.txt`
- Delete: root `pytest.ini`

**Interfaces:**
- Produces: clean monorepo with no legacy files; `docker compose up --build`
  works end-to-end

- [ ] **Step 1: Verify services/api tests still pass**

```bash
cd services/api && pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify services/chat tests still pass**

```bash
cd services/chat && pytest tests/ -v
```

Expected: all 5 tests pass.

- [ ] **Step 3: Delete legacy app/ directory and root-level files**

```bash
rm -rf app/ tests/
rm -f nginx.conf Dockerfile.frontend Dockerfile requirements.txt pytest.ini
```

- [ ] **Step 4: Run make test to confirm both suites still pass**

```bash
make test
```

Expected: all API and chat tests pass.

- [ ] **Step 5: Build all Docker images**

```bash
docker compose build
```

Expected: all three images build successfully.

- [ ] **Step 6: Start stack and smoke test**

```bash
docker compose up -d
curl http://localhost:8000/           # should return dashboard.html
curl http://localhost:8000/workouts   # should return workouts.html
curl http://localhost:8000/api/auth/demo  # should return {"access_token": ...}
```

Expected: all three return expected responses.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: delete legacy monolith files after monorepo restructure"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `services/api/` with domain modules: auth, workouts, exercises, routines, db — Tasks 2–7
- [x] `services/chat/` with HTTP tools calling core API — Tasks 9–12
- [x] `services/frontend/` with Nginx + React-ready structure — Task 13
- [x] `/api/chat` → chat service, `/api/*` → api service in nginx.conf — Task 13
- [x] docker-compose with three services, only frontend exposed — Task 14
- [x] Each service has its own tests — Tasks 8, 12
- [x] `GET /api/auth/me` added for chat service premium check — Task 3
- [x] Import path change table from spec covered in Tasks 3–6

**Key departures from spec:**
- `api_client.py` uses sync `httpx.Client` instead of `AsyncClient` —
  chosen to avoid async refactor of the entire chat service's generator loop.
  Can be migrated to async in a future iteration.
- `_build_dynamic_context` no longer reports top 5 exercises (would require
  N+1 HTTP calls). Reports total count, last date, and routine names.
