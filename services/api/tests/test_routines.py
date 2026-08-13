from app.db.models import RoutineExercise

from conftest import make_exercise


def make_routine_payload(name, exercises):
    """Build a POST/PUT request body dict for the routines API."""
    return {"name": name, "exercises": exercises}


# ---------------------------------------------------------------------------
# POST /api/routines
# ---------------------------------------------------------------------------

def test_create_routine(client, db):
    """Assert POST /api/routines creates routine with ordered exercises."""
    ex_a = make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    payload = make_routine_payload("Push Day", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 4},
        {"exercise_id": ex_b.id, "position": 2, "num_sets": 3},
    ])
    r = client.post("/api/routines", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "Push Day"
    assert len(data["exercises"]) == 2
    assert data["exercises"][0]["position"] == 1
    assert data["exercises"][0]["num_sets"] == 4
    assert data["exercises"][1]["position"] == 2
    assert data["exercises"][1]["num_sets"] == 3


def test_create_routine_single_exercise(client, db):
    """Assert POST /api/routines succeeds with exactly one exercise."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Solo", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    assert r.status_code == 201
    assert len(r.json()["exercises"]) == 1


def test_create_routine_duplicate_name(client, db):
    """Assert POST /api/routines returns 409 on duplicate name."""
    ex = make_exercise(db)
    payload = make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ])
    client.post("/api/routines", json=payload)
    r = client.post("/api/routines", json=payload)
    assert r.status_code == 409


def test_create_routine_empty_exercises(client):
    """Assert POST /api/routines accepts an empty exercises list."""
    r = client.post(
        "/api/routines",
        json={"name": "Empty Routine", "exercises": []},
    )
    assert r.status_code == 201


def test_create_routine_missing_name(client):
    """Assert POST /api/routines returns 422 when name is missing."""
    r = client.post("/api/routines", json={"exercises": []})
    assert r.status_code == 422


def test_create_routine_invalid_exercise_id(client):
    """Assert POST /api/routines rejects non-existent exercise_id."""
    r = client.post("/api/routines", json={
        "name": "Bad Routine",
        "exercises": [
            {"exercise_id": 9999, "position": 1, "num_sets": 3}
        ],
    })
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /api/routines
# ---------------------------------------------------------------------------

def test_list_routines_empty(client):
    """Assert GET /api/routines returns [] when no routines exist."""
    r = client.get("/api/routines")
    assert r.status_code == 200
    assert r.json() == []


def test_list_routines(client, db):
    """Assert GET /api/routines returns routines with summary fields."""
    ex = make_exercise(db)
    for name in ("Push Day", "Pull Day"):
        client.post("/api/routines", json=make_routine_payload(name, [
            {"exercise_id": ex.id, "position": 1, "num_sets": 3},
        ]))
    r = client.get("/api/routines")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "exercise_count" in item


def test_list_routines_includes_exercise_count(client, db):
    """Assert GET /api/routines shows correct exercise count per routine."""
    ex_a = make_exercise(db, name="A")
    ex_b = make_exercise(db, name="B")
    ex_c = make_exercise(db, name="C")
    client.post("/api/routines", json=make_routine_payload("Three", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 3},
        {"exercise_id": ex_b.id, "position": 2, "num_sets": 3},
        {"exercise_id": ex_c.id, "position": 3, "num_sets": 3},
    ]))
    client.post("/api/routines", json=make_routine_payload("One", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 3},
    ]))
    data = client.get("/api/routines").json()
    counts = {item["name"]: item["exercise_count"] for item in data}
    assert counts["Three"] == 3
    assert counts["One"] == 1


# ---------------------------------------------------------------------------
# GET /api/routine/{id}
# ---------------------------------------------------------------------------

def test_get_routine_detail(client, db):
    """Assert GET /api/routine/{id} returns full detail with exercises."""
    ex_a = make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 4},
        {"exercise_id": ex_b.id, "position": 2, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.get(f"/api/routine/{routine_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert "id" in data
    assert "name" in data
    exs = data["exercises"]
    assert len(exs) == 2
    assert exs[0]["position"] == 1
    assert exs[1]["position"] == 2
    for ex in exs:
        assert "exercise_id" in ex
        assert "position" in ex
        assert "num_sets" in ex
        assert "name" in ex


def test_get_routine_not_found(client):
    """Assert GET /api/routine/{id} returns 404 for unknown ID."""
    assert client.get("/api/routine/9999").status_code == 404


def test_get_routine_exercise_order_preserved(client, db):
    """Assert GET /api/routine/{id} orders exercises by position field."""
    ex_a = make_exercise(db, name="A")
    ex_b = make_exercise(db, name="B")
    ex_c = make_exercise(db, name="C")
    r = client.post("/api/routines", json=make_routine_payload("Order", [
        {"exercise_id": ex_c.id, "position": 1, "num_sets": 3},
        {"exercise_id": ex_a.id, "position": 2, "num_sets": 3},
        {"exercise_id": ex_b.id, "position": 3, "num_sets": 3},
    ]))
    exs = client.get(f"/api/routine/{r.json()['id']}").json()["exercises"]
    assert exs[0]["exercise_id"] == ex_c.id
    assert exs[1]["exercise_id"] == ex_a.id
    assert exs[2]["exercise_id"] == ex_b.id


# ---------------------------------------------------------------------------
# PUT /api/routine/{id}
# ---------------------------------------------------------------------------

def test_update_routine_name(client, db):
    """Assert PUT /api/routine/{id} renames without changing exercises."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.put(
        f"/api/routine/{routine_id}",
        json=make_routine_payload("Heavy Push Day", [
            {"exercise_id": ex.id, "position": 1, "num_sets": 3},
        ]),
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "Heavy Push Day"
    assert len(r2.json()["exercises"]) == 1


def test_update_routine_exercises(client, db):
    """Assert PUT /api/routine/{id} replaces exercises on full update."""
    ex_a = make_exercise(db, name="A")
    ex_b = make_exercise(db, name="B")
    ex_c = make_exercise(db, name="C")
    r = client.post("/api/routines", json=make_routine_payload("Test", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 3},
        {"exercise_id": ex_b.id, "position": 2, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.put(
        f"/api/routine/{routine_id}",
        json=make_routine_payload("Test", [
            {"exercise_id": ex_b.id, "position": 1, "num_sets": 3},
            {"exercise_id": ex_c.id, "position": 2, "num_sets": 3},
        ]),
    )
    assert r2.status_code == 200
    ids = [e["exercise_id"] for e in r2.json()["exercises"]]
    assert ex_a.id not in ids
    assert ex_b.id in ids
    assert ex_c.id in ids


def test_update_routine_reorder(client, db):
    """Assert PUT /api/routine/{id} reorders exercises by new positions."""
    ex_a = make_exercise(db, name="A")
    ex_b = make_exercise(db, name="B")
    r = client.post("/api/routines", json=make_routine_payload("Test", [
        {"exercise_id": ex_a.id, "position": 1, "num_sets": 3},
        {"exercise_id": ex_b.id, "position": 2, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.put(
        f"/api/routine/{routine_id}",
        json=make_routine_payload("Test", [
            {"exercise_id": ex_b.id, "position": 1, "num_sets": 3},
            {"exercise_id": ex_a.id, "position": 2, "num_sets": 3},
        ]),
    )
    assert r2.status_code == 200
    exs = r2.json()["exercises"]
    assert exs[0]["exercise_id"] == ex_b.id
    assert exs[1]["exercise_id"] == ex_a.id


def test_update_routine_set_counts(client, db):
    """Assert PUT /api/routine/{id} updates num_sets for an exercise."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Test", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.put(
        f"/api/routine/{routine_id}",
        json=make_routine_payload("Test", [
            {"exercise_id": ex.id, "position": 1, "num_sets": 5},
        ]),
    )
    assert r2.status_code == 200
    assert r2.json()["exercises"][0]["num_sets"] == 5


def test_update_routine_not_found(client, db):
    """Assert PUT /api/routine/{id} returns 404 for unknown routine ID."""
    ex = make_exercise(db)
    r = client.put("/api/routine/9999", json=make_routine_payload("Ghost", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    assert r.status_code == 404


def test_update_routine_name_conflict(client, db):
    """Assert PUT /api/routine/{id} returns 409 on name conflict."""
    ex = make_exercise(db)
    client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    r_b = client.post("/api/routines", json=make_routine_payload("Pull Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    r = client.put(
        f"/api/routine/{r_b.json()['id']}",
        json=make_routine_payload("Push Day", [
            {"exercise_id": ex.id, "position": 1, "num_sets": 3},
        ]),
    )
    assert r.status_code == 409


def test_update_routine_same_name_no_conflict(client, db):
    """Assert PUT /api/routine/{id} returns 200 when name is unchanged."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.put(
        f"/api/routine/{routine_id}",
        json=make_routine_payload("Push Day", [
            {"exercise_id": ex.id, "position": 1, "num_sets": 3},
        ]),
    )
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/routine/{id}
# ---------------------------------------------------------------------------

def test_delete_routine(client, db):
    """Assert DELETE /api/routine/{id} removes routine; GET returns 404."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    r2 = client.delete(f"/api/routine/{routine_id}")
    assert r2.status_code == 200
    assert client.get(f"/api/routine/{routine_id}").status_code == 404


def test_delete_routine_not_found(client):
    """Assert DELETE /api/routine/{id} returns 404 for unknown ID."""
    assert client.delete("/api/routine/9999").status_code == 404


def test_delete_routine_does_not_affect_exercises(client, db):
    """Assert DELETE /api/routine/{id} does not delete exercises."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    client.delete(f"/api/routine/{r.json()['id']}")
    assert client.get(f"/api/exercise/{ex.id}/info").status_code == 200


def test_delete_routine_does_not_affect_workouts(client, db):
    """Assert DELETE /api/routine/{id} does not affect logged workouts."""
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}
        ],
    })
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    client.delete(f"/api/routine/{r.json()['id']}")
    assert len(client.get("/api/workouts").json()) == 1


def test_delete_routine_cleans_up_join_table(client, db):
    """Assert DELETE /api/routine/{id} removes all routine_exercises rows."""
    ex = make_exercise(db)
    r = client.post("/api/routines", json=make_routine_payload("Push Day", [
        {"exercise_id": ex.id, "position": 1, "num_sets": 3},
    ]))
    routine_id = r.json()["id"]
    client.delete(f"/api/routine/{routine_id}")
    count = db.query(RoutineExercise).filter(
        RoutineExercise.routine_id == routine_id
    ).count()
    assert count == 0


def test_routines_scoped_to_user(db):
    """Assert a user only sees their own routines, not another user's."""
    from conftest import make_user, make_exercise
    from app.auth.routes import get_current_user
    from app.db.database import get_db
    from fastapi.testclient import TestClient
    from app.main import app

    user_a = make_user(db, username="alice2")
    user_b = make_user(db, username="bob2")
    ex = make_exercise(db, name="Curl2")

    def db_override():
        """Yield the shared test db session."""
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_a.id), "username": "alice2",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as ca:
        ca.post("/api/routines", json={
            "name": "Alice Routine",
            "exercises": [
                {"exercise_id": ex.id, "position": 1, "num_sets": 3}
            ],
        })
        assert len(ca.get("/api/routines").json()) == 1

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_b.id), "username": "bob2",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as cb:
        assert len(cb.get("/api/routines").json()) == 0

    app.dependency_overrides.clear()
