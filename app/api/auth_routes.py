from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.schemas import LoginRequest, TokenResponse
from app.services.auth_service import (
    ADMIN_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    verify_password,
)

router = APIRouter()

_TOKEN_EXPIRE_HOURS = 720  # 30 days
_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return its decoded payload; raise 401 on failure."""
    return decode_access_token(credentials.credentials)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Verify password and return a JWT on success; raise 401 on failure."""
    if not verify_password(body.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = create_access_token(
        {"sub": "admin"}, timedelta(hours=_TOKEN_EXPIRE_HOURS)
    )
    return TokenResponse(access_token=token, token_type="bearer")
