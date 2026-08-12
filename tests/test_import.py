from fastapi.testclient import TestClient

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app
from conftest import make_exercise, make_user


# ---------------------------------------------------------------------------
# POST /api/workouts/import
# ---------------------------------------------------------------------------

def test_import_single_session(admin_client, db):
    """Assert POST /api/workouts/import creates one session and its sets."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {
                    "exercise_id": ex.id,
                    "sets": [
                        {"reps": 8, "weight_lbs": 135},
                        {"reps": 8, "weight_lbs": 135},
                    ],
                }
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 1
    assert data["sets_created"] == 2
    assert data["errors"] == []


def test_import_multiple_sessions(admin_client, db):
    """Assert POST /api/workouts/import handles multiple sessions correctly."""
    ex1 = make_exercise(db, name="Bench Press")
    ex2 = make_exercise(db, name="Squat")
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {
                    "exercise_id": ex1.id,
                    "sets": [{"reps": 8, "weight_lbs": 135}],
                }
            ],
        },
        {
            "logged_at": "2025-01-11T10:00:00",
            "exercises": [
                {
                    "exercise_id": ex2.id,
                    "sets": [
                        {"reps": 5, "weight_lbs": 225},
                        {"reps": 5, "weight_lbs": 225},
                    ],
                }
            ],
        },
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 2
    assert data["sets_created"] == 3
    assert data["errors"] == []


def test_import_invalid_exercise_id_skipped(admin_client, db):
    """Assert sessions with unknown exercise_ids are skipped and reported."""
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": 9999, "sets": [{"reps": 8}]},
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 0
    assert data["sets_created"] == 0
    assert len(data["errors"]) == 1
    assert "9999" in data["errors"][0]["reason"]
    assert data["errors"][0]["index"] == 0


def test_import_partial_error_continues(admin_client, db):
    """Assert a bad session is skipped but valid sessions still import."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": 9999, "sets": [{"reps": 8}]},
            ],
        },
        {
            "logged_at": "2025-01-11T10:00:00",
            "exercises": [
                {
                    "exercise_id": ex.id,
                    "sets": [{"reps": 5, "weight_lbs": 100}],
                }
            ],
        },
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sessions_created"] == 1
    assert data["sets_created"] == 1
    assert len(data["errors"]) == 1


def test_import_allowed_for_regular_user(client, db):
    """Assert POST /api/workouts/import is allowed for non-admin users."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": ex.id, "sets": [{"reps": 5, "weight_lbs": 100}]},
            ],
        }
    ]
    r = client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    assert r.json()["sessions_created"] == 1


def test_import_bodyweight_set(admin_client, db):
    """Assert sets without weight_lbs (bodyweight) are accepted."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-01-10T09:00:00",
            "exercises": [
                {"exercise_id": ex.id, "sets": [{"reps": 10}]},
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200
    assert r.json()["sets_created"] == 1


def test_import_logged_at_persisted(admin_client, db):
    """Assert the logged_at timestamp from the payload is stored on session."""
    ex = make_exercise(db)
    payload = [
        {
            "logged_at": "2025-03-15T07:30:00",
            "exercises": [
                {
                    "exercise_id": ex.id,
                    "sets": [{"reps": 5, "weight_lbs": 135}],
                }
            ],
        }
    ]
    r = admin_client.post("/api/workouts/import", json=payload)
    assert r.status_code == 200

    def db_override():
        """Yield db for dependency override."""
        yield db

    def user_override():
        """Return admin user dict."""
        from app.model.models import User
        admin = db.query(User).filter(User.username == "admin").first()
        return {
            "sub": str(admin.id),
            "username": admin.username,
            "is_admin": True,
            "is_premium": True,
        }

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = user_override
    with TestClient(app) as c:
        workouts = c.get("/api/workouts").json()
    app.dependency_overrides.clear()

    assert any("2025-03-15" in w["logged_at"] for w in workouts)
