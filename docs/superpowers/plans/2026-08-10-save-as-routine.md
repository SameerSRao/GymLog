# Save as Routine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Save as Routine" button to the log workout page that
captures the current exercise list and set counts into a new routine via
POST /api/routines.

**Architecture:** Single file edit to `app/static/index.html`. A hidden
button is inserted between the notes textarea and "Log Workout." A
`updateSaveRoutineBtn()` helper toggles its visibility whenever exercises
are added or removed. `saveAsRoutine()` validates, prompts for a name, and
POSTs to the routines API.

**Tech Stack:** Vanilla JS, HTML. FastAPI backend already provides
POST /api/routines.

## Global Constraints

- File to edit: `app/static/index.html` only — no backend changes.
- Button element id: `saveRoutineBtn`
- Button label: `Save as Routine`
- Visibility helper name: `updateSaveRoutineBtn()`
- Save function name: `saveAsRoutine()`
- Button styling: reuse existing `.btn-new-exercise` CSS class, `width:100%`, `margin-bottom:12px`
- Error toast strings must match exactly:
  - Unselected exercise: `'Select all exercises from the list before saving as a routine'`
  - 409 conflict: `` `A routine named "${trimmed}" already exists` ``
  - Other error: `'Failed to save routine'`
- Success toast: `` `"${trimmed}" saved as routine` ``
- Prompt string: `'Routine name:'`

---

### Task 1: Button HTML and visibility helper

**Files:**
- Modify: `app/static/index.html:409-410` (HTML), `app/static/index.html:639-689` (JS)

**Interfaces:**
- Produces: `updateSaveRoutineBtn()` — called by `addExercise()` and
  `removeExercise()` to show/hide `#saveRoutineBtn`.

- [ ] **Step 1: Insert the button HTML**

  Open `app/static/index.html`. Find line 409:
  ```html
  <textarea id="workout-notes-input" class="notes-textarea" ...
  ```
  Insert the button **between** the textarea and the submit button so the
  order becomes: textarea → Save as Routine button → Log Workout button.

  The button to insert:
  ```html
  <button
    class="btn-new-exercise"
    id="saveRoutineBtn"
    style="display:none; width:100%; margin-bottom:12px;"
    onclick="saveAsRoutine()"
  >Save as Routine</button>
  ```

- [ ] **Step 2: Add `updateSaveRoutineBtn()` to the JS**

  In the `<script>` block, add this function in the
  `// ── Exercise blocks ──` section, just before `function addExercise()`:

  ```js
  function updateSaveRoutineBtn() {
    const hasBlocks =
      document.querySelectorAll('#exercises .exercise-block').length > 0;
    document.getElementById('saveRoutineBtn').style.display =
      hasBlocks ? 'block' : 'none';
  }
  ```

- [ ] **Step 3: Call `updateSaveRoutineBtn()` at the end of `addExercise()`**

  Find the end of `addExercise()` (currently around line 684). It ends
  with `return id;`. Add the call on the line immediately before `return`:

  ```js
      document.getElementById('exercises').appendChild(div);
      addSet(id);
      updateSaveRoutineBtn();   // ← add this line
      return id;
    }
  ```

- [ ] **Step 4: Call `updateSaveRoutineBtn()` at the end of `removeExercise()`**

  Find `function removeExercise(id)` (around line 687). It currently
  contains only one line. Add the call after the remove:

  ```js
  function removeExercise(id) {
    document.getElementById(`exercise-${id}`).remove();
    updateSaveRoutineBtn();
  }
  ```

- [ ] **Step 5: Verify in the browser**

  Start the dev server if not already running:
  ```bash
  source .venv/bin/activate
  DATABASE_URL="sqlite:////$(pwd)/data/gymlog.db" uvicorn app.main:app --reload --port 8001
  ```
  Open `http://localhost:8001/`.

  - Page loads → "Save as Routine" button is **hidden** (the initial
    `addExercise()` call immediately shows it — confirm it IS visible
    after page load, because `init()` calls `addExercise()`).
  - Add a second exercise block → button remains visible.
  - Remove exercise blocks one by one until zero remain → button hides.
  - Add one back → button reappears.

- [ ] **Step 6: Commit**

  ```bash
  git add app/static/index.html
  git commit -m "feat: add Save as Routine button with show/hide helper"
  ```

---

### Task 2: `saveAsRoutine()` function

**Files:**
- Modify: `app/static/index.html` (add `saveAsRoutine()` to the JS)

**Interfaces:**
- Consumes: `updateSaveRoutineBtn()` from Task 1 (already wired to the
  button's `onclick`).
- Consumes: existing `showToast(msg, type)` — `type` is `'success'` or
  `'error'`.
- Consumes: existing `#exercises .exercise-block` DOM structure where each
  block has id `exercise-{n}`, a name input `name-{n}` with
  `dataset.exerciseId`, and a sets tbody `sets-{n}`.

- [ ] **Step 1: Add `saveAsRoutine()` to the JS**

  In the `<script>` block, add the function in the
  `// ── Load routine ──` section, directly after `loadRoutine()`:

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

- [ ] **Step 2: Verify — unselected exercise is blocked**

  Open `http://localhost:8001/`. Type "bench" in the exercise name field
  but do **not** click a result from the dropdown. Click "Save as Routine."
  Expected: red toast `'Select all exercises from the list before saving
  as a routine'`. No prompt appears.

- [ ] **Step 3: Verify — prompt cancel and blank are silent**

  Select a real exercise from the dropdown (e.g. "barbell bench press").
  Click "Save as Routine." When the prompt appears, click Cancel.
  Expected: nothing happens, no toast.

  Click "Save as Routine" again, type nothing (leave blank), click OK.
  Expected: nothing happens, no toast.

- [ ] **Step 4: Verify — successful save**

  Click "Save as Routine," enter "My Test Routine," click OK.
  Expected: green toast `'"My Test Routine" saved as routine'`.

  Confirm the routine was created: open `http://localhost:8001/api/routines`
  in a new tab and verify "My Test Routine" appears in the list.

- [ ] **Step 5: Verify — 409 name conflict**

  Click "Save as Routine" again and enter "My Test Routine" (same name).
  Expected: red toast `'A routine named "My Test Routine" already exists'`.

- [ ] **Step 6: Verify — set count is captured correctly**

  Add a second exercise, select it from the dropdown, then click
  "+ Add Set" twice so it has 3 sets. Save as a new routine (e.g. "Two
  Exercise Routine"). Check `http://localhost:8001/api/routines`, click
  into that routine's detail and verify `num_sets` matches what was in
  the form.

- [ ] **Step 7: Verify — Load Routine select now lists the saved routine**

  Reload `http://localhost:8001/`. The "Load Routine…" select should now
  show "My Test Routine (1 exercise)" and "Two Exercise Routine (2
  exercises)".

- [ ] **Step 8: Commit**

  ```bash
  git add app/static/index.html
  git commit -m "feat: implement saveAsRoutine() with validation and toast feedback"
  ```
