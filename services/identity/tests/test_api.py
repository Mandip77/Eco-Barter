"""
Integration Tests — Identity Service: REST API endpoints
Uses FastAPI TestClient with a SQLite in-memory database so no
live PostgreSQL connection is required.

Covers:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  GET  /api/v1/auth/me
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Override DB before importing app so SQLite is used
SQLALCHEMY_TEST_URL = "sqlite:///./test_identity.db"

# Patch database module so main.py picks up the test engine
import database as db_module

test_engine = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

db_module.engine = test_engine
db_module.SessionLocal = TestingSession

# Now import the app — it will call Base.metadata.create_all(bind=engine) with test_engine
from main import app
from database import Base, get_db

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Bypass rate limiting — _enabled=False doesn't work in slowapi 0.1.9
app.state.limiter._check_request_limit = lambda *args, **kwargs: None

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe all rows before each test for isolation."""
    yield
    from models import User
    db = TestingSession()
    db.query(User).delete()
    db.commit()
    db.close()


def register_user(username="alice", email="alice@example.com", password="Password123!"):
    return client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })


def login_user(email="alice@example.com", password="Password123!"):
    return client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })


# ─────────────────────────────────────────────────────────────
# POST /api/v1/auth/register
# ─────────────────────────────────────────────────────────────

class TestRegister:
    def test_successful_registration_returns_201(self):
        resp = register_user()
        assert resp.status_code == 201

    def test_successful_registration_body(self):
        resp = register_user()
        data = resp.json()
        assert data["username"] == "alice"
        assert data["email"] == "alice@example.com"
        assert "id" in data
        # Password must never be returned
        assert "password" not in data
        assert "hashed_password" not in data

    def test_duplicate_email_returns_400(self):
        register_user()
        resp = register_user(username="alice2")  # different username, same email
        assert resp.status_code == 400
        assert "Email already registered" in resp.json()["detail"]

    def test_duplicate_username_returns_400(self):
        register_user()
        resp = register_user(email="other@example.com")  # different email, same username
        assert resp.status_code == 400
        assert "Username already taken" in resp.json()["detail"]

    def test_invalid_email_format_returns_422(self):
        resp = client.post("/api/v1/auth/register", json={
            "username": "bob",
            "email": "not-an-email",
            "password": "Password123!",
        })
        assert resp.status_code == 422

    def test_missing_fields_returns_422(self):
        resp = client.post("/api/v1/auth/register", json={"username": "bob"})
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# POST /api/v1/auth/login
# ─────────────────────────────────────────────────────────────

class TestLogin:
    def test_successful_login_returns_200(self):
        register_user()
        resp = login_user()
        assert resp.status_code == 200

    def test_successful_login_returns_token(self):
        register_user()
        resp = login_user()
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 10

    def test_wrong_password_returns_401(self):
        register_user()
        resp = login_user(password="WrongPassword!")
        assert resp.status_code == 401

    def test_nonexistent_email_returns_401(self):
        resp = login_user(email="nobody@example.com")
        assert resp.status_code == 401

    def test_login_error_message_is_generic(self):
        """Don't leak which field is wrong (timing / enumeration safety)."""
        register_user()
        resp = login_user(password="BadPass")
        detail = resp.json()["detail"]
        assert "Incorrect email or password" in detail


# ─────────────────────────────────────────────────────────────
# GET /api/v1/auth/me
# ─────────────────────────────────────────────────────────────

class TestMe:
    def _get_token(self):
        register_user()
        resp = login_user()
        return resp.json()["access_token"]

    def test_me_with_valid_token_returns_200(self):
        token = self._get_token()
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_me_returns_correct_user(self):
        token = self._get_token()
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert data["username"] == "alice"
        assert data["email"] == "alice@example.com"

    def test_me_without_token_returns_403(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_with_bad_token_returns_401(self):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401
