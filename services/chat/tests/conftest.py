import os

os.environ.setdefault("JWT_SECRET", "testsecret123")
os.environ.setdefault("GOOGLE_API_KEY", "fake-key")
os.environ.setdefault("API_BASE_URL", "http://testapi:8000")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """Return a TestClient for the chat service."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    """Return Authorization headers with a fake JWT token."""
    return {"Authorization": "Bearer fake-token"}
