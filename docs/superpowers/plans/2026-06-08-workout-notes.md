# Workout Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing `raw_input` column on `workout_sessions` as a user-facing notes field — writable on the log form, displayed on the workout detail page, and editable via the existing edit mode.

**Architecture:** Backend adds `notes` to `WorkoutRequest` and `WorkoutDetailed` schemas and wires it through the service and route layers. Frontend adds a textarea to `index.html` and to `workout.html`'s edit mode, and displays notes in the workout header when present. No migration needed — `Workout.raw_input` is already `Optional[str]` on the model.

**Tech Stack:** FastAPI + Pydantic (backend), Vanilla JS/HTML/CSS (frontend).

---

## File Structure

| File | Change |
|------|--------|
| `app/api/schemas.py` | Add `notes: Optional[str] = None` to `WorkoutRequest` and `WorkoutDetailed` |
| `app/services/workout_service.py` | Write `workout.notes` to `session.raw_input` in `log_workout` and `update_workout` |
| `app/api/routes.py` | Include `notes=session.raw_input` in `_build_workout_detailed` |
| `app/static/index.html` | Add notes textarea + CSS; include `notes` in `submitWorkout()` body |
| `app/static/workout.html` | Show notes in view mode; textarea pre-populated in edit mode; include `notes` in `saveWorkout()` |

---

### Task 1: Backend — schemas, service, routes

**Files:**
- Modify: `app/api/schemas.py`
- Modify: `app/services/workout_service.py`
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add `notes` to `WorkoutRequest` in `app/api/schemas.py`**

Find:
```python
class WorkoutRequest(BaseModel):
    exercises: list[ExerciseLogRequest]
```

Replace with:
```python
class WorkoutRequest(BaseModel):
    exercises: list[ExerciseLogRequest]
    notes: Optional[str] = None
```

- [ ] **Step 2: Add `notes` to `WorkoutDetailed` in `app/api/schemas.py`**

Find:
```python
class WorkoutDetailed(BaseModel):
    session_id: int
    logged_at: datetime
    exercises: list[ExerciseSchema]
```

Replace with:
```python
class WorkoutDetailed(BaseModel):
    session_id: int
    logged_at: datetime
    notes: Optional[str] = None
    exercises: list[ExerciseSchema]
```

- [ ] **Step 3: Write `notes` to `raw_input` in `log_workout` in `app/services/workout_service.py`**

Find:
```python
def log_workout(db: Session, workout: WorkoutRequest) -> Workout:
    session = Workout()
    db.add(session)
```

Replace with:
```python
def log_workout(db: Session, workout: WorkoutRequest) -> Workout:
    session = Workout(raw_input=workout.notes)
    db.add(session)
```

- [ ] **Step 4: Write `notes` to `raw_input` in `update_workout` in `app/services/workout_service.py`**

Find:
```python
def update_workout(db: Session, session_id: int, workout: WorkoutRequest) -> Optional[Workout]:
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return None

    db.query(Exercise).filter(Exercise.session_id == session_id).delete()
```

Replace with:
```python
def update_workout(db: Session, session_id: int, workout: WorkoutRequest) -> Optional[Workout]:
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return None

    session.raw_input = workout.notes
    db.query(Exercise).filter(Exercise.session_id == session_id).delete()
```

- [ ] **Step 5: Include `notes` in `_build_workout_detailed` in `app/api/routes.py`**

Find:
```python
    return WorkoutDetailed(session_id=session.id, logged_at=session.logged_at, exercises=exercises)
```

Replace with:
```python
    return WorkoutDetailed(session_id=session.id, logged_at=session.logged_at, notes=session.raw_input, exercises=exercises)
```

- [ ] **Step 6: Commit**

```bash
git add app/api/schemas.py app/services/workout_service.py app/api/routes.py
git commit -m "feat: add notes field to WorkoutRequest and WorkoutDetailed, wire to raw_input"
```

---

### Task 2: Log form — `app/static/index.html`

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add `.notes-textarea` CSS**

In `app/static/index.html`, find the `<style>` block. Find this rule (around line 182):
```css
    .btn-add-exercise:hover { border-color: #555; color: #aaa; }
```

Add these rules immediately after it:
```css

    .notes-textarea {
      width: 100%;
      background: #111;
      border: 1px solid #333;
      border-radius: 8px;
      color: #f0f0f0;
      font-size: 0.9rem;
      font-family: system-ui, sans-serif;
      padding: 10px 12px;
      resize: vertical;
      margin-bottom: 16px;
      display: block;
    }
    .notes-textarea:focus { outline: none; border-color: #555; }
```

- [ ] **Step 2: Add notes textarea between `+ Add Exercise` and `Log Workout` buttons**

Find:
```html
  <button class="btn-add-exercise" onclick="addExercise()">+ Add Exercise</button>
  <button class="btn-submit" id="submitBtn" onclick="submitWorkout()">Log Workout</button>
```

Replace with:
```html
  <button class="btn-add-exercise" onclick="addExercise()">+ Add Exercise</button>
  <textarea id="workout-notes-input" class="notes-textarea" placeholder="Notes (optional)" rows="3"></textarea>
  <button class="btn-submit" id="submitBtn" onclick="submitWorkout()">Log Workout</button>
```

- [ ] **Step 3: Include `notes` in the `submitWorkout()` body**

In `app/static/index.html`, find the `submitWorkout` function. Find this block (around line 741):
```js
      if (exercises.length === 0) { showToast('Add at least one exercise', 'error'); return; }

      const btn = document.getElementById('submitBtn');
```

Replace with:
```js
      if (exercises.length === 0) { showToast('Add at least one exercise', 'error'); return; }

      const notes = document.getElementById('workout-notes-input').value.trim() || null;
      const btn = document.getElementById('submitBtn');
```

Then find the fetch body (around line 752):
```js
          body: JSON.stringify({ exercises }),
```

Replace with:
```js
          body: JSON.stringify({ exercises, notes }),
```

- [ ] **Step 4: Clear the notes textarea after a successful submit**

In the same `submitWorkout` function, find the block that resets the form after success (around line 759):
```js
        document.getElementById('exercises').innerHTML = '';
        setCounts = {};
        exerciseCount = 0;
        addExercise();
```

Replace with:
```js
        document.getElementById('exercises').innerHTML = '';
        document.getElementById('workout-notes-input').value = '';
        setCounts = {};
        exerciseCount = 0;
        addExercise();
```

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat: add notes textarea to log form"
```

---

### Task 3: Workout detail page — `app/static/workout.html`

**Files:**
- Modify: `app/static/workout.html`

- [ ] **Step 1: Add `.workout-notes` and `.notes-textarea` CSS**

In `app/static/workout.html`, find the `<style>` block. Find this rule (around line 36):
```css
    .workout-meta { font-size: 0.82rem; color: #555; margin-top: 4px; }
```

Add these rules immediately after it:
```css
    .workout-notes { font-size: 0.82rem; color: #888; margin-top: 6px; line-height: 1.5; white-space: pre-wrap; }

    .notes-textarea {
      width: 100%;
      background: #111;
      border: 1px solid #333;
      border-radius: 8px;
      color: #f0f0f0;
      font-size: 0.9rem;
      font-family: system-ui, sans-serif;
      padding: 10px 12px;
      resize: vertical;
      margin-top: 16px;
      display: block;
    }
    .notes-textarea:focus { outline: none; border-color: #555; }
```

- [ ] **Step 2: Add notes paragraph to view mode HTML**

In `app/static/workout.html`, find:
```html
        <h1 id="workout-date"></h1>
        <p class="workout-meta" id="workout-meta"></p>
```

Replace with:
```html
        <h1 id="workout-date"></h1>
        <p class="workout-meta" id="workout-meta"></p>
        <p class="workout-notes" id="workout-notes" style="display:none"></p>
```

- [ ] **Step 3: Add notes textarea to edit mode HTML**

In `app/static/workout.html`, find:
```html
    <div id="edit-exercise-container" style="display:none"></div>
    <button id="edit-add-exercise-btn" class="btn-add-exercise" onclick="addExercise()" style="display:none">+ Add Exercise</button>
```

Replace with:
```html
    <div id="edit-exercise-container" style="display:none"></div>
    <button id="edit-add-exercise-btn" class="btn-add-exercise" onclick="addExercise()" style="display:none">+ Add Exercise</button>
    <textarea id="edit-notes" class="notes-textarea" placeholder="Notes (optional)" rows="3" style="display:none"></textarea>
```

- [ ] **Step 4: Show notes in `renderWorkout`**

In `app/static/workout.html`, find the `renderWorkout` function. Find this block:
```js
      const totalSets = w.exercises.reduce((n, e) => n + e.sets.length, 0);
      document.getElementById('workout-meta').textContent =
        `${w.exercises.length} exercise${w.exercises.length !== 1 ? 's' : ''} · ${totalSets} sets`;
```

Replace with:
```js
      const totalSets = w.exercises.reduce((n, e) => n + e.sets.length, 0);
      document.getElementById('workout-meta').textContent =
        `${w.exercises.length} exercise${w.exercises.length !== 1 ? 's' : ''} · ${totalSets} sets`;

      const notesEl = document.getElementById('workout-notes');
      if (w.notes) {
        notesEl.textContent = w.notes;
        notesEl.style.display = 'block';
      } else {
        notesEl.style.display = 'none';
      }
```

- [ ] **Step 5: Pre-populate notes textarea in `enterEditMode`**

In `app/static/workout.html`, find the `enterEditMode` function. Find this block at the end of the function:
```js
      for (const ex of workout.exercises) {
        addExercise({ exercise_id: ex.exercise_id, name: ex.name, sets: ex.sets });
      }
    }
```

Replace with:
```js
      for (const ex of workout.exercises) {
        addExercise({ exercise_id: ex.exercise_id, name: ex.name, sets: ex.sets });
      }

      const editNotes = document.getElementById('edit-notes');
      editNotes.value = workout.notes || '';
      editNotes.style.display = 'block';
    }
```

- [ ] **Step 6: Hide notes textarea in `exitEditMode`**

In `app/static/workout.html`, find the `exitEditMode` function:
```js
    function exitEditMode() {
      document.getElementById('view-actions').style.display = 'flex';
      document.getElementById('edit-actions').style.display = 'none';

      document.getElementById('exercises').style.display = 'block';
      document.getElementById('edit-exercise-container').style.display = 'none';
      document.getElementById('edit-add-exercise-btn').style.display = 'none';

      renderWorkout(workout);
    }
```

Replace with:
```js
    function exitEditMode() {
      document.getElementById('view-actions').style.display = 'flex';
      document.getElementById('edit-actions').style.display = 'none';

      document.getElementById('exercises').style.display = 'block';
      document.getElementById('edit-exercise-container').style.display = 'none';
      document.getElementById('edit-add-exercise-btn').style.display = 'none';
      document.getElementById('edit-notes').style.display = 'none';

      renderWorkout(workout);
    }
```

- [ ] **Step 7: Include `notes` in the `saveWorkout` PUT body**

In `app/static/workout.html`, find the `saveWorkout` function. Find:
```js
      if (exercises.length === 0) { alert('Add at least one exercise'); return; }

      const saveBtn = document.querySelector('.btn-save');
```

Replace with:
```js
      if (exercises.length === 0) { alert('Add at least one exercise'); return; }

      const notes = document.getElementById('edit-notes').value.trim() || null;
      const saveBtn = document.querySelector('.btn-save');
```

Then find the fetch body:
```js
          body: JSON.stringify({ exercises }),
```

Replace with:
```js
          body: JSON.stringify({ exercises, notes }),
```

- [ ] **Step 8: Commit**

```bash
git add app/static/workout.html
git commit -m "feat: display and edit workout notes on workout detail page"
```

---

### Task 4: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Start the app**

```bash
docker compose up --build
```

- [ ] **Step 2: Log a workout with notes**

Open `http://localhost:8000/log`. Add at least one exercise, fill in the notes textarea (e.g. `"Felt strong today. PR on bench."`), then click "Log Workout".

Confirm:
- Toast shows success
- Notes textarea is cleared after submit

- [ ] **Step 3: Verify notes appear on the workout detail page**

Click "View workout →" link (shown after submit) to go to `/workout/{session_id}`.

Confirm:
- Notes appear below the "X exercises · Y sets" meta line in the workout header
- Notes text matches what was typed

- [ ] **Step 4: Verify notes without a value don't render**

Log a second workout with no notes. Open its detail page.

Confirm: no notes paragraph appears (the element stays hidden).

- [ ] **Step 5: Edit a workout and update notes**

On any workout detail page, click "Edit". Confirm:
- The notes textarea appears below the exercise list, pre-populated with existing notes
- Clearing or changing notes and clicking "Save" reflects the change in view mode

- [ ] **Step 6: Verify the API response includes notes**

```bash
curl -s http://localhost:8000/api/workout/1 | python3 -m json.tool | grep notes
```

Expected: `"notes": "Felt strong today. PR on bench."` (or `"notes": null` for a workout without notes)
