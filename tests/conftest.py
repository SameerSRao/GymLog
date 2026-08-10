import os

os.environ["TESTING"] = "1"          # must be set before app.main is imported
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")
os.environ.setdefault("JWT_SECRET", "testsecret123")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth_routes import get_current_user
from app.db.database import Base, get_db
from app.main import app
from app.model.models import ExerciseDef, MuscleGroup

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


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
):
    """Insert an ExerciseDef into the test database and return it."""
    ex = ExerciseDef(
        name=name,
        equipment=equipment,
        instructions=instructions,
        muscle_groups=muscle_groups or [],
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after to prevent state pollution."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    """Provide a clean SQLAlchemy session bound to the in-memory test database."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """Return a FastAPI TestClient with get_db overridden to use the test session.

    Reuses the same db session so data inserted via db is visible to HTTP handlers.
    Auth is bypassed via a get_current_user override so tests focus on business logic.
    """
    def _override_get_db():
        yield db

    def _override_get_current_user():
        return {"sub": "admin"}

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
