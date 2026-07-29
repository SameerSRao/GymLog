from app.model.models import MuscleGroup, ExerciseDef


def make_muscle_group(db, name="pectorals"):
    mg = MuscleGroup(name=name)
    db.add(mg)
    db.commit()
    db.refresh(mg)
    return mg


def make_exercise(db, name="Bench Press", equipment="barbell",
                  instructions="Press the bar up", muscle_groups=None):
    ex = ExerciseDef(
        name=name,
        equipment=equipment,
        instructions=instructions,
        muscle_groups=muscle_groups or [],
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


# ---------------------------------------------------------------------------
# GET /api/exercises
# ---------------------------------------------------------------------------

def test_list_exercises_empty(client):
    r = client.get("/api/exercises")
    assert r.status_code == 200
    assert r.json() == []


def test_list_exercises_returns_all(client, db):
    make_exercise(db, name="Bench Press")
    make_exercise(db, name="Squat")
    r = client.get("/api/exercises")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for item in data:
        assert {"id", "name", "equipment", "instructions", "muscle_groups"}.issubset(item.keys())


def test_list_exercises_includes_muscle_groups(client, db):
    mg = make_muscle_group(db, name="pectorals")
    make_exercise(db, name="Bench Press", muscle_groups=[mg])
    r = client.get("/api/exercises")
    assert r.status_code == 200
    mgs = r.json()[0]["muscle_groups"]
    assert len(mgs) == 1
    assert mgs[0]["id"] == mg.id
    assert mgs[0]["name"] == "pectorals"


# ---------------------------------------------------------------------------
# POST /api/exercises
# ---------------------------------------------------------------------------

def test_create_exercise(client, db):
    mg = make_muscle_group(db)
    r = client.post("/api/exercises", json={
        "name": "Custom Press",
        "equipment": "dumbbell",
        "instructions": "Push up",
        "muscle_group_ids": [mg.id],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Custom Press"
    assert len(data["muscle_groups"]) == 1


def test_create_exercise_no_muscle_groups(client):
    r = client.post("/api/exercises", json={"name": "Plank", "muscle_group_ids": []})
    assert r.status_code == 201
    data = r.json()
    assert data["muscle_groups"] == []
    assert data["equipment"] is None


def test_create_exercise_invalid_muscle_group_id(client):
    r = client.post("/api/exercises", json={"name": "Bad Exercise", "muscle_group_ids": [9999]})
    assert r.status_code == 400


def test_create_exercise_missing_name(client):
    r = client.post("/api/exercises", json={"muscle_group_ids": []})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/info
# ---------------------------------------------------------------------------

def test_get_exercise_info(client, db):
    ex = make_exercise(db, name="Bench Press", equipment="barbell", instructions="Press up")
    r = client.get(f"/api/exercise/{ex.id}/info")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press up"


def test_get_exercise_info_not_found(client):
    r = client.get("/api/exercise/9999/info")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_update_exercise_name(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Incline Bench Press"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Incline Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press the bar up"


def test_update_exercise_muscle_groups(client, db):
    mg1 = make_muscle_group(db, name="pectorals")
    mg2 = make_muscle_group(db, name="triceps")
    ex = make_exercise(db, muscle_groups=[mg1])
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [mg2.id]})
    assert r.status_code == 200
    data = r.json()
    assert len(data["muscle_groups"]) == 1
    assert data["muscle_groups"][0]["id"] == mg2.id


def test_update_exercise_multiple_fields(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={
        "name": "New Name",
        "equipment": "cable",
        "instructions": "Pull down",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "New Name"
    assert data["equipment"] == "cable"
    assert data["instructions"] == "Pull down"


def test_update_exercise_not_found(client):
    r = client.put("/api/exercise/9999", json={"name": "Ghost"})
    assert r.status_code == 404


def test_update_exercise_name_conflict(client, db):
    make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.put(f"/api/exercise/{ex_b.id}", json={"name": "Bench Press"})
    assert r.status_code == 409


def test_update_exercise_same_name_no_conflict(client, db):
    ex = make_exercise(db, name="Bench Press")
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Bench Press"})
    assert r.status_code == 200


def test_update_exercise_invalid_muscle_group_id(client, db):
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [9999]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_delete_exercise(client, db):
    ex = make_exercise(db)
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 204
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 404


def test_delete_exercise_not_found(client):
    r = client.delete("/api/exercise/9999")
    assert r.status_code == 404


def test_delete_exercise_with_history(client, db):
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 409
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 200


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/progression
# ---------------------------------------------------------------------------

def test_progression_no_history(client, db):
    ex = make_exercise(db, name="Bench Press")
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == []
    assert data["exercise_name"] == "Bench Press"


def test_progression_with_history(client, db):
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]}],
        "logged_at": "2026-01-01T08:00:00",
    })
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 110}]}],
        "logged_at": "2026-01-15T08:00:00",
    })
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert len(data["sessions"]) == 2
    s0, s1 = data["sessions"]
    assert s0["logged_at"] < s1["logged_at"]
    for s in data["sessions"]:
        assert "sets" in s
        assert "volume" in s
        assert "best_set_weight" in s


def test_progression_not_found(client):
    r = client.get("/api/exercise/9999/progression")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/muscle-groups
# ---------------------------------------------------------------------------

def test_list_muscle_groups_empty(client):
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    assert r.json() == []


def test_list_muscle_groups(client, db):
    for name in ["traps", "abs", "chest"]:
        make_muscle_group(db, name=name)
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    names = [item["name"] for item in data]
    assert names == sorted(names)
