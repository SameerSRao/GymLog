# Save as Routine Design

**Goal:** Add a "Save as Routine" button to the log workout page that
captures the current exercise list and set counts into a new routine.

**Scope:** Frontend JS changes to `app/static/index.html` only. No new
API endpoints.

---

## Behaviour

### Button visibility

A full-width secondary button labelled "Save as Routine" sits between the
notes textarea and the "Log Workout" button. It is hidden (`display:none`)
on page load and shown whenever at least one exercise block is present in
the form. A helper `updateSaveRoutineBtn()` manages visibility; it is
called from `addExercise()`, `removeExercise()`, and `loadRoutine()`.

### Save flow

1. User clicks "Save as Routine."
2. Iterate every `.exercise-block` inside `#exercises`. If any block has a
   name typed but no `dataset.exerciseId` (not selected from the dropdown),
   show an error toast — `'Select all exercises from the list before saving
   as a routine'` — and stop.
3. Call `window.prompt('Routine name:')`. If the user cancels (returns
   `null`) or submits an empty string, abort silently with no feedback.
4. Build the POST body:
   - `name`: the trimmed prompt value
   - `exercises`: one entry per block in DOM order
     - `exercise_id`: `parseInt(nameInput.dataset.exerciseId)`
     - `position`: 1-based index of the block in the list
     - `num_sets`: count of `<tr>` elements in `#sets-{id}`
5. POST `/api/routines`.
6. On **409**: toast `'A routine named "${name}" already exists'` (error).
7. On **other error**: toast `'Failed to save routine'` (error).
8. On **success**: toast `'"${name}" saved as routine'` (success).

### Button styling

Reuse the existing `.btn-new-exercise` class (solid `#333` border, `#888`
text, `border-radius: 6px`), full width, `margin-bottom: 12px` to
separate it from the "Log Workout" button.

---

## Implementation

Single file change: `app/static/index.html`.

### HTML

Add the button between `#workout-notes-input` and `#submitBtn`:

```html
<button
  class="btn-new-exercise"
  id="saveRoutineBtn"
  style="display:none; width:100%; margin-bottom:12px;"
  onclick="saveAsRoutine()"
>Save as Routine</button>
```

### JS — `updateSaveRoutineBtn()`

```js
function updateSaveRoutineBtn() {
  const hasBlocks =
    document.querySelectorAll('#exercises .exercise-block').length > 0;
  document.getElementById('saveRoutineBtn').style.display =
    hasBlocks ? 'block' : 'none';
}
```

Call sites: end of `addExercise()`, end of `removeExercise()`, end of
`loadRoutine()` (after the for-loop and the empty-routine fallback).

### JS — `saveAsRoutine()`

```js
async function saveAsRoutine() {
  const blocks = [
    ...document.querySelectorAll('#exercises .exercise-block')
  ];

  for (const block of blocks) {
    const id = block.id.replace('exercise-', '');
    const inp = document.getElementById(`name-${id}`);
    if (inp && inp.value.trim() && !inp.dataset.exerciseId) {
      showToast(
        'Select all exercises from the list before saving as a routine',
        'error'
      );
      return;
    }
  }

  const name = window.prompt('Routine name:');
  if (!name || !name.trim()) return;
  const trimmed = name.trim();

  const exercises = blocks.map((block, i) => {
    const id = block.id.replace('exercise-', '');
    const inp = document.getElementById(`name-${id}`);
    const numSets = document.querySelectorAll(`#sets-${id} tr`).length;
    return {
      exercise_id: parseInt(inp.dataset.exerciseId),
      position: i + 1,
      num_sets: numSets,
    };
  });

  try {
    const res = await fetch('/api/routines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: trimmed, exercises }),
    });
    if (res.status === 409) {
      showToast(`A routine named "${trimmed}" already exists`, 'error');
      return;
    }
    if (!res.ok) throw new Error();
    showToast(`"${trimmed}" saved as routine`, 'success');
  } catch {
    showToast('Failed to save routine', 'error');
  }
}
```

---

## Edge cases

| Scenario | Behaviour |
|---|---|
| Exercise typed but not picked from list | Error toast, no API call |
| `window.prompt` cancelled | Silent abort |
| `window.prompt` submitted blank | Silent abort |
| Name already taken (409) | Error toast naming the conflict |
| Exercise block with 0 sets | `num_sets: 0` sent; API accepts it |
| All exercises removed | Button hides; button cannot be clicked |
