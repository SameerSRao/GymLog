# Exercise Browser — Edit & Delete Design

**Date:** 2026-07-28
**Branch:** feat/crud-exercises-backend

## Summary

Add inline edit and delete functionality to the existing `/exercises` browser page. No backend changes — the PUT and DELETE endpoints are already implemented. Also add `/exercises` nav links to pages that currently only have `/workouts`.

## Pages Changed

| File | Change |
|------|--------|
| `app/static/exercises.html` | Add per-row edit form + delete with confirmation |
| `app/static/index.html` | Add Exercises nav link |
| `app/static/workouts.html` | Add Exercises nav link |
| `SPEC.md` | Add `/exercises` to pages table; remove from "What's Not Built Yet" |

No changes to `main.py` or any backend file — `GET /exercises` route already exists.

## Row Structure

The existing `.ex-row` `<a>` elements become `<div>`s (buttons can't be nested inside anchors). Each row in view mode shows:

- Exercise name as a link to `/exercise/{id}`
- Equipment tag + up to 3 muscle group tags
- **Edit** button (right side, `.btn-edit` style from workout.html)
- **Delete** button (right side, `.btn-delete` style from workout.html)

## Edit Flow

Clicking **Edit** replaces the row's innerHTML with an inline form (full row swap, matching workout.html's per-exercise block pattern):

**Fields:**
- `name` — text input (pre-filled)
- `equipment` — text input (pre-filled, optional)
- `target` — text input (pre-filled, optional)
- `instructions` — textarea (pre-filled, optional)
- `muscle_groups` — searchable checkbox dropdown, reusing the existing `.filter-panel` + `.filter-option` CSS already in the page

**Actions:**
- **Cancel** — re-renders the original read-only row from the in-memory `allExercises` array
- **Save** — calls `PUT /api/exercise/{id}` with updated fields and `muscle_group_ids`
  - 200 → updates the exercise object in `allExercises`, re-renders row in view mode
  - 409 (name conflict) → shows inline error below the form: "An exercise with that name already exists"
  - Other errors → generic inline error

Only one row can be in edit mode at a time. Clicking Edit while another row is already open closes the open row (discarding unsaved changes) and opens the new one.

## Delete Flow

Clicking **Delete** opens a confirmation overlay (`.confirm-overlay` pattern from workout.html, reused).

On confirm:
- Calls `DELETE /api/exercise/{id}`
- **204** → removes the row element from the DOM, splices exercise from `allExercises`, updates `results-meta` count
- **409** (has logged history) → closes overlay, shows a dismissible message on the row: "Can't delete — this exercise has logged history"
- **404** → closes overlay, shows: "Exercise not found"

The overlay is a single shared instance (one per page), pre-populated with the exercise name before opening.

## Navigation Updates

- `index.html`: add `<a href="/exercises" class="btn-secondary">Exercises</a>` in `.page-header` alongside existing Workouts link
- `workouts.html`: add `<a href="/exercises" class="btn-secondary">Exercises</a>` in its header area
- `dashboard.html`: already has both links — no change
- `exercises.html`: already has Log Workout link — no change needed

## Muscle Group Checkbox Dropdown

The edit form's muscle group selector reuses the existing `.filter-panel` / `.filter-option` / `.filter-search` CSS already present in exercises.html. It's a button that opens a panel with a search input and a scrollable checkbox list. Pre-checks the exercise's current muscle groups on open.

## Out of Scope

- Bulk edit/delete
- Exercise merge
- Reordering or categorization
- New exercise creation (already exists on the log page)
