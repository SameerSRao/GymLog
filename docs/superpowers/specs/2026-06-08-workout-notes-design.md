# Workout Notes Design

**Goal:** Surface the existing `raw_input` column on `workout_sessions` as a user-facing notes field — writable on the log form, displayed on the workout detail page, and editable via the existing edit mode.

**Architecture:** Backend adds `notes` to request and response schemas and wires it through the service layer. Frontend adds a textarea to the log form and edit mode, and displays notes in the workout header when present. No migration needed — the column already exists.

---

## Backend

### `app/api/schemas.py`

Add `notes: Optional[str] = None` to two schemas:

- `WorkoutRequest` — accepts notes from the log form and edit form
- `WorkoutDetailed` — returns notes in the workout detail response

### `app/services/workout_service.py`

- `log_workout`: set `session.raw_input = workout.notes` when creating the session
- `update_workout`: set `session.raw_input = workout.notes` when updating the session

### `app/api/routes.py`

- `_build_workout_detailed`: include `notes=session.raw_input` in the `WorkoutDetailed` constructor

---

## Frontend

### `app/static/index.html`

Add an optional `<textarea>` between the exercise list (`#exercises`) and the "Log Workout" button. Placeholder text: `"Notes (optional)"`. In `submitWorkout()`, read the textarea value; if non-empty, include `notes` in the JSON body sent to `POST /api/workouts`. If empty, omit (the field defaults to `null`).

### `app/static/workout.html`

**View mode:** Below the `<p class="workout-meta" id="workout-meta">` line, add `<p class="workout-notes" id="workout-notes" style="display:none"></p>`. After load, if `w.notes` is non-empty, set its `textContent` and show it. Style: similar to `.workout-meta` but color `#888`.

**Edit mode:** Below the edit exercise container, add a `<textarea id="edit-notes">` pre-populated with `workout.notes` when `enterEditMode()` is called. In `saveWorkout()`, read the textarea and include `notes` in the PUT body.

---

## Scope

- No per-exercise notes (workout-level only)
- No character limit enforced client-side (the column is `TEXT`, unlimited)
- No markdown or rich text — plain text only
