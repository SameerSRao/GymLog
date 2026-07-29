# Exercise Detail Page — Edit & Equipment Dropdown Design

**Date:** 2026-07-28
**Branch:** feat/crud-exercises-backend (or new branch)

## Summary

Add inline edit functionality to the exercise detail page (`/exercise/{id}`) and replace the free-text equipment input with a `<select>` dropdown in all exercise edit forms. No backend changes — `PUT /api/exercise/{id}` already handles all fields.

## Files Changed

| File | Change |
|------|--------|
| `app/static/exercise.html` | Add Edit button + inline header swap edit form |
| `app/static/exercises.html` | Replace equipment `<input>` with `<select>` in the edit row form |

## Equipment Dropdown

A shared static list used in both files. All 29 values come from the seeded exercise data:

```
(none / blank)
assisted, band, barbell, body weight, bosu ball, cable, dumbbell,
elliptical machine, ez barbell, hammer, kettlebell, leverage machine,
medicine ball, olympic barbell, resistance band, roller, rope,
skierg machine, sled machine, smith machine, stability ball,
stationary bike, stepmill machine, tire, trap bar,
upper body ergometer, weighted, wheel roller
```

The blank option represents "no equipment specified" and maps to `null` on save. If an exercise has a current equipment value not in the list (legacy custom data), the select falls back to blank.

## Exercise Detail Page (`exercise.html`)

### Edit Button

A small "Edit" button rendered to the right of the `<h1>` exercise name. Styled as `.btn-edit` consistent with exercises.html. Only visible in view mode.

### Edit Mode — Inline Header Swap

Clicking Edit replaces the header section (the `<h1>`, `.tags` div, and `<details>` instructions element) with an inline edit form. The PR banner, chart, and session cards below are untouched.

**Form fields:**
- `name` — text input, required, prefilled with `info.name`
- `equipment` — `<select>` with 29 options + blank, prefilled to `info.equipment`
- `target` — text input, optional, prefilled with `info.target`
- `instructions` — textarea, optional, prefilled with `info.instructions`
- `muscle_groups` — searchable checkbox dropdown (same `.filter-panel` / `.filter-option` pattern as exercises.html), pre-checked with `info.muscle_groups`

**Actions:**
- **Save** — calls `PUT /api/exercise/{id}` with `{ name, equipment, target, instructions, muscle_group_ids }`
  - 200 → update in-memory `info` object, re-render header in view mode, update `document.title`
  - 409 → inline error below form: "An exercise with that name already exists"
  - Other errors → inline error: "Something went wrong, please try again"
- **Cancel** — re-renders header from cached `info` object, no network call

### State

One boolean `let editing = false` tracks mode. The `info` object fetched on page load is the source of truth for Cancel and view-mode re-render. On successful save, `info` is updated in place before re-rendering.

### Muscle Group Dropdown

Fetches `GET /api/muscle-groups` once on page load (alongside the existing `info` and `progression` fetches). Stored in `let allMuscleGroups = []`. The dropdown opens/closes via a button, filters via a search input, and updates `let editMuscleGroupIds = []` on checkbox toggle.

## exercises.html — Equipment Select

The existing edit row form has:
```html
<input id="edit-equipment-${ex.id}" class="edit-input" value="${equipVal}" placeholder="e.g. barbell" />
```

Replace with:
```html
<select id="edit-equipment-${ex.id}" class="edit-input">
  <option value="">— none —</option>
  <!-- 29 options -->
</select>
```

The `saveEdit(id)` function already reads `.value` from the element — no logic change needed, just the DOM type. `renderEditRow(ex)` pre-selects the option matching `ex.equipment` (or blank if no match).

## Out of Scope

- Deleting exercises from the detail page (already available on exercises browser)
- Editing session history or sets from this page
- Adding new equipment values (fixed list)
- Creating exercises from the detail page
