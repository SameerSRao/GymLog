# Design: Monorepo Restructure — Three-Service Architecture

Date: 2026-08-12

## Overview

Reorganize GymLog from a single FastAPI container serving everything into a
monorepo with three independently deployable services: `api`, `chat`, and
`frontend`. Within the API service, replace the current cross-cutting folder
layout (`api/`, `services/`, `model/`) with domain modules that co-locate
routes, service logic, and schemas by feature.

---

## Services

### `services/api/` — Core API

Handles auth, workouts, exercises, and routines. Owns the database. Exposes
`/api/*` routes (except `/api/chat`). Not exposed externally — only reachable
through the Nginx frontend proxy.

### `services/chat/` — Chat / LLM Service

Handles `POST /api/chat`. Calls the Gemini API and uses tools that fetch
workout/exercise/routine context from the core API over HTTP. Has no database
connection. Scales independently from the core API due to its different
resource profile (slow LLM calls vs fast DB queries) and isolated external
dependency (Google API key).

### `services/frontend/` — Nginx Frontend

Serves static HTML/JS assets. Proxies `/api/chat` to the chat service and all
other `/api/*` to the core API. Structured for a React migration: swapping
vanilla HTML for a React build requires only a Dockerfile change and an
nginx.conf simplification — no infrastructure changes.

---

## Top-Level Layout

```
GymLog/
├── services/
│   ├── api/
│   ├── chat/
│   └── frontend/
├── docker-compose.yml
├── .env.example
├── data/               ← SQLite volume (dev only, gitignored)
└── docs/
```

Root holds only orchestration and documentation. No application code lives
here.

---

## API Service Internal Structure

Domain modules replace the current cross-cutting layout. Each domain owns its
routes, service logic, and schemas.

```
services/api/
├── app/
│   ├── auth/
│   │   ├── routes.py       ← login, register, demo, get_current_user,
│   │   │                      require_not_demo
│   │   ├── service.py      ← hash_password, verify_password,
│   │   │                      create_access_token, get_user_by_username
│   │   └── schemas.py      ← LoginRequest, RegisterRequest, TokenResponse
│   ├── workouts/
│   │   ├── routes.py       ← CRUD + batch import endpoint
│   │   ├── service.py      ← log_workout, get_all_workouts, import_workouts,
│   │   │                      update_workout, delete_workout,
│   │   │                      build_workout_detailed
│   │   └── schemas.py      ← WorkoutRequest, WorkoutResponse, WorkoutDetailed,
│   │                          WorkoutImportRequest, ImportError, ImportResponse,
│   │                          ExerciseLogRequest, SetSchema, ExerciseSchema
│   ├── exercises/
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── schemas.py      ← ExerciseDefSchema, MuscleGroupSchema,
│   │                          CreateExerciseSchema, ExerciseUpdate,
│   │                          ExerciseProgressionSchema, SessionSummary,
│   │                          SetDetail
│   ├── routines/
│   │   ├── routes.py
│   │   ├── service.py
│   │   └── schemas.py      ← RoutineCreate, RoutineUpdate, RoutineDetail,
│   │                          RoutineListItem, RoutineExerciseRequest,
│   │                          RoutineExerciseDetail
│   ├── db/
│   │   ├── models.py       ← all ORM models (was app/model/models.py)
│   │   ├── database.py     ← engine, SessionLocal, get_db
│   │   └── seed.py         ← seed_exercises, seed_demo_data
│   └── main.py             ← wires routers, CORS middleware, startup seeding
├── tests/                  ← moves from root /tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_demo.py
│   ├── test_exercises.py
│   ├── test_import.py
│   ├── test_routines.py
│   ├── test_seed.py
│   └── test_workouts.py
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

**Cross-domain import rule:** `MuscleGroupSchema` is defined in
`exercises/schemas.py` (canonical owner). `workouts/schemas.py` imports it for
`WorkoutDetailed`. This is the only cross-domain schema import in the API.

**`auth/service.py` absorbs `user_service.py`:** `get_user_by_username` is
only called by auth routes, so it belongs there rather than as a standalone
module.

---

## Chat Service Internal Structure

```
services/chat/
├── app/
│   ├── chat/
│   │   ├── routes.py       ← POST /api/chat
│   │   ├── service.py      ← Gemini integration, tool dispatch
│   │   └── schemas.py      ← ChatRequest, ChatResponse
│   ├── tools/
│   │   ├── base.py         ← tool interface / registry
│   │   ├── workouts.py     ← calls api: GET /api/workouts, /api/workout/{id}
│   │   ├── exercises.py    ← calls api: GET /api/exercises
│   │   └── routines.py     ← calls api: GET /api/routines
│   ├── client/
│   │   └── api_client.py   ← httpx.AsyncClient; single source of API_BASE_URL
│   └── main.py
├── tests/
│   └── test_chat.py        ← mocks api_client, never hits real API or Gemini
├── Dockerfile
└── requirements.txt        ← fastapi, httpx, google-genai, python-jose, uvicorn
```

**Inter-service auth:** The frontend forwards the user's JWT to the chat
service unchanged. The chat service attaches it as an `Authorization` header
on every call to the core API. The core API validates it and scopes data to
the correct user. The chat service never touches the DB or JWT secret.

**`client/api_client.py`:** One `httpx.AsyncClient` instance configured with
`API_BASE_URL` (docker-compose env var: `http://api:8000`). All tools import
from this module — changing the API URL requires editing one file.

---

## Frontend Service Structure

```
services/frontend/
├── src/                    ← current vanilla HTML/JS
│   ├── auth.js
│   ├── dashboard.html
│   ├── workouts.html
│   └── ...
├── nginx.conf
└── Dockerfile
```

### React Migration Path

Only the Dockerfile and nginx.conf change — nothing else:

**Dockerfile (now):**
```dockerfile
FROM nginx:alpine
COPY src/ /usr/share/nginx/html/static/
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

**Dockerfile (React):**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY src/ ./src/
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

**nginx.conf (React):** Replace all per-route `location =` blocks with:
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

---

## Docker Compose Wiring

```yaml
services:
  frontend:
    build: services/frontend
    ports:
      - "8000:80"
    depends_on: [api, chat]

  api:
    build: services/api
    volumes:
      - ./data:/app/data
    env_file: .env

  chat:
    build: services/chat
    env_file: .env
    environment:
      - API_BASE_URL=http://api:8000
    depends_on: [api]
```

Only `frontend` exposes a port. `api` and `chat` are internal to the Docker
network. Nginx routes `/api/chat` to `http://chat:8000` and all other
`/api/*` to `http://api:8000`. The chat location block uses a 60s
`proxy_read_timeout` (LLM calls are slow); the API block uses 30s.

---

## nginx.conf Routing

```nginx
# Chat — matched first (more specific); longer timeout for LLM latency
location /api/chat {
    proxy_pass         http://chat:8000;
    proxy_read_timeout 60s;
}

# Core API
location /api/ {
    proxy_pass         http://api:8000;
    proxy_read_timeout 30s;
}

# Static assets — short cache
location /static/ {
    expires 1h;
    add_header Cache-Control "public";
}

# HTML page routes — no cache
location = / { try_files /static/dashboard.html =404; }
location = /workouts { ... }
# etc.

# Dynamic routes
location ~ ^/workout/\d+$ { try_files /static/workout.html =404; }
location ~ ^/exercise/\d+$ { try_files /static/exercise.html =404; }
```

---

## Testing Strategy

Each service tests itself independently. No shared test runner at the root.

**API tests:** Unchanged — `TestClient` + in-memory SQLite, existing fixtures
in `conftest.py`. `pytest.ini` moves into `services/api/`.

**Chat tests:** Mock `api_client.py` to avoid real HTTP or Gemini calls:
```python
@pytest.fixture(autouse=True)
def mock_api_client(monkeypatch):
    async def fake_get_workouts(token): return [...]
    monkeypatch.setattr("app.tools.workouts.get_workouts", fake_get_workouts)
```

**Running per service:**
```bash
cd services/api  && pytest tests/ -v
cd services/chat && pytest tests/ -v
```

**Root Makefile for convenience:**
```makefile
test:
    cd services/api  && pytest tests/ -v
    cd services/chat && pytest tests/ -v
```

---

## Import Path Changes (API service)

| Old | New |
|-----|-----|
| `app.api.auth_routes` | `app.auth.routes` |
| `app.api.workout_routes` | `app.workouts.routes` |
| `app.api.exercise_routes` | `app.exercises.routes` |
| `app.api.routine_routes` | `app.routines.routes` |
| `app.api.schemas` | domain-specific schemas module |
| `app.services.auth_service` | `app.auth.service` |
| `app.services.workout_service` | `app.workouts.service` |
| `app.services.exercise_service` | `app.exercises.service` |
| `app.services.routine_service` | `app.routines.service` |
| `app.services.user_service` | `app.auth.service` |
| `app.services.chat_service` | `app.chat.service` (chat repo) |
| `app.services.chat_tools` | `app.tools` (chat repo) |
| `app.model.models` | `app.db.models` |

---

## Out of Scope

- Redis caching layer
- PgBouncer connection pooling
- Celery async task queue
- Analytics / reporting service
- Kubernetes / ECS deployment manifests
- CI/CD pipeline configuration
