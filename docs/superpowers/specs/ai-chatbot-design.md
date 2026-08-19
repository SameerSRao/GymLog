# AI Chatbot Design — GymLog

**Date:** 2026-08-10
**Branch:** feat/chatbot
**Status:** Approved

---

## Goal

Add a conversational AI assistant (GymBot) to the GymLog dashboard that can log workouts, query workout history, and check exercise progression — using real database reads and writes, not just canned responses.

This is the primary UI change for the app's home page.

---

## Architecture

### Backend

**`app/services/chat_service.py`** — core agentic loop.

- Instantiates an `openai.OpenAI` client pointed at `https://api.groq.com/openai/v1` with `GROQ_API_KEY`.
- Model: `llama-3.3-70b-versatile`.
- Runs a `while True` loop:
  1. Call Groq with the full message history + 4 tool definitions.
  2. If `finish_reason == "tool_calls"`: execute each tool against the DB, append the assistant turn and tool result turns to the message list, loop.
  3. If `finish_reason == "stop"`: yield the response text and break.
- The loop is a synchronous generator (`yield`). No streaming during tool calls — the final text arrives as one chunk.
- The system prompt instructs the model to **confirm workout details with the user before calling `log_workout`**.

**`app/api/chat_routes.py`** — single endpoint.

- `POST /api/chat` — JWT-protected via `Depends(get_current_user)`.
- Request body: `{ messages: [{role: "user"|"assistant", content: "..."}] }`.
- Response: `text/event-stream` (SSE).
  - Each chunk: `data: {"text": "..."}\n\n`
  - On exception: `data: {"error": "..."}\n\n`
  - Final: `data: [DONE]\n\n`
- The server is stateless — the client sends full conversation history on every request.
- DB session stays open for the duration of the generator via FastAPI's `get_db` dependency.

**`app/main.py`** — registers `chat_router` with `prefix="/api"`.

**`requirements.txt`** — adds `openai>=1.0.0`.

**`.env` / `.env.example`** — adds `GROQ_API_KEY`.

---

## The 4 Tools

### `search_exercises`

```text
Input:  { query: string }
Output: { matches: [{id, name, equipment}], count: int }
```

Case-insensitive substring match against all exercise names. Returns top 20.

---

### `get_recent_workouts`

```text
Input:  { days: int }
Output: { workouts: [{session_id, date, exercises: [name], total_sets}], count: int }
```

Filters all workouts to those logged within the last `days` days. Accesses `w.sets` and `s.exercise_def.name` via lazy load (acceptable for demo scale).

---

### `get_exercise_progression`

```text
Input:  { exercise_name: string }
Output: { exercise: string, sessions: [{date, sets, volume, best_set_weight}] }
        OR { error: string }
```

Fuzzy-matches exercise name, then delegates to existing `get_exercise_progression` service. Returns last 10 sessions. Returns an error string if no match found, so the model can ask the user to clarify or call `search_exercises` first.

---

### `log_workout`

```text
Input:  { exercises: [{exercise_name, sets: [{reps, weight_lbs?}]}], notes? }
Output: { success: true, session_id, logged_at, exercises_logged }
        OR { error: string }
```

Fuzzy-matches each exercise name to an `ExerciseDef` ID. Returns an error if any name can't be resolved (so the model can ask the user to clarify). On success, calls the existing `log_workout` service and returns the new session ID.

**Confirm-before-log:** Enforced at the system prompt level. The model is instructed to state the full workout details and wait for user confirmation before calling this tool.

---

## Dashboard UI (Option A)

Layout (top to bottom):

1. **Header** — logo + nav (History, Exercises, Routines)
2. **Stats bar** — Total workouts | This Week | Day Streak (loaded async from `/api/workouts`)
3. **Chat window** (460px tall, full width)
   - Scrollable messages area
   - Bot messages: left-aligned, dark bubble
   - User messages: right-aligned, white bubble
   - Typing dots animation while awaiting response
4. **"Log Workout manually →"** link — subdued style, below chat

**Chat behavior:**

- On page load: welcome message from GymBot appears immediately (no API call).
- User sends message → appended to local `history` array → `POST /api/chat` with full history → SSE consumed → bot message rendered.
- Enter sends; Shift+Enter inserts newline.
- Auto-scroll to bottom on new messages.
- Stats bar refreshes after every bot response (in case a workout was just logged).
- History is in-memory JS array — cleared on page refresh. No server-side persistence.

---

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq API key for LLM calls |
| `ANTHROPIC_API_KEY` | Not used — Groq replaces Anthropic |

`GROQ_API_KEY` must be set in Railway env vars for production.

---

## What's Explicitly Out of Scope

- Server-side conversation persistence (single-user app, page refresh is acceptable reset)
- Markdown rendering in chat (plain text + `\n → <br>` is sufficient)
- Streaming during tool calls (tool loop is fast, final text appears at once)
- Rate limiting or abuse protection (single-user app behind JWT)
- Tests for the chat service (Groq calls would require mocking; not worth the complexity for demo)
