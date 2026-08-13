import re

from pydantic import BaseModel, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,30}$")
_PASSWORD_RE = re.compile(r"^[\x20-\x7E]{3,72}$")


class LoginRequest(BaseModel):
    """Request schema for the login endpoint."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request schema for the register endpoint."""

    username: str
    password: str
    signup_code: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Reject usernames that don't match [a-zA-Z0-9_-]{3,30}."""
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3–30 characters and contain only "
                "letters, numbers, underscores, and hyphens."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Reject passwords outside printable ASCII or outside 8–72 chars."""
        if not _PASSWORD_RE.match(v):
            raise ValueError(
                "Password must be 3–72 printable characters."
            )
        return v


class TokenResponse(BaseModel):
    """Response schema returned after a successful login."""

    access_token: str
    token_type: str
