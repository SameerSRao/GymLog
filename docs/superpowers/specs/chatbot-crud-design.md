# Chatbot Full CRUD Design

## Goal

Expand the AI chatbot from read-heavy + log-only to full CRUD across workouts, user-created exercises, and routines — 8 new tools on top of the existing 5.

## Architecture

`app/services/chat_tools.py` is converted into a Python package. Each domain owns its tool declarations and handler functions. A shared `base.py` holds fuzzy-matching helpers used across domains. `__init__.py` aggregates everything so the import in `chat_service.py` (`from app.services.chat_tools import TOOLS, execute_tool`) is unchanged.

## File Structure

```
app/services/chat_tools/
├── __init__.py      # aggregates TOOLS list; routes execute_tool() to domain handlers
├── base.py          # _all_exercises_with_muscles, _best_exercise_match,
│                    # _resolve_routine, _resolve_muscle_groups
├── workouts.py      # get_recent_workouts, log_workout, delete_workout, update_workout
├── exercises.py     # search_exercises, get_exercise_progression,
│                    # create_exercise, update_exercise, delete_exercise
└── routines.py      # get_routines, create_routine, update_routine, delete_routine
```

The old `app/services/chat_tools.py` is deleted.

## Tool Inventory

### workouts.py — 4 tools

| Tool | Type | Description |
|---|---|---|
| `get_recent_workouts(days)` | read | List recent sessions with exercises and set detail |
| `log_workout(exercises, notes?)` | create | Log a new session (existing) |
| `delete_workout(session_id)` | delete | Delete a session by ID |
| `update_workout(session_id, exercises, notes?)` | update | Replace all sets in a session in-place |

`delete_workout` and `update_workout` descriptions: *"Only call after the user has explicitly confirmed the session ID and the action."* Bot surfaces session IDs via `get_recent_workouts` first.

### exercises.py — 5 tools

| Tool | Type | Description |
|---|---|---|
| `search_exercises(query)` | read | Search by name or muscle group (existing) |
| `get_exercise_progression(exercise_name)` | read | Progression history (existing) |
| `create_exercise(name, equipment?, muscle_group_names[])` | create | Create a custom exercise owned by the caller |
| `update_exercise(exercise_name, new_name?, equipment?, muscle_group_names[])` | update | Edit own custom exercise |
| `delete_exercise(exercise_name)` | delete | Delete own custom exercise |

`create_exercise`, `update_exercise`, `delete_exercise` descriptions include explicit confirmation guard. Muscle groups resolved by case-insensitive substring against the `muscle_groups` table; unresolved names returned as `{"unresolved": [...]}` so the bot can ask the user to clarify.

### routines.py — 4 tools

| Tool | Type | Description |
|---|---|---|
| `get_routines()` | read | List all routines with exercises (existing) |
| `create_routine(name, exercises[{exercise_name, sets}])` | create | Create a new routine |
| `update_routine(routine_name, new_name?, exercises?)` | update | Replace routine name and/or exercise list |
| `delete_routine(routine_name)` | delete | Delete a routine |

Routines resolved by case-insensitive substring match against the caller's routines. If multiple routines match, return all candidates and ask the user to clarify. Confirmation guard on all mutating tools.

### base.py — shared helpers (no tools)

| Helper | Used by |
|---|---|
| `_all_exercises_with_muscles(db)` | workouts.py, exercises.py |
| `_best_exercise_match(words, exercises)` | workouts.py, exercises.py |
| `_resolve_routine(name, db, user_id) -> Routine or error dict` | routines.py |
| `_resolve_muscle_groups(names, db) -> (matched_ids, unresolved_names)` | exercises.py |

## Resolution Rules

**Exercise by name**: exact match (case-insensitive) → word-level fuzzy → substring. On failure, return error and suggest `search_exercises`.

**Routine by name**: case-insensitive substring against caller's routines. Single match → proceed. Multiple matches → return all and ask for clarification. No match → return error with list of existing routine names.

**Workout by ID**: `delete_workout` / `update_workout` require a `session_id`. Bot must call `get_recent_workouts` first to surface the ID; tool descriptions state this requirement explicitly.

**Muscle groups**: case-insensitive substring match against `muscle_groups` table. Returns `(matched_ids, unresolved_names)`. If any unresolved, bot reports them and asks the user to pick valid names before proceeding.

## Error Handling

All handlers return a JSON string. On success: `{"success": true, ...}`. On failure: `{"error": "..."}` with a human-readable message the model can relay directly to the user.

The `execute_tool` dispatcher in `__init__.py` routes by tool name to the appropriate domain handler function, raising `{"error": "Unknown tool: <name>"}` for anything unrecognised.

## Service Layer

All handlers call existing service functions — no new service functions are needed:

- `workout_service.get_all_workouts`, `log_workout`, `delete_workout`, `update_workout`
- `exercise_service.get_all_exercises`, `create_exercise`, `update_exercise`, `delete_exercise`, `get_exercise_progression`
- `routine_service.get_all_routines`, `create_routine`, `update_routine`, `delete_routine`
- `get_all_muscle_groups` from `exercise_service`

## Testing

Existing `tests/test_chat.py` (3 tests: 403 gate, premium access, admin access) remains unchanged. No new chat tests are added — the service functions are already covered by their own test suites, and tool dispatch is thin glue.
