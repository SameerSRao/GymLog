import pytest
from fastapi.testclient import TestClient

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app
from conftest import make_exercise, make_user


@pytest.fixture()
def demo_user(db):
    """Create and return a demo user."""
    user = make_user(db, username="demo", password="x")
    user.is_demo = True
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def demo_client(db, demo_user):
    """Return a TestClient authenticated as the demo user."""
    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(demo_user.id),
            "username": demo_user.username,
            "is_admin": False,
            "is_premium": False,
            "is_demo": True,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/auth/demo
# ---------------------------------------------------------------------------

def test_demo_login_returns_token(db, demo_user):
    """Assert GET /api/auth/demo returns a JWT when demo user exists."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/api/auth/demo")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_demo_login_503_when_no_demo_user(db):
    """Assert GET /api/auth/demo returns 503 when demo user is not seeded."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/api/auth/demo")
    app.dependency_overrides.clear()

    assert r.status_code == 503
