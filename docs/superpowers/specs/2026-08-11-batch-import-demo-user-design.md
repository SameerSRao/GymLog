# Design: Batch CSV Import + Demo User

Date: 2026-08-11

## Overview

Two independent features:

1. **Batch CSV Import** — authenticated users can upload a CSV of historical workout sessions.
2. **Demo User** — unauthenticated visitors can click "Try Demo" to log in as a read-only demo account.

---

## Feature 1: Batch CSV Import

### CSV Format

One row per set. Grouping key is the exact `timestamp` value — rows sharing a timestamp become one workout session.

```csv
timestamp,exercise_name,set_number,reps,weight_lbs
2025-01-10T09:00:00,Bench Press,1,8,135
2025-01-10T09:00:00,Bench Press,2,8,135
2025-01-10T17:30:00,Squat,1,5,225
2025-01-11T10:00:00,Deadlift,1,5,315
```

- `timestamp` — ISO 8601 datetime. The exact value becomes `logged_at` on the workout session.
- `exercise_name` — case-insensitive match against the `exercises` table. Unmatched names are skipped and reported in the response; the rest of the file still imports.
- `set_number` — integer; stored as-is on `exercise_sets`.
- `reps` — required integer.
- `weight_lbs` — optional float; empty cell treated as bodyweight (null).

### API Endpoint

`POST /api/workouts/import`

- Auth: standard JWT (all authenticated users, demo user blocked).
- Body: multipart form upload, field name `file`, `Content-Type: text/csv`.
- Response:

```json
{
  "sessions_created": 14,
  "sets_created": 87,
  "skipped_rows": [
    {"row": 12, "reason": "exercise 'Leg Day' not found"},
    {"row": 31, "reason": "invalid timestamp '2025-13-01T00:00:00'"}
  ]
}
```

Row errors are non-fatal: skip the offending row, continue processing, report all errors at the end.

### Service Layer

New function `import_workouts_from_csv(db, file_bytes, user_id)` in `app/services/workout_service.py`:

1. Parse CSV rows.
2. Build a name→id map for all exercises (single query, case-insensitive).
3. Group rows by exact timestamp string.
4. For each group, call the existing `log_workout` logic, passing the timestamp as `logged_at`.
5. Collect and return a list of skipped-row errors alongside the created session/set counts.

No changes to existing routes or service functions.

### UI

- "Import CSV" button added to `/workouts` page.
- Opens a `<input type="file" accept=".csv">` file picker.
- On selection, POST to `/api/workouts/import`.
- Show result banner: "14 sessions imported, 2 rows skipped" with expandable error details.

---

## Feature 2: Demo User

### Data Model

Add `is_demo: bool` column to `users` (default `False`). No other schema changes.

### Auth Endpoint

`GET /api/auth/demo` — no body, no password required. Returns a standard JWT for the demo user. The token payload includes `is_demo: true` so the frontend can detect it.

The login page gains a "Try Demo" button that calls this endpoint and stores the token identically to a normal login.

### Read-Only Enforcement

**Backend:** `require_not_demo` FastAPI dependency — reads `is_demo` from the current user, raises `403 Forbidden` if true. Applied to every mutation route:

- `POST /api/workouts`, `PUT /api/workout/{id}`, `DELETE /api/workout/{id}`
- `POST /api/workouts/import`
- `POST /api/exercises`, `PUT /api/exercise/{id}`, `DELETE /api/exercise/{id}`
- `POST /api/routines`, `PUT /api/routine/{id}`, `DELETE /api/routine/{id}`
- `POST /api/chat` (or equivalent chat mutation routes)

**Frontend:** When `is_demo: true` is present in the decoded JWT, all create/edit/delete buttons are hidden and replaced with a "Sign up to log workouts" nudge linking to `/register`.

### Demo Data Seeding

`seed_demo_data(db)` in `app/db/seed.py` — idempotent, called at server startup after `seed_exercises`:

1. Create the demo user (username `demo`, `is_demo=True`) if absent.
2. Check the age of the demo user's most recent workout session.
3. If no workouts exist, or the newest session is older than 30 days:
   - Delete all existing demo workout sessions (cascade deletes sets).
   - Re-seed ~8 weeks of realistic sample workouts with `logged_at` anchored to `now - N days` so the calendar always looks current.

### Monthly Reset

No cron job needed. The idempotent startup check handles calendar drift automatically: each server start re-seeds if demo data is stale (>30 days old). Since all writes are blocked, data can only go stale from time passing, not from user mutations.

---

## Out of Scope

- JSON import format (CSV only for now).
- Premium gating on import (all authenticated users).
- Demo data reset on a schedule independent of server restarts.
- Two-step preview/confirm flow for import.
