import pytest
from fastapi.testclient import TestClient

from app.api.auth_routes import get_current_user
from app.db.database import get_db
from app.main import app


@pytest.fixture()
def non_premium_client(db, user):
    """TestClient for a non-premium, non-admin user."""
    user.is_premium = False
    db.commit()

    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": False,
            "is_premium": False,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_returns_403_for_non_premium(non_premium_client):
    """Assert POST /api/chat returns 403 for a non-premium, non-admin user."""
    r = non_premium_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code == 403


def test_chat_not_403_for_premium(client):
    """Assert POST /api/chat is reachable for a premium user (client fixture is premium)."""
    r = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code != 403


def test_chat_not_403_for_admin(admin_client):
    """Assert POST /api/chat is reachable for an admin even without premium."""
    r = admin_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert r.status_code != 403
