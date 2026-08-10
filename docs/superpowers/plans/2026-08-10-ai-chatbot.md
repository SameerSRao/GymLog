# AI Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the remaining pieces so GymBot is live locally and in production on Railway.

**Architecture:** Three implementation files are already written and committed to `feat/chatbot`: `app/services/chat_service.py` (agentic tool loop via Groq), `app/api/chat_routes.py` (SSE endpoint), and `app/static/dashboard.html` (Option A layout). What remains is environment setup, a spec doc cleanup, a local smoke test, and setting the Railway production env var.

**Tech Stack:** FastAPI, Groq API (via `openai` Python SDK with custom `base_url`), `llama-3.3-70b-versatile`, SSE, Docker Compose for local dev.

## Global Constraints

- Branch: `feat/chatbot`
- Model: `llama-3.3-70b-versatile` via `https://api.groq.com/openai/v1`
- Auth: all API routes are JWT-protected; `POST /api/chat` is no exception
- Local run: `docker compose up --build`
- No tests for the chat service (Groq calls require live credentials; mocking not worth it for demo)
- No server-side conversation persistence

---

### Task 1: Environment variable setup

**Files:**
- Modify: `.env`
- Modify: `.env.example`

**Interfaces:**
- Produces: `GROQ_API_KEY` available to `chat_service.py` at `os.environ.get("GROQ_API_KEY", "")`

- [ ] **Step 1: Add GROQ_API_KEY to .env**

Open `.env` and append:

```text
GROQ_API_KEY=<your-groq-api-key-from-console.groq.com>
```

Replace `<your-groq-api-key-from-console.groq.com>` with the real key. The file already contains `DATABASE_URL`, `ENVIRONMENT`, `ADMIN_PASSWORD`, and `JWT_SECRET`.

- [ ] **Step 2: Add GROQ_API_KEY placeholder to .env.example**

Open `.env.example` and append:

```text
GROQ_API_KEY=your-groq-api-key-here
```

- [ ] **Step 3: Verify .env is in .gitignore**

Run:

```bash
grep -n ".env" .gitignore
```

Expected: `.env` is listed. If not, add it. `.env.example` should NOT be in `.gitignore` (it's safe to commit).

- [ ] **Step 4: Commit .env.example only**

```bash
git add .env.example
git commit -m "chore: add GROQ_API_KEY to env example"
```

Do NOT `git add .env` — it contains secrets.

---

### Task 2: Fix spec doc markdown lint warnings

**Files:**
- Modify: `docs/superpowers/specs/2026-08-10-ai-chatbot-design.md`

**Interfaces:**
- None — cosmetic only

The markdownlint tool flagged: fenced code blocks without a language tag (lines 55, 66, 77, 89) and a table with missing pipe spacing (line 128).

- [ ] **Step 1: Add language tags to fenced code blocks**

The four code blocks currently start with ` ``` ` and no language. Change each to ` ```text `:

Block at line 55 (search_exercises schema):
```text
Input:  { query: string }
Output: { matches: [{id, name, equipment}], count: int }
```

Block at line 66 (get_recent_workouts schema):
```text
Input:  { days: int }
Output: { workouts: [{session_id, date, exercises: [name], total_sets}], count: int }
```

Block at line 77 (get_exercise_progression schema):
```text
Input:  { exercise_name: string }
Output: { exercise: string, sessions: [{date, sets, volume, best_set_weight}] }
        OR { error: string }
```

Block at line 89 (log_workout schema):
```text
Input:  { exercises: [{exercise_name, sets: [{reps, weight_lbs?}]}], notes? }
Output: { success: true, session_id, logged_at, exercises_logged }
        OR { error: string }
```

- [ ] **Step 2: Fix table pipe spacing**

Line 128 currently reads:

```text
|---|---|
```

Change to:

```text
| --- | --- |
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-10-ai-chatbot-design.md
git commit -m "docs: fix markdown lint warnings in chatbot spec"
```

---

### Task 3: Commit implementation files and local smoke test

**Files:**
- Already created: `app/services/chat_service.py`, `app/api/chat_routes.py`
- Already modified: `app/main.py`, `app/static/dashboard.html`, `requirements.txt`

**Interfaces:**
- Consumes: `GROQ_API_KEY` from `.env` (Task 1)
- Produces: working chatbot at `http://localhost:8000`

- [ ] **Step 1: Commit all unstaged implementation files**

```bash
git add app/services/chat_service.py \
        app/api/chat_routes.py \
        app/main.py \
        app/static/dashboard.html \
        requirements.txt
git commit -m "feat: add AI chatbot with Groq tool use"
```

- [ ] **Step 2: Build and start the app**

```bash
docker compose up --build
```

Wait for: `Application startup complete.`

- [ ] **Step 3: Smoke test — chat loads**

Open `http://localhost:8000`. Expected:
- Stats bar shows (Total / This Week / Day Streak)
- Chat window shows GymBot welcome message: "Hey! I'm GymBot..."
- Text input and Send button are visible

- [ ] **Step 4: Smoke test — search exercises**

Type: `what exercises can I do for chest?`

Expected: GymBot responds with a list of chest exercises (it will call `search_exercises` with query `"chest"`). Response should appear within ~5 seconds.

- [ ] **Step 5: Smoke test — confirm-before-log**

Type: `log my bench press, 3 sets of 8 at 135 lbs`

Expected: GymBot responds asking for confirmation (e.g., "Just to confirm — logging 3×8 at 135 lbs of Barbell Bench Press. Is that right?") without immediately logging.

- [ ] **Step 6: Smoke test — log after confirmation**

Reply: `yes`

Expected: GymBot calls `log_workout` and responds with something like "Done! Logged your Barbell Bench Press session." The stats bar should update (Total count increases by 1).

- [ ] **Step 7: Smoke test — recent workouts**

Type: `what did I do this week?`

Expected: GymBot calls `get_recent_workouts` and lists the session just logged.

---

### Task 4: Production deployment (Railway)

**Files:** None — Railway dashboard only

**Interfaces:**
- Consumes: Groq API key from console.groq.com
- Produces: chatbot live at the Railway production URL

- [ ] **Step 1: Add GROQ_API_KEY in Railway**

1. Open railway.app → your GymLog project
2. Click the service → **Variables** tab
3. Add variable: `GROQ_API_KEY` = `<your-groq-api-key>`
4. Railway will trigger a redeploy automatically

- [ ] **Step 2: Push the branch and open a PR**

```bash
git push origin feat/chatbot
```

Then open a PR from `feat/chatbot` → `main` on GitHub and merge it. Railway redeploys on merge to main.

- [ ] **Step 3: Verify production**

Open your Railway production URL. Repeat smoke test steps 3–7 against production. Confirm the chatbot works end-to-end with the live Postgres database.
