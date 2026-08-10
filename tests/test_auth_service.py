import os
from datetime import timedelta

# Must be set before importing auth_service (module reads env at import time)
os.environ.setdefault("ADMIN_PASSWORD", "supersecret")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi import HTTPException

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


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
