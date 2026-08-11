import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException
from jose import JWTError, jwt

_JWT_SECRET = os.environ.get("JWT_SECRET", "")
_SIGNUP_CODE = os.environ.get("SIGNUP_CODE", "")
_ALGORITHM = "HS256"

if not _JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of plain."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed, False otherwise."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def check_signup_code(code: str) -> bool:
    """Return True if code matches the SIGNUP_CODE env var."""
    return bool(_SIGNUP_CODE) and code == _SIGNUP_CODE


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """Return a signed JWT encoding data with expiry now + expires_delta."""
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate token; raise HTTPException 401 if invalid or expired."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
