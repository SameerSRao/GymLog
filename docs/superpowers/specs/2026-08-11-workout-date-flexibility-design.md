# Workout Date Flexibility — Design Spec

## Problem

Users cannot backfill workouts for a past date, and cannot correct the date/time
of an existing workout. The frontend always sends the current moment as `logged_at`.
The backend already accepts an optional `logged_at` on both create and update —
this is a frontend-only gap.

## Scope

Two pages: the workout log page (`index.html`) and the workout edit page
(`workout.html`). No backend changes required.

---

## Logging Page (`index.html`)

### UI

A `<input type="date">` field, always visible at the top of the log form,
labeled "Workout Date". It is pre-filled with today's local date.

### Behavior

- If the user leaves the date as today (or clears it), `logged_at` is set to
  the current moment — identical to existing behavior.
- If the user selects a different date, `logged_at` is set to
  `<selected-date>T00:00:00` (midnight local time).

### Validation (on save)

- If a date is entered, it must not be in the future.
- Empty/cleared field is allowed; falls back to current moment.

---

## Edit Page (`workout.html`)

### UI

When the user enters edit mode, the read-only date header is replaced by two
side-by-side inputs:

- `<input type="date">` — pre-populated from the existing `logged_at`
- `<input type="time">` — pre-populated from the existing `logged_at`

Both inputs sit at the top of the edit panel, above sets and notes.

### Behavior

On save, the two inputs are combined into a local ISO string
(`<date>T<time>:00`) and sent as `logged_at` in the PUT request body.

### Validation (on save)

- Both date and time are required.
- Combined datetime must not be in the future.

---

## Shared Logic

A small inline helper combines a date string + optional time string into a
local ISO string (e.g. `"2026-08-10T00:00:00"`). This follows the existing
pattern of `localISOString()` defined inline in each page's `<script>` block.
No shared JS file is introduced.

---

## Out of Scope

- Backend changes (already supported)
- Custom date picker widget (native inputs used throughout)
- Time picker on the log page (date only)
- Validation that the date is not too far in the past
