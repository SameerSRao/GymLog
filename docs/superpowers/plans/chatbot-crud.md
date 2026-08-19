# Chatbot Full CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `app/services/chat_tools.py` into a domain-split package and add 8 new tools covering delete/update for workouts and full CRUD for exercises and routines.

**Architecture:** The existing single file becomes a Python package (`app/services/chat_tools/`). Each domain file owns its `FunctionDeclaration` list and handler function. `__init__.py` aggregates them into `TOOLS` and routes `execute_tool()` calls by name. Shared helpers live in `base.py`. The import in `chat_service.py` is unchanged.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, google-genai (Gemini), Pydantic v2, pytest.

## Global Constraints

- All Python follows PEP 8: max 79-char lines, snake_case, two blank lines between top-level defs.
- Every function/method/class must have a PEP 257 docstring (imperative mood, one line if it fits).
- Run tests with: `JWT_SECRET=testsecret123 SIGNUP_CODE=testcode .venv/bin/pytest -q`
- Do not add new HTTP routes — all new functionality goes through the chatbot tool layer only.
- All tool handler functions return a JSON **string** (via `json.dumps`). On success: `{"success": True, ...}`. On failure: `{"error": "..."}`.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Delete | `app/services/chat_tools.py` | Old single file — replaced by package |
| Create | `app/services/chat_tools/__init__.py` | Aggregates TOOLS; routes execute_tool() |
| Create | `app/services/chat_tools/base.py` | Shared helpers: exercise fuzzy match, routine resolver, muscle group resolver |
| Create | `app/services/chat_tools/workouts.py` | get_recent_workouts, log_workout, delete_workout, update_workout |
| Create | `app/services/chat_tools/exercises.py` | search_exercises, get_exercise_progression, create_exercise, update_exercise, delete_exercise |
| Create | `app/services/chat_tools/routines.py` | get_routines, create_routine, update_routine, delete_routine |
| Unchanged | `app/services/chat_service.py` | No changes needed |
| Unchanged | `tests/test_chat.py` | No new tests needed |

---

### Task 1: Package scaffold — migrate existing tools, delete old file

**Files:**
- Delete: `app/services/chat_tools.py`
- Create: `app/services/chat_tools/__init__.py`
- Create: `app/services/chat_tools/base.py`
- Create: `app/services/chat_tools/workouts.py` (existing 2 workout tools only)
- Create: `app/services/chat_tools/exercises.py` (existing 2 exercise tools only)
- Create: `app/services/chat_tools/routines.py` (existing 1 routine tool only)

**Interfaces:**
- Produces: `TOOLS: types.Tool`, `execute_tool(name: str, inputs: dict, db: Session, user_id: int) -> str` — same signatures as before, imported from `app.services.chat_tools`

- [ ] **Step 1: Create `app/services/chat_tools/base.py`**

```python
from sqlalchemy.orm import Session, joinedload

from app.model.models import ExerciseDef, MuscleGroup, Routine


def _all_exercises_with_muscles(db: Session) -> list[ExerciseDef]:
    """Return all exercises with muscle groups eager-loaded."""
    return (
        db.query(ExerciseDef)
        .options(joinedload(ExerciseDef.muscle_groups))
        .order_by(ExerciseDef.name)
        .all()
    )


def _best_exercise_match(
    query_words: list[str], exercises: list[ExerciseDef]
) -> ExerciseDef | None:
    """Return the best word-level match, falling back to substring match."""
    q_set = set(query_words)
    word_matches = [
        e for e in exercises
        if q_set.issubset(set(e.name.lower().split()))
    ]
    if word_matches:
        return word_matches[0]
    query_str = " ".join(query_words)
    sub_matches = [e for e in exercises if query_str in e.name.lower()]
    return sub_matches[0] if sub_matches else None


def _resolve_routine(
    name: str, db: Session, user_id: int
) -> Routine | dict:
    """Return matching Routine (with exercises loaded) or an error dict.

    Returns an error dict if zero or multiple routines match the name.
    """
    q = name.lower()
    routines = (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .filter(Routine.user_id == user_id)
        .all()
    )
    matches = [r for r in routines if q in r.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {
            "error": (
                f"Multiple routines match '{name}': "
                f"{[r.name for r in matches]}. Be more specific."
            )
        }
    names = [r.name for r in routines]
    return {
        "error": (
            f"No routine found matching '{name}'. "
            f"Your routines: {names}"
        )
    }


def _resolve_muscle_groups(
    names: list[str], db: Session
) -> tuple[list[int], list[str]]:
    """Resolve muscle group name strings to IDs.

    Returns (matched_ids, unresolved_names).
    """
    all_mgs = db.query(MuscleGroup).all()
    matched_ids: list[int] = []
    unresolved: list[str] = []
    for name in names:
        q = name.lower()
        match = next(
            (mg for mg in all_mgs if q in mg.name.lower()), None
        )
        if match:
            matched_ids.append(match.id)
        else:
            unresolved.append(name)
    return matched_ids, unresolved
```

- [ ] **Step 2: Create `app/services/chat_tools/workouts.py`** (existing tools only — new ones added in Task 2)

```python
import json
from datetime import datetime, timedelta, timezone

from google.genai import types
from sqlalchemy.orm import Session

from app.api.schemas import ExerciseLogRequest, SetSchema, WorkoutRequest
from app.model.models import ExerciseDef
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
)
from app.services.workout_service import (
    get_all_workouts,
    log_workout as _log_workout,
)

WORKOUT_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_recent_workouts",
        description="Get the user's recent workout sessions.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "days": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of days to look back",
                )
            },
            required=["days"],
        ),
    ),
    types.FunctionDeclaration(
        name="log_workout",
        description=(
            "Log a new workout session. Only call after the user has"
            " explicitly confirmed the exercise list, sets, reps,"
            " and weights."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "reps": types.Schema(
                                            type=types.Type.INTEGER
                                        ),
                                        "weight_lbs": types.Schema(
                                            type=types.Type.NUMBER,
                                            description=(
                                                "Weight in lbs;"
                                                " omit for bodyweight"
                                            ),
                                        ),
                                    },
                                    required=["reps"],
                                ),
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
                "notes": types.Schema(
                    type=types.Type.STRING,
                    description="Optional notes for the workout",
                ),
            },
            required=["exercises"],
        ),
    ),
]


def _resolve_exercise_inputs(
    exercise_inputs: list[dict],
    ex_by_name: dict[str, ExerciseDef],
    all_ex: list[ExerciseDef],
) -> tuple[list[ExerciseLogRequest], list[str]]:
    """Resolve exercise name dicts to ExerciseLogRequests.

    Returns (requests, not_found_names).
    """
    logged: list[ExerciseLogRequest] = []
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
            SetSchema(reps=s["reps"], weight_lbs=s.get("weight_lbs"))
            for s in ex["sets"]
        ]
        logged.append(ExerciseLogRequest(exercise_id=match.id, sets=sets))
    return logged, not_found


def handle_workout_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a workout tool call; return result as a JSON string."""
    if name == "get_recent_workouts":
        days = inputs.get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        workouts = get_all_workouts(db, user_id)
        recent = []
        for w in workouts:
            logged = w.logged_at
            if logged.tzinfo is None:
                logged = logged.replace(tzinfo=timezone.utc)
            if logged < cutoff:
                continue
            exercises_done = list({s.exercise_def.name for s in w.sets})
            recent.append({
                "session_id": w.id,
                "date": w.logged_at.strftime("%Y-%m-%d"),
                "exercises": exercises_done,
                "total_sets": len(w.sets),
            })
        return json.dumps({"workouts": recent, "count": len(recent)})

    if name == "log_workout":
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}
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
        req = WorkoutRequest(
            exercises=logged, notes=inputs.get("notes")
        )
        session = _log_workout(db, req, user_id)
        return json.dumps({
            "success": True,
            "session_id": session.id,
            "logged_at": session.logged_at.isoformat(),
            "exercises_logged": len(logged),
        })

    return json.dumps({"error": f"Unknown workout tool: {name}"})
```

- [ ] **Step 3: Create `app/services/chat_tools/exercises.py`** (existing tools only)

```python
import json

from google.genai import types
from sqlalchemy.orm import Session

from app.services.chat_tools.base import _all_exercises_with_muscles
from app.services.exercise_service import get_exercise_progression

EXERCISE_DECLARATIONS = [
    types.FunctionDeclaration(
        name="search_exercises",
        description=(
            "Search exercises by name or muscle group keyword."
            " Returns matching exercise names, IDs, equipment,"
            " and muscle groups."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Search term — a muscle group (e.g. 'chest',"
                        " 'back') or exercise name (e.g. 'bench press')"
                    ),
                )
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_exercise_progression",
        description=(
            "Get progression history (sets, volume, best weight)"
            " for a specific exercise. Prefers exercises the user"
            " has actually logged."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(
                    type=types.Type.STRING,
                    description="Name of the exercise",
                )
            },
            required=["exercise_name"],
        ),
    ),
]


def handle_exercise_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch an exercise tool call; return result as a JSON string."""
    if name == "search_exercises":
        query = inputs["query"].lower()
        exercises = _all_exercises_with_muscles(db)
        matches = [
            {
                "id": e.id,
                "name": e.name,
                "equipment": e.equipment,
                "muscle_groups": [mg.name for mg in e.muscle_groups],
            }
            for e in exercises
            if query in e.name.lower()
            or any(query in mg.name.lower() for mg in e.muscle_groups)
        ][:20]
        return json.dumps({"matches": matches, "count": len(matches)})

    if name == "get_exercise_progression":
        raw_name = inputs["exercise_name"]
        query_words = raw_name.lower().split()
        exercises = _all_exercises_with_muscles(db)
        q_set = set(query_words)
        candidates = [
            e for e in exercises
            if q_set.issubset(set(e.name.lower().split()))
        ]
        if not candidates:
            candidates = [
                e for e in exercises
                if " ".join(query_words) in e.name.lower()
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
            _, sessions = get_exercise_progression(
                db, candidate.id, user_id
            )
            if len(sessions) > len(best_sessions):
                best = candidate
                best_sessions = sessions
        if not best or not best_sessions:
            names = ", ".join(c.name for c in candidates[:5])
            return json.dumps({
                "error": (
                    f"No logged data found for '{raw_name}'."
                    f" Matching exercises: {names}."
                    " Have you logged any of these?"
                )
            })
        return json.dumps({
            "exercise": best.name,
            "sessions": [
                {
                    "date": s["logged_at"].strftime("%Y-%m-%d"),
                    "sets": s["sets"],
                    "volume": s["volume"],
                    "best_set_weight": s["best_set_weight"],
                }
                for s in best_sessions[-10:]
            ],
        })

    return json.dumps({"error": f"Unknown exercise tool: {name}"})
```

- [ ] **Step 4: Create `app/services/chat_tools/routines.py`** (existing tool only)

```python
import json

from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.model.models import Routine, RoutineExercise

ROUTINE_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_routines",
        description=(
            "List all saved workout routines with their exercises."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
]


def handle_routine_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a routine tool call; return result as a JSON string."""
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
        result = [
            {
                "id": r.id,
                "name": r.name,
                "exercises": [
                    {
                        "position": ex.position,
                        "name": ex.exercise_def.name,
                        "sets": ex.num_sets,
                    }
                    for ex in sorted(
                        r.exercises, key=lambda x: x.position
                    )
                ],
            }
            for r in routines
        ]
        return json.dumps({"routines": result, "count": len(result)})

    return json.dumps({"error": f"Unknown routine tool: {name}"})
```

- [ ] **Step 5: Create `app/services/chat_tools/__init__.py`**

```python
import json

from google.genai import types
from sqlalchemy.orm import Session

from app.services.chat_tools.exercises import (
    EXERCISE_DECLARATIONS,
    handle_exercise_tool,
)
from app.services.chat_tools.routines import (
    ROUTINE_DECLARATIONS,
    handle_routine_tool,
)
from app.services.chat_tools.workouts import (
    WORKOUT_DECLARATIONS,
    handle_workout_tool,
)

TOOLS = types.Tool(
    function_declarations=(
        WORKOUT_DECLARATIONS + EXERCISE_DECLARATIONS + ROUTINE_DECLARATIONS
    )
)

_WORKOUT_NAMES = {d.name for d in WORKOUT_DECLARATIONS}
_EXERCISE_NAMES = {d.name for d in EXERCISE_DECLARATIONS}
_ROUTINE_NAMES = {d.name for d in ROUTINE_DECLARATIONS}


def execute_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a tool call by name for user_id; return result as JSON."""
    if name in _WORKOUT_NAMES:
        return handle_workout_tool(name, inputs, db, user_id)
    if name in _EXERCISE_NAMES:
        return handle_exercise_tool(name, inputs, db, user_id)
    if name in _ROUTINE_NAMES:
        return handle_routine_tool(name, inputs, db, user_id)
    return json.dumps({"error": f"Unknown tool: {name}"})
```

- [ ] **Step 6: Delete the old file**

```bash
rm app/services/chat_tools.py
```

- [ ] **Step 7: Run tests to verify nothing broke**

```bash
JWT_SECRET=testsecret123 SIGNUP_CODE=testcode .venv/bin/pytest -q
```

Expected: all 107 tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/services/chat_tools/ && git rm app/services/chat_tools.py
git commit -m "refactor: convert chat_tools to domain-split package"
```

---

### Task 2: Workout delete + update tools

**Files:**
- Modify: `app/services/chat_tools/workouts.py`

**Interfaces:**
- Consumes: `workout_service.delete_workout(db, session_id, user_id) -> bool`, `workout_service.update_workout(db, session_id, workout, user_id) -> Workout | None`, `_resolve_exercise_inputs` (defined in Task 1 workouts.py)
- Produces: tools `delete_workout` and `update_workout` available via `execute_tool`

- [ ] **Step 1: Add imports to `workouts.py`**

Add to the existing imports at the top of `app/services/chat_tools/workouts.py`:

```python
from app.services.workout_service import (
    get_all_workouts,
    log_workout as _log_workout,
    delete_workout as _delete_workout,      # add this
    update_workout as _update_workout,      # add this
)
```

- [ ] **Step 2: Add declarations to `WORKOUT_DECLARATIONS`**

Append to the `WORKOUT_DECLARATIONS` list in `workouts.py`:

```python
    types.FunctionDeclaration(
        name="delete_workout",
        description=(
            "Delete a workout session by session_id. Call"
            " get_recent_workouts first to find the correct session_id."
            " Only call after the user has explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "session_id": types.Schema(
                    type=types.Type.INTEGER,
                    description="The session ID to delete",
                ),
            },
            required=["session_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_workout",
        description=(
            "Replace all exercises and sets in an existing workout"
            " session in-place. Call get_recent_workouts first to find"
            " the session_id. Only call after the user has explicitly"
            " confirmed the full updated exercise list."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "session_id": types.Schema(
                    type=types.Type.INTEGER,
                    description="The session ID to update",
                ),
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "reps": types.Schema(
                                            type=types.Type.INTEGER
                                        ),
                                        "weight_lbs": types.Schema(
                                            type=types.Type.NUMBER,
                                            description=(
                                                "Weight in lbs;"
                                                " omit for bodyweight"
                                            ),
                                        ),
                                    },
                                    required=["reps"],
                                ),
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
                "notes": types.Schema(type=types.Type.STRING),
            },
            required=["session_id", "exercises"],
        ),
    ),
```

- [ ] **Step 3: Add handlers in `handle_workout_tool`**

Replace the final `return json.dumps({"error": ...})` line in `handle_workout_tool` with:

```python
    if name == "delete_workout":
        session_id = inputs["session_id"]
        found = _delete_workout(db, session_id, user_id)
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
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}
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
        req = WorkoutRequest(
            exercises=logged, notes=inputs.get("notes")
        )
        session = _update_workout(db, session_id, req, user_id)
        if not session:
            return json.dumps({
                "error": f"Workout session {session_id} not found."
            })
        return json.dumps({
            "success": True,
            "session_id": session.id,
            "exercises_updated": len(logged),
        })

    return json.dumps({"error": f"Unknown workout tool: {name}"})
```

- [ ] **Step 4: Run tests**

```bash
JWT_SECRET=testsecret123 SIGNUP_CODE=testcode .venv/bin/pytest -q
```

Expected: all 107 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/chat_tools/workouts.py
git commit -m "feat: add delete_workout and update_workout chat tools"
```

---

### Task 3: Exercise create, update, delete tools

**Files:**
- Modify: `app/services/chat_tools/exercises.py`

**Interfaces:**
- Consumes: `_resolve_muscle_groups(names, db) -> (list[int], list[str])` from `base.py`; `_best_exercise_match` from `base.py`; `exercise_service.create_exercise(db, data, user_id)`, `exercise_service.update_exercise(db, id, data, user_id, is_admin)`, `exercise_service.delete_exercise(db, id, user_id, is_admin)`; `CreateExerciseSchema`, `ExerciseUpdate` from `app.api.schemas`
- Produces: tools `create_exercise`, `update_exercise`, `delete_exercise` available via `execute_tool`

- [ ] **Step 1: Add imports to `exercises.py`**

Replace the imports block at the top of `exercises.py` with:

```python
import json

from google.genai import types
from sqlalchemy.orm import Session

from app.api.schemas import CreateExerciseSchema, ExerciseUpdate
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
    _resolve_muscle_groups,
)
from app.services.exercise_service import (
    create_exercise as _create_exercise,
    delete_exercise as _delete_exercise,
    get_exercise_progression,
    update_exercise as _update_exercise,
)
```

- [ ] **Step 2: Append declarations to `EXERCISE_DECLARATIONS`**

```python
    types.FunctionDeclaration(
        name="create_exercise",
        description=(
            "Create a custom exercise for the user. Only call after"
            " the user has confirmed the name, equipment, and muscle"
            " groups."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING),
                "equipment": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Equipment type (e.g. 'barbell', 'dumbbell');"
                        " omit if bodyweight"
                    ),
                ),
                "muscle_group_names": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description=(
                        "Muscle group names (e.g. ['chest', 'triceps'])"
                    ),
                ),
            },
            required=["name", "muscle_group_names"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_exercise",
        description=(
            "Edit a custom exercise the user owns. Only call after the"
            " user has confirmed the changes."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(
                    type=types.Type.STRING,
                    description="Current name of the exercise to edit",
                ),
                "new_name": types.Schema(type=types.Type.STRING),
                "equipment": types.Schema(type=types.Type.STRING),
                "muscle_group_names": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
            },
            required=["exercise_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_exercise",
        description=(
            "Delete a custom exercise the user owns. Only call after"
            " the user has explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(type=types.Type.STRING),
            },
            required=["exercise_name"],
        ),
    ),
```

- [ ] **Step 3: Add handlers in `handle_exercise_tool`**

Replace the final `return json.dumps({"error": ...})` line with:

```python
    if name == "create_exercise":
        mg_names = inputs.get("muscle_group_names", [])
        mg_ids, unresolved = _resolve_muscle_groups(mg_names, db)
        if unresolved:
            return json.dumps({
                "error": (
                    f"Unknown muscle groups: {unresolved}."
                    " Try search_exercises to find valid muscle group"
                    " names."
                )
            })
        data = CreateExerciseSchema(
            name=inputs["name"],
            equipment=inputs.get("equipment"),
            instructions=None,
            muscle_group_ids=mg_ids,
        )
        ex = _create_exercise(db, data, user_id)
        return json.dumps({
            "success": True,
            "exercise_id": ex.id,
            "name": ex.name,
        })

    if name == "update_exercise":
        raw_name = inputs["exercise_name"]
        exercises = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in exercises}
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
                inputs["muscle_group_names"], db
            )
            if unresolved:
                return json.dumps({
                    "error": f"Unknown muscle groups: {unresolved}."
                })
        data = ExerciseUpdate(
            name=inputs.get("new_name"),
            equipment=inputs.get("equipment"),
            muscle_group_ids=mg_ids,
        )
        try:
            updated = _update_exercise(
                db, match.id, data, user_id=user_id, is_admin=False
            )
        except ValueError as e:
            if str(e) == "forbidden":
                return json.dumps({
                    "error": (
                        f"You don't have permission to edit"
                        f" '{match.name}'. You can only edit exercises"
                        " you created."
                    )
                })
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"An exercise named '{inputs.get('new_name')}'"
                        " already exists."
                    )
                })
            raise
        if not updated:
            return json.dumps({"error": "Exercise not found."})
        return json.dumps({
            "success": True,
            "exercise_id": updated.id,
            "name": updated.name,
        })

    if name == "delete_exercise":
        raw_name = inputs["exercise_name"]
        exercises = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in exercises}
        match = ex_by_name.get(raw_name.lower()) or _best_exercise_match(
            raw_name.lower().split(), exercises
        )
        if not match:
            return json.dumps({
                "error": f"No exercise found matching '{raw_name}'."
            })
        try:
            found = _delete_exercise(
                db, match.id, user_id=user_id, is_admin=False
            )
        except ValueError as e:
            if str(e) == "forbidden":
                return json.dumps({
                    "error": (
                        f"You don't have permission to delete"
                        f" '{match.name}'. You can only delete exercises"
                        " you created."
                    )
                })
            if str(e) == "has_history":
                return json.dumps({
                    "error": (
                        f"'{match.name}' has logged workout history"
                        " and cannot be deleted."
                    )
                })
            raise
        if not found:
            return json.dumps({"error": "Exercise not found."})
        return json.dumps({"success": True, "deleted": match.name})

    return json.dumps({"error": f"Unknown exercise tool: {name}"})
```

- [ ] **Step 4: Run tests**

```bash
JWT_SECRET=testsecret123 SIGNUP_CODE=testcode .venv/bin/pytest -q
```

Expected: all 107 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/chat_tools/exercises.py
git commit -m "feat: add create/update/delete exercise chat tools"
```

---

### Task 4: Routine create, update, delete tools

**Files:**
- Modify: `app/services/chat_tools/routines.py`

**Interfaces:**
- Consumes: `_resolve_routine(name, db, user_id) -> Routine | dict` from `base.py`; `_all_exercises_with_muscles`, `_best_exercise_match` from `base.py`; `routine_service.create_routine(db, data, user_id)`, `routine_service.update_routine(db, id, data, user_id)`, `routine_service.delete_routine(db, id, user_id)`; `RoutineCreate`, `RoutineUpdate`, `RoutineExerciseRequest` from `app.api.schemas`
- Produces: tools `create_routine`, `update_routine`, `delete_routine` available via `execute_tool`

- [ ] **Step 1: Replace imports in `routines.py`**

```python
import json

from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import RoutineCreate, RoutineExerciseRequest, RoutineUpdate
from app.model.models import Routine, RoutineExercise
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
    _resolve_routine,
)
from app.services.routine_service import (
    create_routine as _create_routine,
    delete_routine as _delete_routine,
    update_routine as _update_routine,
)
```

- [ ] **Step 2: Add a module-level helper**

Add this function after the imports, before `ROUTINE_DECLARATIONS`:

```python
def _resolve_routine_exercises(
    exercise_inputs: list[dict],
    ex_by_name: dict,
    all_ex: list,
) -> tuple[list[RoutineExerciseRequest], list[str]]:
    """Resolve exercise name dicts to RoutineExerciseRequests.

    Returns (requests, not_found_names).
    """
    requests: list[RoutineExerciseRequest] = []
    not_found: list[str] = []
    for i, ex in enumerate(exercise_inputs):
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        requests.append(
            RoutineExerciseRequest(
                exercise_id=match.id,
                position=i + 1,
                num_sets=ex["sets"],
            )
        )
    return requests, not_found
```

- [ ] **Step 3: Append declarations to `ROUTINE_DECLARATIONS`**

```python
    types.FunctionDeclaration(
        name="create_routine",
        description=(
            "Create a new workout routine. Only call after the user"
            " has confirmed the name and exercise list."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING,
                    description="Name for the new routine",
                ),
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(
                                type=types.Type.INTEGER,
                                description="Default number of sets",
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
            },
            required=["name", "exercises"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_routine",
        description=(
            "Replace a routine's name and/or exercise list. Only call"
            " after the user has confirmed the full updated routine."
            " Omit 'exercises' to keep the current list unchanged."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "routine_name": types.Schema(
                    type=types.Type.STRING,
                    description="Current name of the routine to update",
                ),
                "new_name": types.Schema(
                    type=types.Type.STRING,
                    description="New name; omit to keep the current name",
                ),
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(type=types.Type.INTEGER),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
            },
            required=["routine_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_routine",
        description=(
            "Delete a routine by name. Only call after the user has"
            " explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "routine_name": types.Schema(type=types.Type.STRING),
            },
            required=["routine_name"],
        ),
    ),
```

- [ ] **Step 4: Add handlers in `handle_routine_tool`**

Replace the final `return json.dumps({"error": ...})` line with:

```python
    if name == "create_routine":
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}
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
        data = RoutineCreate(
            name=inputs["name"], exercises=exercise_reqs
        )
        try:
            routine = _create_routine(db, data, user_id)
        except ValueError as e:
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"You already have a routine named"
                        f" '{inputs['name']}'."
                    )
                })
            raise
        return json.dumps({
            "success": True,
            "routine_id": routine.id,
            "name": routine.name,
            "exercises": len(exercise_reqs),
        })

    if name == "update_routine":
        routine_or_err = _resolve_routine(
            inputs["routine_name"], db, user_id
        )
        if isinstance(routine_or_err, dict):
            return json.dumps(routine_or_err)
        routine = routine_or_err
        new_name = inputs.get("new_name") or routine.name
        if inputs.get("exercises"):
            all_ex = _all_exercises_with_muscles(db)
            ex_by_name = {e.name.lower(): e for e in all_ex}
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
                RoutineExerciseRequest(
                    exercise_id=ex.exercise_id,
                    position=ex.position,
                    num_sets=ex.num_sets,
                )
                for ex in sorted(
                    routine.exercises, key=lambda x: x.position
                )
            ]
        data = RoutineUpdate(name=new_name, exercises=exercise_reqs)
        try:
            updated = _update_routine(db, routine.id, data, user_id)
        except ValueError as e:
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"You already have a routine named '{new_name}'."
                    )
                })
            raise
        if not updated:
            return json.dumps({"error": "Routine not found."})
        return json.dumps({
            "success": True,
            "routine_id": updated.id,
            "name": updated.name,
        })

    if name == "delete_routine":
        routine_or_err = _resolve_routine(
            inputs["routine_name"], db, user_id
        )
        if isinstance(routine_or_err, dict):
            return json.dumps(routine_or_err)
        routine = routine_or_err
        _delete_routine(db, routine.id, user_id)
        return json.dumps({"success": True, "deleted": routine.name})

    return json.dumps({"error": f"Unknown routine tool: {name}"})
```

- [ ] **Step 5: Run tests**

```bash
JWT_SECRET=testsecret123 SIGNUP_CODE=testcode .venv/bin/pytest -q
```

Expected: all 107 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/chat_tools/routines.py
git commit -m "feat: add create/update/delete routine chat tools"
```
