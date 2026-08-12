from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.db.database import get_db
from app.services.auth_service import (
    check_signup_code,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.services.user_service import create_user, get_user_by_username

router = APIRouter()

_TOKEN_EXPIRE_HOURS = 720
_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return its decoded payload; raise 401 on failure."""
    return decode_access_token(credentials.credentials)


def _make_token(user) -> str:
    """Return a signed JWT for user encoding id, username, is_admin, is_premium."""
    return create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
        },
        timedelta(hours=_TOKEN_EXPIRE_HOURS),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Verify credentials and return a JWT on success; 401 on failure."""
    user = get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail="Incorrect username or password"
        )
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create account and return a JWT; 400 on bad code, 409 on duplicate username."""
    if not check_signup_code(body.signup_code):
        raise HTTPException(status_code=400, detail="Invalid signup code")
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = create_user(db, body.username, body.password)
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )
