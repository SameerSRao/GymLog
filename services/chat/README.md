# Chat Service

AI coaching chatbot. A separate FastAPI service that wraps Google Gemini with a tool-use loop. The chat service never touches the database directly — it forwards all data operations to the API service using the user's own Bearer token.

---

## How It Works

```
Browser sends POST /api/chat
  │  (nginx proxies to this service)
  │
  ▼
chat/routes.py
  ├── Validates token via GET /api/auth/me on the API service
  ├── Rejects demo accounts and non-premium users
  └── Starts SSE streaming response
       │
       ▼
chat/service.py  run_chat()
  ├── Builds system prompt (static prompt + fitness knowledge + dynamic user context)
  ├── Sends messages to Gemini (gemini-3-flash-preview)
  │
  └── Gemini tool loop (up to 10 rounds):
       ├── Gemini requests a tool call
       ├── tools/__init__.py execute_tool() dispatches to the right module
       │    ├── tools/workouts.py  → calls API service endpoints
       │    ├── tools/exercises.py → calls API service endpoints
       │    └── tools/routines.py  → calls API service endpoints
       └── Result fed back to Gemini as function response
       
  When no tool calls: Gemini returns text → streamed to browser as SSE
```

---

## Running

```bash
# Via Docker Compose (recommended — needs API service running)
docker compose up --build

# Standalone (set API_BASE_URL to point at the API service)
API_BASE_URL=http://localhost:8000 GOOGLE_API_KEY=... uvicorn app.main:app --reload
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Gemini API key |
| `API_BASE_URL` | Yes | Base URL of the API service. Default: `http://localhost:8000` |

---

## File-by-File Breakdown

### `app/main.py`

Minimal FastAPI app. Mounts the chat router under `/api` and provides a `GET /health` endpoint. Docs disabled in all environments.

---

### `app/chat/schemas.py`

```python
class MessageSchema:
    role: str    # "user" or "assistant"
    content: str

class ChatRequest:
    messages: list[MessageSchema]  # full conversation history, managed by client
    local_time: str | None         # ISO 8601; used when logging workouts without explicit timestamp
```

The client sends the entire conversation history on every request because SSE is one-way and stateless — there is no server-side session.

---

### `app/chat/routes.py`

`POST /api/chat`

1. Extracts the Bearer token.
2. Calls `GET /api/auth/me` on the API service to validate the token and get user flags.
3. Rejects with `403` if the user is a demo account or doesn't have premium/admin status.
4. Calls `run_chat(token, messages, local_time)` which returns a generator.
5. Wraps the generator in a `StreamingResponse` with `media_type="text/event-stream"`.

Each yielded chunk:
```
data: {"text": "some text..."}\n\n
```
Final:
```
data: [DONE]\n\n
```
Exceptions inside the generator:
```
data: {"error": "error message"}\n\n
```

---

### `app/chat/service.py`

`run_chat(token, messages, local_time)` — the core agentic loop.

**System prompt construction:** On each call, the system content is built fresh:

1. Static `system_prompt.md` — GymBot persona and tool usage rules.
2. Static `knowledge.md` — fitness reference content (exercise recommendations, muscle group info).
3. Dynamic user context — fetches `GET /api/workouts` and `GET /api/routines` to inject total workout count, last workout date, and saved routine names.
4. Optional `local_time` line injected last.

**Message history:** Truncated to the last 20 messages to stay within context limits. Converted from `{"role": ..., "content": ...}` dicts to Gemini `Content` objects.

**Tool loop:** Up to 10 rounds. Each round:
1. Send current `contents` to Gemini with the tool declarations.
2. If the response has no function calls, yield the text and break.
3. If there are function calls, append the model's response to `contents`, execute each tool via `execute_tool()`, append the results as function responses, and loop.
4. If 10 rounds are exhausted, yield a fallback error message.

**Rate limiting:** Gemini `429` responses are retried up to 4 times with exponential backoff (1s, 2s, 4s).

**Config:**
- `_MAX_HISTORY = 20` — messages kept from conversation history
- `_MAX_TOOL_ROUNDS = 10` — max Gemini tool loop iterations per request

---

### `app/client/api_client.py`

A singleton `httpx.Client` (`api_client`) used by all tool modules to call the API service.

All methods take a `token: str` and pass it as `Authorization: Bearer <token>` so operations execute as the user, not as a service account. This means:
- Permission checks on the API side still apply (e.g., demo accounts can't log workouts).
- Data is automatically scoped to the user — no need to pass user IDs.

Methods map 1:1 to API service endpoints:

| Method | API endpoint |
|--------|-------------|
| `get_me(token)` | `GET /api/auth/me` |
| `get_exercises(token)` | `GET /api/exercises` |
| `post_exercise(token, data)` | `POST /api/exercises` |
| `put_exercise(token, id, data)` | `PUT /api/exercise/{id}` |
| `delete_exercise(token, id)` | `DELETE /api/exercise/{id}` |
| `get_exercise_progression(token, id)` | `GET /api/exercise/{id}/progression` |
| `get_workouts(token, year, month)` | `GET /api/workouts` |
| `get_workout(token, session_id)` | `GET /api/workout/{id}` |
| `post_workout(token, data)` | `POST /api/workouts` |
| `put_workout(token, session_id, data)` | `PUT /api/workout/{id}` |
| `delete_workout(token, session_id)` | `DELETE /api/workout/{id}` |
| `get_routines(token)` | `GET /api/routines` |
| `get_routine(token, routine_id)` | `GET /api/routine/{id}` |
| `post_routine(token, data)` | `POST /api/routines` |
| `put_routine(token, routine_id, data)` | `PUT /api/routine/{id}` |
| `delete_routine(token, routine_id)` | `DELETE /api/routine/{id}` |

---

### `app/tools/__init__.py`

`TOOLS` — a single `types.Tool` object holding all function declarations, passed to Gemini in `GenerateContentConfig`.

`execute_tool(name, inputs, token, local_time)` — dispatches by name to one of the three tool modules. Returns JSON string results back to the loop.

Tool names are grouped into three sets:
- `_WORKOUT_NAMES` → `handle_workout_tool`
- `_EXERCISE_NAMES` → `handle_exercise_tool`
- `_ROUTINE_NAMES` → `handle_routine_tool`

---

### `app/tools/base.py`

Shared fuzzy-matching helpers used by multiple tool modules.

**`_best_exercise_match(query_words, exercises)`** — finds the exercise whose name best matches a list of query words. First tries full-word matches (`{"barbell", "bench", "press"}` ⊆ name words), then falls back to substring match. Returns `None` if no match.

**`_resolve_muscle_groups(names, all_exercises)`** — takes a list of muscle group name strings and resolves them to IDs. Extracts all unique muscle groups from the exercise list, then does a case-insensitive substring lookup for each name. Returns `(matched_ids, unresolved_names)`.

**`_resolve_routine(name, routines)`** — finds a routine by name substring match. Returns the routine dict if exactly one match, or an error dict if zero or multiple matches.

---

### `app/tools/workouts.py`

Gemini tool declarations and handlers for workout operations.

**`get_recent_workouts`** — fetches all workouts, filters client-side to the last `days` days, then fetches detail for each matching session. Returns a list of `{session_id, date, exercises, total_sets}`.

**`log_workout`** — resolves exercise names to IDs using `_resolve_exercise_inputs` (which calls `_best_exercise_match` for fuzzy matching), then calls `POST /api/workouts`. If `logged_at` is provided by Gemini or from `local_time`, it's included. Returns success or an error listing unresolved exercise names.

**`delete_workout`** — calls `DELETE /api/workout/{id}` by session ID. Gemini is instructed to call `get_recent_workouts` first to find the right session ID.

**`update_workout`** — resolves exercise names, then calls `PUT /api/workout/{id}` with the full updated exercise list.

**`_resolve_exercise_inputs(exercise_inputs, ex_by_name, all_ex)`** — converts a list of `{exercise_name, sets}` dicts (Gemini's format) into `{exercise_id, sets}` dicts (API's format). Tries exact name match first, then `_best_exercise_match`. Returns `(resolved_list, not_found_names)`.

---

### `app/tools/exercises.py`

**`search_exercises`** — fetches all exercises, filters by query string appearing in name or any muscle group name, returns up to 20 matches with `{id, name, equipment, muscle_groups}`.

**`get_exercise_progression`** — finds exercise candidates by word/substring match, then calls `GET /api/exercise/{id}/progression` for up to 5 candidates, picking the one with the most sessions logged. Returns the last 10 sessions with date, set count, volume, and best weight.

**`create_exercise`** — resolves muscle group names to IDs via `_resolve_muscle_groups`, then calls `POST /api/exercises`.

**`update_exercise`** — finds the exercise by name (fuzzy match), then calls `PUT /api/exercise/{id}`. Translates 403 to a user-friendly "you can only edit exercises you created" message and 409 to a name conflict message.

**`delete_exercise`** — finds the exercise by name, then calls `DELETE /api/exercise/{id}`. Translates 403/409 to friendly messages.

---

### `app/tools/routines.py`

**`get_routines`** — fetches the summary list, then fetches full detail for each routine. Returns the full list including exercises.

**`create_routine`** — resolves exercise names, assigns positions (1-indexed by order in Gemini's list), calls `POST /api/routines`.

**`update_routine`** — resolves the routine by fuzzy name match (`_resolve_routine`). If no new exercises are provided, fetches the current exercise list to preserve it. Then calls `PUT /api/routine/{id}`.

**`delete_routine`** — resolves by name, calls `DELETE /api/routine/{id}`.

**`_resolve_routine_exercises(exercise_inputs, ex_by_name, all_ex)`** — converts `{exercise_name, sets}` dicts to `{exercise_id, position, num_sets}` for the routine API.

---

### `app/context/system_prompt.md`

Static system prompt injected at the start of every Gemini request. Defines:
- GymBot's persona and tone rules (concise, never invent data, redirect medical questions)
- Tool usage rules with concrete examples for each tool
- Exercise naming conventions (e.g., "bench press" → search for "Barbell Bench Press")
- What to do if a tool isn't available for a request

---

### `app/context/knowledge.md`

Static fitness reference injected alongside the system prompt. Contains:
- Exercise recommendations grouped by muscle group
- Notes on movement patterns and equipment variants
- General training guidance the AI can use to answer questions without calling a tool
