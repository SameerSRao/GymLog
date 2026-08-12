from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.auth.service import (
    check_signup_code,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_username,
    verify_password,
)
from app.db.database import get_db

router = APIRouter()

_TOKEN_EXPIRE_HOURS = 720
_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return its decoded payload; raise 401."""
    return decode_access_token(credentials.credentials)


def require_not_demo(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Raise 403 if the caller is a demo account."""
    if current_user.get("is_demo"):
        raise HTTPException(
            status_code=403,
            detail="Demo accounts cannot perform this action",
        )
    return current_user


def _make_token(user) -> str:
    """Return a signed JWT for user with id, username, flags."""
    return create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
            "is_demo": user.is_demo,
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


@router.post(
    "/auth/register", response_model=TokenResponse, status_code=201
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create account and return JWT; 400 bad code, 409 duplicate user."""
    if not check_signup_code(body.signup_code):
        raise HTTPException(status_code=400, detail="Invalid signup code")
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = create_user(db, body.username, body.password)
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.get("/auth/demo", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """Return a JWT for the demo user; 503 if demo user is not seeded."""
    user = get_user_by_username(db, "demo")
    if not user or not user.is_demo:
        raise HTTPException(status_code=503, detail="Demo unavailable")
    return TokenResponse(
        access_token=_make_token(user), token_type="bearer"
    )


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    """Return current user's profile flags; used by chat service."""
    return {
        "id": int(current_user["sub"]),
        "username": current_user["username"],
        "is_admin": current_user.get("is_admin", False),
        "is_premium": current_user.get("is_premium", False),
        "is_demo": current_user.get("is_demo", False),
    }
