# Design: Batch JSON Import + Demo User

Date: 2026-08-11

## Overview

Two independent features:

1. **Batch JSON Import** — programmatic API endpoint for populating workout history (developer/admin use only, no UI).
2. **Demo User** — unauthenticated visitors can click "Try Demo" to log in as a read-only demo account.

---

## Feature 1: Batch JSON Import

### Purpose

Developer-facing endpoint for bulk-inserting historical workout sessions — intended for data migration, seeding, or scripted population. Not exposed in the UI.

### Request Format

`POST /api/workouts/import` — JSON body, array of session objects.

```json
[
  {
    "logged_at": "2025-01-10T09:00:00",
    "exercises": [
      {
        "exercise_id": 42,
        "sets": [
          {"reps": 8, "weight_lbs": 135},
          {"reps": 8, "weight_lbs": 135}
        ]
      }
    ]
  },
  {
    "logged_at": "2025-01-10T17:30:00",
    "exercises": [
      {
        "exercise_id": 17,
        "sets": [
          {"reps": 5, "weight_lbs": 225}
        ]
      }
    ]
  }
]
```

Each object is a `WorkoutRequest` (existing schema) plus a required `logged_at`. One object = one `workout_session` row. Exercise IDs are exact references — no name matching.

### Auth

Admin-only (`is_admin: true` on the calling user). Demo user blocked. Standard JWT in the `Authorization` header.

### Response

```json
{
  "sessions_created": 14,
  "sets_created": 87,
  "errors": [
    {"index": 3, "reason": "exercise_id 9999 does not exist"}
  ]
}
```

Per-session errors are non-fatal: skip the failing session, continue, report all errors in the response.

### Service Layer

New function `import_workouts(db, sessions, user_id)` in `app/services/workout_service.py`:

1. Validate all `exercise_id` values exist (single query, set lookup).
2. For each session object, call the existing `log_workout` logic with its `logged_at`.
3. Collect and return counts and any per-session errors.

No changes to existing routes or service functions.

### Schema

New request schema `WorkoutImportRequest` — a `WorkoutRequest` with `logged_at` required (not optional). New response schema `ImportResponse` with `sessions_created`, `sets_created`, `errors`.

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

- CSV import format.
- UI for batch import (developer API only).
- Non-admin users triggering imports.
- Two-step preview/confirm flow for import.
- Demo data reset on a schedule independent of server restarts.
