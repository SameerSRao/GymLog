import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException
from jose import JWTError, jwt

_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_JWT_SECRET = os.environ.get("JWT_SECRET", "")

if not _ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is not set")
if not _JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

_ALGORITHM = "HS256"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(
    _ADMIN_PASSWORD.encode(), bcrypt.gensalt()
).decode()


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of plain."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed, False otherwise."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """Return a signed JWT encoding data with an expiry of now + expires_delta."""
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate token; raise HTTPException 401 if invalid or expired."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
