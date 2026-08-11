from app.model.models import Exercise

from conftest import make_exercise, make_muscle_group


# ---------------------------------------------------------------------------
# POST /api/workouts
# ---------------------------------------------------------------------------

def test_create_workout_single_exercise(client, db):
    """Assert POST /api/workouts logs one exercise with one set correctly."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert data["exercises_logged"] == 1
    assert data["sets_logged"] == 1


def test_create_workout_multiple_exercises(client, db):
    """Assert POST /api/workouts logs multiple exercises and counts sets correctly."""
    ex1 = make_exercise(db, name="Bench Press")
    ex2 = make_exercise(db, name="Squat")
    r = client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex1.id, "sets": [
                {"reps": 5, "weight_lbs": 135},
                {"reps": 5, "weight_lbs": 145},
                {"reps": 5, "weight_lbs": 155},
            ]},
            {"exercise_id": ex2.id, "sets": [
                {"reps": 5, "weight_lbs": 185},
                {"reps": 5, "weight_lbs": 195},
                {"reps": 5, "weight_lbs": 205},
            ]},
        ]
    })
    assert r.status_code == 200
    data = r.json()
    assert data["exercises_logged"] == 2
    assert data["sets_logged"] == 6


def test_create_workout_bodyweight_exercise(client, db):
    """Assert POST /api/workouts accepts a set with no weight_lbs."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 10}]}]
    })
    assert r.status_code == 200
    assert r.json()["sets_logged"] == 1


def test_create_workout_with_notes(client, db):
    """Assert POST /api/workouts persists notes and returns them in the detail response."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}],
        "notes": "Felt strong today",
    })
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert r2.status_code == 200
    assert r2.json()["notes"] == "Felt strong today"


def test_create_workout_with_custom_timestamp(client, db):
    """Assert POST /api/workouts persists a custom logged_at timestamp."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}],
        "logged_at": "2026-01-15T08:00:00",
    })
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert "2026-01-15" in r2.json()["logged_at"]


def test_create_workout_empty_exercises(client):
    """Assert POST /api/workouts succeeds with an empty exercises list."""
    r = client.post("/api/workouts", json={"exercises": []})
    assert r.status_code == 200
    data = r.json()
    assert data["exercises_logged"] == 0
    assert data["sets_logged"] == 0


# ---------------------------------------------------------------------------
# GET /api/workouts
# ---------------------------------------------------------------------------

def test_list_workouts_empty(client):
    """Assert GET /api/workouts returns an empty list when no sessions exist."""
    r = client.get("/api/workouts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_workouts(client, db):
    """Assert GET /api/workouts returns all sessions with required summary fields."""
    ex = make_exercise(db)
    for _ in range(3):
        client.post("/api/workouts", json={
            "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
        })
    r = client.get("/api/workouts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    for item in data:
        assert "session_id" in item
        assert "logged_at" in item
        assert "exercises_logged" in item
        assert "sets_logged" in item


def test_list_workouts_ordered_by_date_desc(client, db):
    """Assert GET /api/workouts returns sessions newest-first."""
    ex = make_exercise(db)
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]}],
        "logged_at": "2026-01-01T08:00:00",
    })
    client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 110}]}],
        "logged_at": "2026-06-01T08:00:00",
    })
    r = client.get("/api/workouts")
    data = r.json()
    assert data[0]["logged_at"] > data[1]["logged_at"]


# ---------------------------------------------------------------------------
# GET /api/workout/{id}
# ---------------------------------------------------------------------------

def test_get_workout_detail(client, db):
    """Assert GET /api/workout/{id} returns exercises with muscle groups and correct sets."""
    mg = make_muscle_group(db, name="pectorals")
    ex1 = make_exercise(db, name="Bench Press", muscle_groups=[mg])
    ex2 = make_exercise(db, name="Squat", muscle_groups=[mg])
    r = client.post("/api/workouts", json={
        "exercises": [
            {"exercise_id": ex1.id, "sets": [
                {"reps": 5, "weight_lbs": 135}, {"reps": 5, "weight_lbs": 145}
            ]},
            {"exercise_id": ex2.id, "sets": [
                {"reps": 5, "weight_lbs": 185}, {"reps": 5, "weight_lbs": 195}
            ]},
        ]
    })
    session_id = r.json()["session_id"]
    r2 = client.get(f"/api/workout/{session_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["exercises"]) == 2
    for ex in data["exercises"]:
        assert "name" in ex
        assert len(ex["muscle_groups"]) > 0
        assert len(ex["sets"]) == 2
        assert ex["sets"][0]["reps"] == 5


def test_get_workout_not_found(client):
    """Assert GET /api/workout/{id} returns 404 for an unknown session ID."""
    r = client.get("/api/workout/9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/workout/{id}
# ---------------------------------------------------------------------------

def test_update_workout_replace_exercises(client, db):
    """Assert PUT /api/workout/{id} replaces all exercises and returns only the new ones."""
    ex_a = make_exercise(db, name="Bench Press")
    ex_b = make_exercise(db, name="Squat")
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex_a.id, "sets": [
            {"reps": 5, "weight_lbs": 135},
            {"reps": 5, "weight_lbs": 145},
        ]}]
    })
    session_id = r.json()["session_id"]
    r2 = client.put(f"/api/workout/{session_id}", json={
        "exercises": [{"exercise_id": ex_b.id, "sets": [
            {"reps": 8, "weight_lbs": 185},
            {"reps": 8, "weight_lbs": 195},
            {"reps": 8, "weight_lbs": 205},
        ]}]
    })
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["exercise_id"] == ex_b.id
    assert len(data["exercises"][0]["sets"]) == 3


def test_update_workout_not_found(client, db):
    """Assert PUT /api/workout/{id} returns 404 for an unknown session ID."""
    ex = make_exercise(db)
    r = client.put("/api/workout/9999", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workout/{id}
# ---------------------------------------------------------------------------

def test_delete_workout(client, db):
    """Assert DELETE /api/workout/{id} removes the session and returns its ID."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 135}]}]
    })
    session_id = r.json()["session_id"]
    r2 = client.delete(f"/api/workout/{session_id}")
    assert r2.json() == {"deleted": session_id}
    assert client.get(f"/api/workout/{session_id}").status_code == 404


def test_delete_workout_not_found(client):
    """Assert DELETE /api/workout/{id} returns 404 for an unknown session ID."""
    r = client.delete("/api/workout/9999")
    assert r.status_code == 404


def test_delete_workout_cascades_sets(client, db):
    """Assert DELETE /api/workout/{id} also removes all associated exercise sets."""
    ex = make_exercise(db)
    r = client.post("/api/workouts", json={
        "exercises": [{"exercise_id": ex.id, "sets": [
            {"reps": 5, "weight_lbs": 135},
            {"reps": 5, "weight_lbs": 145},
            {"reps": 5, "weight_lbs": 155},
        ]}]
    })
    session_id = r.json()["session_id"]
    client.delete(f"/api/workout/{session_id}")
    count = db.query(Exercise).filter(Exercise.session_id == session_id).count()
    assert count == 0


def test_workouts_scoped_to_user(db):
    """Assert a user only sees their own workouts, not another user's."""
    from conftest import make_user, make_exercise
    from app.api.auth_routes import get_current_user
    from app.db.database import get_db
    from fastapi.testclient import TestClient
    from app.main import app

    user_a = make_user(db, username="alice")
    user_b = make_user(db, username="bob")
    ex = make_exercise(db, name="Curl")

    def db_override():
        """Yield the shared test db session."""
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_a.id), "username": "alice",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as ca:
        ca.post("/api/workouts", json={
            "exercises": [{"exercise_id": ex.id, "sets": [{"reps": 5}]}]
        })
        assert len(ca.get("/api/workouts").json()) == 1

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user_b.id), "username": "bob",
        "is_admin": False, "is_premium": True,
    }
    with TestClient(app) as cb:
        assert len(cb.get("/api/workouts").json()) == 0

    app.dependency_overrides.clear()
