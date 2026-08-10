from conftest import make_exercise, make_muscle_group


# ---------------------------------------------------------------------------
# GET /api/exercises
# ---------------------------------------------------------------------------

def test_list_exercises_empty(client):
    """Assert GET /api/exercises returns an empty list when no exercises exist."""
    r = client.get("/api/exercises")
    assert r.status_code == 200
    assert r.json() == []


def test_list_exercises_returns_all(client, db):
    """Assert GET /api/exercises returns all exercises with expected fields."""
    make_exercise(db, name="Bench Press")
    make_exercise(db, name="Squat")
    r = client.get("/api/exercises")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for item in data:
        assert {"id", "name", "equipment", "instructions", "muscle_groups"}.issubset(
            item.keys()
        )


def test_list_exercises_includes_muscle_groups(client, db):
    """Assert GET /api/exercises returns linked muscle groups with correct id and name."""
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
    """Assert POST /api/exercises creates the exercise and returns it with muscle groups."""
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
    """Assert POST /api/exercises succeeds with empty muscle_group_ids and null equipment."""
    r = client.post("/api/exercises", json={"name": "Plank", "muscle_group_ids": []})
    assert r.status_code == 201
    data = r.json()
    assert data["muscle_groups"] == []
    assert data["equipment"] is None


def test_create_exercise_invalid_muscle_group_id(client):
    """Assert POST /api/exercises returns 400 for a non-existent muscle group ID."""
    r = client.post(
        "/api/exercises",
        json={"name": "Bad Exercise", "muscle_group_ids": [9999]},
    )
    assert r.status_code == 400


def test_create_exercise_missing_name(client):
    """Assert POST /api/exercises returns 422 when the required name field is absent."""
    r = client.post("/api/exercises", json={"muscle_group_ids": []})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/info
# ---------------------------------------------------------------------------

def test_get_exercise_info(client, db):
    """Assert GET /api/exercise/{id}/info returns the correct exercise fields."""
    ex = make_exercise(
        db, name="Bench Press", equipment="barbell", instructions="Press up"
    )
    r = client.get(f"/api/exercise/{ex.id}/info")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press up"


def test_get_exercise_info_not_found(client):
    """Assert GET /api/exercise/{id}/info returns 404 for an unknown ID."""
    r = client.get("/api/exercise/9999/info")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_update_exercise_name(client, db):
    """Assert PUT /api/exercise/{id} updates the name while leaving other fields unchanged."""
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Incline Bench Press"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Incline Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press the bar up"


def test_update_exercise_muscle_groups(client, db):
    """Assert PUT /api/exercise/{id} replaces the exercise's muscle group list."""
    mg1 = make_muscle_group(db, name="pectorals")
    mg2 = make_muscle_group(db, name="triceps")
    ex = make_exercise(db, muscle_groups=[mg1])
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [mg2.id]})
    assert r.status_code == 200
    data = r.json()
    assert len(data["muscle_groups"]) == 1
    assert data["muscle_groups"][0]["id"] == mg2.id


def test_update_exercise_multiple_fields(client, db):
    """Assert PUT /api/exercise/{id} can update name, equipment, and instructions together."""
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
    """Assert PUT /api/exercise/{id} returns 404 for an unknown ID."""
    r = client.put("/api/exercise/9999", json={"name": "Ghost"})
    assert r.status_code == 404


def test_update_exercise_name_conflict(client, db):
    """Assert PUT /api/exercise/{id} returns 409 when the new name is already taken."""
    make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.put(f"/api/exercise/{ex_b.id}", json={"name": "Bench Press"})
    assert r.status_code == 409


def test_update_exercise_same_name_no_conflict(client, db):
    """Assert PUT /api/exercise/{id} returns 200 when the name is unchanged."""
    ex = make_exercise(db, name="Bench Press")
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "Bench Press"})
    assert r.status_code == 200


def test_update_exercise_invalid_muscle_group_id(client, db):
    """Assert PUT /api/exercise/{id} returns 400 for a non-existent muscle group ID."""
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [9999]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/exercise/{id}
# ---------------------------------------------------------------------------

def test_delete_exercise(client, db):
    """Assert DELETE /api/exercise/{id} removes the exercise and returns 204."""
    ex = make_exercise(db)
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 204
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 404


def test_delete_exercise_not_found(client):
    """Assert DELETE /api/exercise/{id} returns 404 for an unknown ID."""
    r = client.delete("/api/exercise/9999")
    assert r.status_code == 404


def test_delete_exercise_with_history(client, db):
    """Assert DELETE /api/exercise/{id} returns 409 and leaves the exercise intact when it has logged history."""
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
    """Assert GET /api/exercise/{id}/progression returns empty sessions when no workouts exist."""
    ex = make_exercise(db, name="Bench Press")
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == []
    assert data["exercise_name"] == "Bench Press"


def test_progression_with_history(client, db):
    """Assert GET /api/exercise/{id}/progression returns sessions in chronological order with aggregates."""
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
    """Assert GET /api/exercise/{id}/progression returns 404 for an unknown ID."""
    r = client.get("/api/exercise/9999/progression")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/muscle-groups
# ---------------------------------------------------------------------------

def test_list_muscle_groups_empty(client):
    """Assert GET /api/muscle-groups returns an empty list when no muscle groups exist."""
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    assert r.json() == []


def test_list_muscle_groups(client, db):
    """Assert GET /api/muscle-groups returns all muscle groups in alphabetical order."""
    for name in ["traps", "abs", "chest"]:
        make_muscle_group(db, name=name)
    r = client.get("/api/muscle-groups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    names = [item["name"] for item in data]
    assert names == sorted(names)
