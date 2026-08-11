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
        assert {
            "id", "name", "equipment", "instructions", "muscle_groups"
        }.issubset(item.keys())


def test_list_exercises_includes_muscle_groups(client, db):
    """Assert GET /api/exercises returns linked muscle groups with id and name."""
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
    """Assert POST /api/exercises creates the exercise and returns it."""
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
    """Assert POST /api/exercises succeeds with empty muscle_group_ids."""
    r = client.post("/api/exercises", json={"name": "Plank", "muscle_group_ids": []})
    assert r.status_code == 201
    data = r.json()
    assert data["muscle_groups"] == []
    assert data["equipment"] is None


def test_create_exercise_invalid_muscle_group_id(client):
    """Assert POST /api/exercises returns 400 for a non-existent muscle group."""
    r = client.post(
        "/api/exercises",
        json={"name": "Bad Exercise", "muscle_group_ids": [9999]},
    )
    assert r.status_code == 400


def test_create_exercise_missing_name(client):
    """Assert POST /api/exercises returns 422 when name is absent."""
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
# PUT /api/exercise/{id} — admin_client for global exercises
# ---------------------------------------------------------------------------

def test_update_exercise_name(admin_client, db):
    """Assert PUT /api/exercise/{id} updates the name while leaving other fields."""
    ex = make_exercise(db)
    r = admin_client.put(
        f"/api/exercise/{ex.id}", json={"name": "Incline Bench Press"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Incline Bench Press"
    assert data["equipment"] == "barbell"
    assert data["instructions"] == "Press the bar up"


def test_update_exercise_muscle_groups(admin_client, db):
    """Assert PUT /api/exercise/{id} replaces the muscle group list."""
    mg1 = make_muscle_group(db, name="pectorals")
    mg2 = make_muscle_group(db, name="triceps")
    ex = make_exercise(db, muscle_groups=[mg1])
    r = admin_client.put(
        f"/api/exercise/{ex.id}", json={"muscle_group_ids": [mg2.id]}
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["muscle_groups"]) == 1
    assert data["muscle_groups"][0]["id"] == mg2.id


def test_update_exercise_multiple_fields(admin_client, db):
    """Assert PUT /api/exercise/{id} updates name, equipment, instructions together."""
    ex = make_exercise(db)
    r = admin_client.put(f"/api/exercise/{ex.id}", json={
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


def test_update_exercise_name_conflict(admin_client, db):
    """Assert PUT /api/exercise/{id} returns 409 when the new name is taken."""
    make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = admin_client.put(f"/api/exercise/{ex_b.id}", json={"name": "Bench Press"})
    assert r.status_code == 409


def test_update_exercise_same_name_no_conflict(admin_client, db):
    """Assert PUT /api/exercise/{id} returns 200 when the name is unchanged."""
    ex = make_exercise(db, name="Bench Press")
    r = admin_client.put(f"/api/exercise/{ex.id}", json={"name": "Bench Press"})
    assert r.status_code == 200


def test_update_exercise_invalid_muscle_group_id(admin_client, db):
    """Assert PUT /api/exercise/{id} returns 400 for a non-existent muscle group."""
    ex = make_exercise(db)
    r = admin_client.put(f"/api/exercise/{ex.id}", json={"muscle_group_ids": [9999]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/exercise/{id} — admin_client for global exercises
# ---------------------------------------------------------------------------

def test_delete_exercise(admin_client, db):
    """Assert DELETE /api/exercise/{id} removes the exercise and returns 204."""
    ex = make_exercise(db)
    r = admin_client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 204
    assert admin_client.get(f"/api/exercise/{ex.id}/info").status_code == 404


def test_delete_exercise_not_found(client):
    """Assert DELETE /api/exercise/{id} returns 404 for an unknown ID."""
    r = client.delete("/api/exercise/9999")
    assert r.status_code == 404


def test_delete_exercise_with_history(admin_client, db):
    """Assert DELETE returns 409 and leaves exercise intact when it has history."""
    ex = make_exercise(db)
    admin_client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}
        ]
    })
    r = admin_client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 409
    assert admin_client.get(f"/api/exercise/{ex.id}/info").status_code == 200


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------

def test_non_admin_cannot_edit_global_exercise(client, db):
    """Assert PUT /api/exercise/{id} returns 403 for a global exercise as non-admin."""
    ex = make_exercise(db)
    r = client.put(f"/api/exercise/{ex.id}", json={"name": "New Name"})
    assert r.status_code == 403


def test_non_admin_cannot_delete_global_exercise(client, db):
    """Assert DELETE /api/exercise/{id} returns 403 for a global exercise as non-admin."""
    ex = make_exercise(db)
    r = client.delete(f"/api/exercise/{ex.id}")
    assert r.status_code == 403


def test_user_can_edit_own_custom_exercise(client, db):
    """Assert PUT /api/exercise/{id} succeeds for the user's own custom exercise."""
    r = client.post("/api/exercises", json={
        "name": "My Custom Press", "muscle_group_ids": []
    })
    exercise_id = r.json()["id"]
    r2 = client.put(
        f"/api/exercise/{exercise_id}", json={"name": "My Updated Press"}
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "My Updated Press"


def test_user_can_delete_own_custom_exercise(client, db):
    """Assert DELETE /api/exercise/{id} returns 204 for the user's own custom exercise."""
    r = client.post(
        "/api/exercises", json={"name": "To Delete", "muscle_group_ids": []}
    )
    exercise_id = r.json()["id"]
    assert client.delete(f"/api/exercise/{exercise_id}").status_code == 204


def test_user_cannot_edit_other_users_custom_exercise(client, db, user):
    """Assert PUT /api/exercise/{id} returns 403 for another user's custom exercise."""
    from app.model.models import ExerciseDef
    other_ex = ExerciseDef(name="Other Custom", user_id=user.id + 999)
    db.add(other_ex)
    db.commit()
    db.refresh(other_ex)
    r = client.put(f"/api/exercise/{other_ex.id}", json={"name": "Hijacked"})
    assert r.status_code == 403


def test_admin_can_edit_global_exercise(admin_client, db):
    """Assert PUT /api/exercise/{id} returns 200 when admin edits a global exercise."""
    ex = make_exercise(db)
    r = admin_client.put(f"/api/exercise/{ex.id}", json={"name": "Admin Renamed"})
    assert r.status_code == 200


def test_admin_can_delete_global_exercise(admin_client, db):
    """Assert DELETE /api/exercise/{id} returns 204 when admin deletes a global exercise."""
    ex = make_exercise(db)
    assert admin_client.delete(f"/api/exercise/{ex.id}").status_code == 204


def test_list_exercises_includes_own_custom(client, db):
    """Assert GET /api/exercises returns global + caller's custom exercises."""
    make_exercise(db, name="Global Squat")
    client.post("/api/exercises", json={
        "name": "My Curl", "muscle_group_ids": []
    })
    names = [e["name"] for e in client.get("/api/exercises").json()]
    assert "Global Squat" in names
    assert "My Curl" in names


def test_list_exercises_excludes_other_users_custom(client, db, user):
    """Assert GET /api/exercises does not include another user's custom exercise."""
    from app.model.models import ExerciseDef
    other_ex = ExerciseDef(name="Other User Curl", user_id=user.id + 999)
    db.add(other_ex)
    db.commit()
    names = [e["name"] for e in client.get("/api/exercises").json()]
    assert "Other User Curl" not in names


# ---------------------------------------------------------------------------
# GET /api/exercise/{id}/progression
# ---------------------------------------------------------------------------

def test_progression_no_history(client, db):
    """Assert GET /api/exercise/{id}/progression returns empty sessions."""
    ex = make_exercise(db, name="Bench Press")
    r = client.get(f"/api/exercise/{ex.id}/progression")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == []
    assert data["exercise_name"] == "Bench Press"


def test_progression_with_history(client, db):
    """Assert progression returns sessions chronologically with aggregates."""
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
    """Assert GET /api/muscle-groups returns an empty list when none exist."""
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
