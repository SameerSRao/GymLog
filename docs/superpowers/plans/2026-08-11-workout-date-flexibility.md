# Workout Date Flexibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pick a workout date when logging, and edit the date+time of an existing workout.

**Architecture:** Frontend-only changes to `index.html` (log page) and `workout.html` (edit page). The backend already accepts an optional `logged_at` field on both POST `/api/workouts` and PUT `/api/workout/{id}`. No new files are created.

**Tech Stack:** Vanilla JS, HTML, inline `<style>` blocks — no framework, no dependencies.

## Global Constraints

- No backend changes — `WorkoutRequest.logged_at` is already `datetime | None` on create and present on update.
- Follow existing code style: inline JS in `<script>` blocks, CSS in `<style>` blocks, no external libraries.
- Error feedback: `index.html` uses `showToast(msg, type)`. `workout.html` uses `alert(msg)` — match each page's existing pattern.
- `logged_at` sent to the API must be a local ISO string without timezone offset, e.g. `"2026-08-10T00:00:00"` — same format as the existing `localISOString()` helper.

---

## File Map

- Modify: `app/static/index.html` — add date input to log form, update `submitWorkout()`
- Modify: `app/static/workout.html` — add date+time inputs, update `enterEditMode()`, `exitEditMode()`, `saveWorkout()`

---

## Task 1: Date picker on the log page (`index.html`)

**Files:**
- Modify: `app/static/index.html`

**Interfaces:**
- Produces: `workout-date-input` (`<input type="date">`) element readable by `submitWorkout()`

### Steps

- [ ] **Step 1: Add the date input to the HTML**

  In `index.html`, find the `<div id="exercises"></div>` block (around line 456). Insert a date input directly above it:

  ```html
  <div class="log-date-row">
    <label class="log-date-label" for="workout-date-input">Workout Date</label>
    <input type="date" id="workout-date-input" class="log-date-input" />
  </div>
  <div id="exercises"></div>
  ```

- [ ] **Step 2: Add CSS for the date input**

  In the `<style>` block, add after the `.notes-textarea` rules:

  ```css
  .log-date-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }
  .log-date-label {
    font-size: 0.85rem;
    color: #888;
    white-space: nowrap;
  }
  .log-date-input {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 6px 10px;
    font-size: 0.9rem;
    color-scheme: dark;
  }
  .log-date-input:focus { outline: none; border-color: #555; }
  ```

- [ ] **Step 3: Set the default value to today's local date**

  `localISOString()` is already defined around line 487 and returns the current local datetime as `"YYYY-MM-DDTHH:MM:SS"`. After it, add an IIFE to set the input's default:

  ```js
  function localISOString() {
    const d = new Date();
    return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
  }
  // Set workout date input to today's local date on load
  (function () {
    const el = document.getElementById('workout-date-input');
    if (el) el.value = localISOString().slice(0, 10);
  })();
  ```

- [ ] **Step 4: Update `submitWorkout()` to read the date input and validate**

  Find the `submitWorkout` function. Near the top where it reads `notes`, add date logic. Replace:

  ```js
  body: JSON.stringify({ exercises, notes, logged_at: localISOString() }),
  ```

  With:

  ```js
  const dateVal = document.getElementById('workout-date-input').value;
  let loggedAt;
  if (dateVal) {
    const chosen = new Date(dateVal + 'T00:00:00');
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    if (chosen > now) {
      showToast('Workout date cannot be in the future', 'error');
      return;
    }
    loggedAt = dateVal + 'T00:00:00';
  } else {
    loggedAt = localISOString();
  }
  // ...existing btn.disabled / btn.textContent lines...
  body: JSON.stringify({ exercises, notes, logged_at: loggedAt }),
  ```

  The full block surrounding the fetch should look like:

  ```js
  const notes = document.getElementById('workout-notes-input').value.trim() || null;

  const dateVal = document.getElementById('workout-date-input').value;
  let loggedAt;
  if (dateVal) {
    const chosen = new Date(dateVal + 'T00:00:00');
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    if (chosen > now) {
      showToast('Workout date cannot be in the future', 'error');
      return;
    }
    loggedAt = dateVal + 'T00:00:00';
  } else {
    loggedAt = localISOString();
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Logging...';

  try {
    const res = await authFetch('/api/workouts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercises, notes, logged_at: loggedAt }),
    });
  ```

- [ ] **Step 5: Reset the date input to today after successful submit**

  Inside the `try` block of `submitWorkout()`, after clearing other fields, reset the date:

  ```js
  document.getElementById('workout-notes-input').value = '';
  document.getElementById('workout-date-input').value = localISOString().slice(0, 10);
  setCounts = {};
  ```

- [ ] **Step 6: Manual test**

  - Open `http://localhost:8000` (run `docker compose up --build` if not running).
  - Verify the "Workout Date" label and date input appear above the exercise list, defaulting to today.
  - Set the date to tomorrow → click "Log Workout" → toast shows "Workout date cannot be in the future".
  - Clear the date → log a workout → succeeds, date resets to today.
  - Set the date to yesterday → log a workout → succeeds, workout detail page shows yesterday's date.

- [ ] **Step 7: Commit**

  ```bash
  git add app/static/index.html
  git commit -m "feat: add date picker to workout log page"
  ```

---

## Task 2: Date + time pickers on the edit page (`workout.html`)

**Files:**
- Modify: `app/static/workout.html`

**Interfaces:**
- Consumes: `workout.logged_at` (string, e.g. `"2026-08-10T18:30:00"`) from the loaded workout object
- Produces: `edit-date-input` and `edit-time-input` elements read by `saveWorkout()`

### Steps

- [ ] **Step 1: Add the date+time inputs to the HTML**

  In `workout.html`, find the `<textarea id="edit-notes" ...>` element (around line 493). Insert the date+time row directly above it (it will be hidden by default, shown only in edit mode):

  ```html
  <div id="edit-datetime-row" style="display:none; margin-bottom:14px;">
    <label class="edit-label">Date &amp; Time</label>
    <div style="display:flex; gap:8px;">
      <input type="date" id="edit-date-input" class="edit-input" style="flex:1;" />
      <input type="time" id="edit-time-input" class="edit-input" style="flex:1;" />
    </div>
  </div>
  <textarea id="edit-notes" class="notes-textarea" placeholder="Notes (optional)" rows="3" style="display:none"></textarea>
  ```

  The `edit-input` and `edit-label` CSS classes already exist in the page's `<style>` block and will style these inputs correctly. Add `color-scheme: dark;` to `.edit-input` if date/time inputs render with a light background:

  ```css
  .edit-input { color-scheme: dark; }
  ```

  (Add this line to the existing `.edit-input` rule, not as a duplicate rule.)

- [ ] **Step 2: Show and pre-populate inputs in `enterEditMode()`**

  Find `enterEditMode()`. After the line that shows `edit-notes`:

  ```js
  const editNotes = document.getElementById('edit-notes');
  editNotes.value = workout.notes || '';
  editNotes.style.display = 'block';
  ```

  Add:

  ```js
  const dtRow = document.getElementById('edit-datetime-row');
  dtRow.style.display = 'block';
  // Pre-populate from workout.logged_at e.g. "2026-08-10T18:30:00"
  const [datePart, timePart] = (workout.logged_at || '').split('T');
  document.getElementById('edit-date-input').value = datePart || '';
  document.getElementById('edit-time-input').value = (timePart || '').slice(0, 5); // "HH:MM"
  ```

- [ ] **Step 3: Hide inputs in `exitEditMode()`**

  Find `exitEditMode()`. After the line that hides `edit-notes`:

  ```js
  document.getElementById('edit-notes').style.display = 'none';
  ```

  Add:

  ```js
  document.getElementById('edit-datetime-row').style.display = 'none';
  ```

- [ ] **Step 4: Read, validate, and send `logged_at` in `saveWorkout()`**

  Find `saveWorkout()`. After the line that reads notes:

  ```js
  const notes = document.getElementById('edit-notes').value.trim() || null;
  ```

  Add:

  ```js
  const editDate = document.getElementById('edit-date-input').value;
  const editTime = document.getElementById('edit-time-input').value;

  if (!editDate || !editTime) {
    alert('Date and time are required');
    return;
  }

  const chosenDt = new Date(editDate + 'T' + editTime + ':00');
  if (chosenDt > new Date()) {
    alert('Workout date cannot be in the future');
    return;
  }

  const loggedAt = editDate + 'T' + editTime + ':00';
  ```

  Then in the `authFetch` PUT call, replace:

  ```js
  body: JSON.stringify({ exercises, notes }),
  ```

  With:

  ```js
  body: JSON.stringify({ exercises, notes, logged_at: loggedAt }),
  ```

- [ ] **Step 5: Manual test**

  - Open any existing workout's detail page (e.g. `http://localhost:8000/workout/1`).
  - Click "Edit" — verify date and time inputs appear, pre-filled with the workout's current date and time.
  - Click "Cancel" — verify the inputs disappear.
  - Click "Edit" again, set the date to tomorrow → click "Save" → alert shows "Workout date cannot be in the future".
  - Clear the time field → click "Save" → alert shows "Date and time are required".
  - Set a valid past date+time → click "Save" → workout header updates to the new date.

- [ ] **Step 6: Commit**

  ```bash
  git add app/static/workout.html
  git commit -m "feat: add date+time pickers to workout edit mode"
  ```
