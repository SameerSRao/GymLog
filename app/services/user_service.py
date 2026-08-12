from sqlalchemy.orm import Session

from app.model.models import User
from app.services.auth_service import hash_password


def create_user(db: Session, username: str, password: str) -> User:
    """Create and persist a new user with a bcrypt-hashed password."""
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return a User by username, or None if not found."""
    return db.query(User).filter(User.username == username).first()
