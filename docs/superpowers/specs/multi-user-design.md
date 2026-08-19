# Multi-User Support — Design Spec

**Date:** 2026-08-11

---

## Overview

Convert GymLog from a single-admin app to a multi-user app with self-registration gated by a shared signup code. Each user owns their workouts, routines, and custom exercises. Seeded (global) exercises are visible to all but editable only by admins. The AI chatbot is gated behind an `is_premium` flag.

---

## Data Model

### New: `users` table

| Column        | Type     | Notes                  |
| ------------- | -------- | ---------------------- |
| id            | INTEGER  | primary key            |
| username      | TEXT     | unique, not null       |
| password_hash | TEXT     | bcrypt                 |
| is_admin      | BOOLEAN  | default false          |
| is_premium    | BOOLEAN  | default false          |
| created_at    | DATETIME | UTC, default now       |

### Modified: `workout_sessions`

Add `user_id` (INTEGER, FK → users.id, NOT NULL). Existing data must be assigned to a user before the migration is finalized — reset the DB or assign rows to a seed admin account.

### Modified: `routines`

Add `user_id` (INTEGER, FK → users.id, NOT NULL).

### Modified: `exercises`

Add `user_id` (INTEGER, FK → users.id, nullable).

- `user_id = NULL` — global seeded exercise, visible to all, editable by admin only
- `user_id = <id>` — custom exercise, private to that user, editable/deletable by owner

The global unique constraint on `exercises.name` is replaced by application-level checks:

- Seeded exercises: deduplication handled by the existing idempotent `seed.py`
- Custom exercises: checked with `WHERE user_id = :me AND name = :name` before insert

---

## Environment Variables

| Variable        | Notes                                    |
| --------------- | ---------------------------------------- |
| `SIGNUP_CODE`   | Required to register; shared out-of-band |
| `JWT_SECRET`    | Unchanged                                |
| `GOOGLE_API_KEY`| Unchanged                                |
| `DATABASE_URL`  | Unchanged                                |

`ADMIN_PASSWORD` is removed — replaced by user accounts with `is_admin = true`.

Admin and premium status are set by running a small CLI helper after registration:

```
python -m app.admin promote <username> --admin
python -m app.admin promote <username> --premium
```

---

## Auth Flow

### Registration

`POST /api/auth/register`

Request:

```json
{ "username": "alice", "password": "...", "signup_code": "..." }
```

- 400 if `signup_code` does not match `SIGNUP_CODE` env var
- 409 if `username` is already taken
- Creates user with `is_admin = false`, `is_premium = false`
- Returns a JWT on success

### Login

`POST /api/auth/login`

Request:

```json
{ "username": "alice", "password": "..." }
```

- 401 if credentials are wrong
- Returns a JWT on success

### JWT Payload

```json
{
  "sub": "<user_id>",
  "username": "alice",
  "is_admin": false,
  "is_premium": false,
  "exp": "..."
}
```

Token expiry: 30 days (unchanged).

All `/api` routes except `/api/auth/login` and `/api/auth/register` require a valid Bearer token.

The `get_current_user` dependency returns a dict with `user_id`, `username`, `is_admin`, and `is_premium` decoded from the token — no DB lookup needed.

---

## Permission Model

| Action                                          | Who can                  |
| ----------------------------------------------- | ------------------------ |
| Edit/delete seeded exercise (`user_id = NULL`)  | Admin only               |
| CRUD own workouts, routines, custom exercises   | Any registered user      |
| Use chatbot (`POST /api/chat`)                  | Premium users + admin    |
| Access another user's data                      | Nobody                   |

Permission checks are zero-query: `is_admin` and `is_premium` are decoded directly from the JWT.

---

## Service Layer

All workout and routine services gain a `user_id` parameter and filter all queries by it.

**`exercise_service`:**

- Reads: `WHERE user_id = :me OR user_id IS NULL`
- Write (custom exercise create): sets `user_id = :me`
- Edit/delete: if `user_id IS NULL` → reject unless caller is admin; else if `user_id != :me` → reject unless caller is admin

**New `user_service.py`:**

- `create_user(db, username, password)` → `User`
- `get_user_by_username(db, username)` → `User | None`

**New `app/admin.py` CLI:**

- `promote <username> --admin` — sets `is_admin = true`
- `promote <username> --premium` — sets `is_premium = true`

**`chat_service.py` / `chat_tools.py`:**

`run_chat` receives `user_id` from the route and passes it into `execute_tool`. All tools that read or write user data (`get_recent_workouts`, `get_routines`, `log_workout`) use `user_id` to scope their queries and writes. `search_exercises` and `get_exercise_progression` already read global + owned exercises via the standard filter.

---

## API Changes

| Method    | Route                  | Change                                                                                   |
| --------- | ---------------------- | ---------------------------------------------------------------------------------------- |
| POST      | `/api/auth/register`   | New                                                                                      |
| POST      | `/api/auth/login`      | Now takes `username` + `password`                                                        |
| POST      | `/api/chat`            | 403 if caller is not premium and not admin                                               |
| PUT/DELETE| `/api/exercise/{id}`   | 403 if seeded and not admin, or custom and not owner                                     |
| All others| —                      | Extract `user_id` from JWT, pass to service                                              |

---

## Frontend Changes

### New: `/register` page

Same dark style as `/login`. Fields: username, password, signup code. On success stores JWT and redirects to `/`.

### Modified: `/login` page

Adds username field.

### Modified: nav/header

Displays logged-in username. Admin users get a subtle "admin" badge.

### Modified: chatbot panel

Non-premium users see a locked/upgrade message in place of the chat input.

### Modified: `auth.js`

Decodes JWT payload client-side to expose `is_premium` and `is_admin` for UI gating.

---

## What's Not Included

- Password reset / forgot password
- Admin UI for managing users
- User profile pages
- Viewing other users' workouts
