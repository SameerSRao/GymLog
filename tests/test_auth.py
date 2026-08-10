import os
from datetime import timedelta

# Must be set before importing auth_service (module reads env at import time)
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Auth service unit tests
# ---------------------------------------------------------------------------

def test_verify_password_returns_true_for_correct_password():
    """Assert verify_password returns True when plain matches the hash."""
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_returns_false_for_wrong_password():
    """Assert verify_password returns False when plain does not match."""
    hashed = hash_password("mysecret")
    assert verify_password("wrong", hashed) is False


def test_create_access_token_returns_non_empty_string():
    """Assert create_access_token returns a non-empty JWT string."""
    token = create_access_token({"sub": "admin"}, timedelta(minutes=30))
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token_returns_correct_claims():
    """Assert decode_access_token returns the original payload on a valid token."""
    token = create_access_token({"sub": "admin"}, timedelta(minutes=30))
    payload = decode_access_token(token)
    assert payload["sub"] == "admin"


def test_decode_access_token_raises_401_on_tampered_token():
    """Assert decode_access_token raises HTTPException 401 when signature is invalid."""
    token = create_access_token({"sub": "admin"}, timedelta(minutes=30))
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(HTTPException) as exc:
        decode_access_token(tampered)
    assert exc.value.status_code == 401


def test_decode_access_token_raises_401_on_expired_token():
    """Assert decode_access_token raises HTTPException 401 when token is expired."""
    token = create_access_token({"sub": "admin"}, timedelta(seconds=-1))
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

def test_login_with_correct_password_returns_token(client):
    """Assert POST /api/auth/login returns 200 and an access_token."""
    r = client.post("/api/auth/login", json={"password": "testpassword"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


def test_login_with_wrong_password_returns_401(client):
    """Assert POST /api/auth/login returns 401 on wrong password."""
    r = client.post("/api/auth/login", json={"password": "wrongpassword"})
    assert r.status_code == 401


def test_login_with_missing_password_returns_422(client):
    """Assert POST /api/auth/login returns 422 when password field is absent."""
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Route protection
# ---------------------------------------------------------------------------

@pytest.fixture()
def unauth_client(db):
    """TestClient with get_db overridden but no get_current_user override."""
    def _override_get_db():
        yield db
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_protected_route_without_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with no Authorization header."""
    r = unauth_client.get("/api/workouts")
    assert r.status_code == 401


def test_protected_route_with_invalid_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with a bad token."""
    r = unauth_client.get(
        "/api/workouts", headers={"Authorization": "Bearer badtoken"}
    )
    assert r.status_code == 401


def test_protected_route_with_valid_token_returns_200(unauth_client):
    """Assert GET /api/workouts returns 200 with a valid Bearer token."""
    token = create_access_token({"sub": "admin"}, timedelta(minutes=30))
    r = unauth_client.get(
        "/api/workouts", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200


def test_protected_route_with_expired_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with an expired Bearer token."""
    token = create_access_token({"sub": "admin"}, timedelta(seconds=-1))
    r = unauth_client.get(
        "/api/workouts", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401
