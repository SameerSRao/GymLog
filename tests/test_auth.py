import os
from datetime import timedelta

os.environ.setdefault("SIGNUP_CODE", "testcode")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.auth_service import (
    check_signup_code,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Auth service unit tests
# ---------------------------------------------------------------------------

def test_verify_password_correct():
    """Assert verify_password returns True when plain matches the hash."""
    assert verify_password("mysecret", hash_password("mysecret")) is True


def test_verify_password_wrong():
    """Assert verify_password returns False when plain does not match."""
    assert verify_password("wrong", hash_password("mysecret")) is False


def test_check_signup_code_correct():
    """Assert check_signup_code returns True for the configured code."""
    assert check_signup_code("testcode") is True


def test_check_signup_code_wrong():
    """Assert check_signup_code returns False for the wrong code."""
    assert check_signup_code("wrongcode") is False


def test_create_access_token_returns_jwt():
    """Assert create_access_token returns a non-empty string."""
    token = create_access_token({"sub": "1"}, timedelta(minutes=30))
    assert isinstance(token, str) and len(token) > 0


def test_decode_returns_correct_claims():
    """Assert decode_access_token returns the encoded payload."""
    token = create_access_token(
        {"sub": "1", "username": "alice"}, timedelta(minutes=30)
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "alice"


def test_decode_raises_401_on_tampered_token():
    """Assert decode_access_token raises HTTPException 401 on bad signature."""
    token = create_access_token({"sub": "1"}, timedelta(minutes=30))
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token[:-5] + "XXXXX")
    assert exc.value.status_code == 401


def test_decode_raises_401_on_expired_token():
    """Assert decode_access_token raises HTTPException 401 on expired token."""
    token = create_access_token({"sub": "1"}, timedelta(seconds=-1))
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

def test_register_correct_code_returns_201(client):
    """Assert POST /api/auth/register returns 201 and a JWT on valid code."""
    r = client.post("/api/auth/register", json={
        "username": "newuser",
        "password": "pass123",
        "signup_code": "testcode",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_wrong_code_returns_400(client):
    """Assert POST /api/auth/register returns 400 on wrong signup code."""
    r = client.post("/api/auth/register", json={
        "username": "newuser",
        "password": "pass123",
        "signup_code": "wrongcode",
    })
    assert r.status_code == 400


def test_register_duplicate_username_returns_409(client, db, user):
    """Assert POST /api/auth/register returns 409 when username is taken."""
    r = client.post("/api/auth/register", json={
        "username": user.username,
        "password": "pass123",
        "signup_code": "testcode",
    })
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

def test_login_correct_credentials_returns_200(client, db, user):
    """Assert POST /api/auth/login returns 200 and a JWT on valid credentials."""
    r = client.post("/api/auth/login", json={
        "username": user.username,
        "password": "testpass",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client, db, user):
    """Assert POST /api/auth/login returns 401 on wrong password."""
    r = client.post("/api/auth/login", json={
        "username": user.username,
        "password": "wrongpassword",
    })
    assert r.status_code == 401


def test_login_unknown_username_returns_401(client):
    """Assert POST /api/auth/login returns 401 for a non-existent username."""
    r = client.post("/api/auth/login", json={
        "username": "ghost",
        "password": "pass",
    })
    assert r.status_code == 401


def test_login_missing_fields_returns_422(client):
    """Assert POST /api/auth/login returns 422 when fields are absent."""
    assert client.post("/api/auth/login", json={}).status_code == 422


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
    assert unauth_client.get("/api/workouts").status_code == 401


def test_protected_route_with_invalid_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with a bad token."""
    assert unauth_client.get(
        "/api/workouts",
        headers={"Authorization": "Bearer badtoken"},
    ).status_code == 401


def test_protected_route_with_valid_token_returns_200(unauth_client, db):
    """Assert GET /api/workouts returns 200 with a valid Bearer token."""
    from conftest import make_user
    u = make_user(db)
    token = create_access_token(
        {
            "sub": str(u.id),
            "username": u.username,
            "is_admin": False,
            "is_premium": False,
        },
        timedelta(minutes=30),
    )
    r = unauth_client.get(
        "/api/workouts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_protected_route_with_expired_token_returns_401(unauth_client):
    """Assert GET /api/workouts returns 401 with an expired token."""
    token = create_access_token({"sub": "1"}, timedelta(seconds=-1))
    assert unauth_client.get(
        "/api/workouts",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 401
