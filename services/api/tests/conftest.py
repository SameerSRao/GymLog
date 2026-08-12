import os

os.environ["TESTING"] = "1"
os.environ.setdefault("SIGNUP_CODE", "testcode")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.routes import get_current_user
from app.db.database import Base, get_db
from app.db.models import ExerciseDef, MuscleGroup
from app.main import app

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(
    bind=test_engine, autocommit=False, autoflush=False
)


def make_user(
    db,
    username="testuser",
    password="testpass",
    is_admin=False,
    is_premium=True,
):
    """Insert a User into the test database and return it."""
    from app.auth.service import create_user
    user = create_user(db, username, password)
    user.is_admin = is_admin
    user.is_premium = is_premium
    db.commit()
    db.refresh(user)
    return user


def make_muscle_group(db, name="pectorals"):
    """Insert a MuscleGroup into the test database and return it."""
    mg = MuscleGroup(name=name)
    db.add(mg)
    db.commit()
    db.refresh(mg)
    return mg


def make_exercise(
    db,
    name="Bench Press",
    equipment="barbell",
    instructions="Press the bar up",
    muscle_groups=None,
    user_id=None,
):
    """Insert an ExerciseDef (global by default) into the test database."""
    ex = ExerciseDef(
        name=name,
        equipment=equipment,
        instructions=instructions,
        muscle_groups=muscle_groups or [],
        user_id=user_id,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    """Provide a clean SQLAlchemy session for the in-memory test database."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    """Create and return a standard (non-admin, premium) test user."""
    return make_user(db)


@pytest.fixture()
def client(db, user):
    """Return a TestClient authenticated as the standard test user."""
    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client(db):
    """Return a TestClient authenticated as an admin user."""
    admin = make_user(db, username="admin", is_admin=True, is_premium=True)

    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {
            "sub": str(admin.id),
            "username": admin.username,
            "is_admin": True,
            "is_premium": True,
        }

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
