"""Tests for admin endpoint authorization gates.

Run from backend/:  python -m pytest tests/test_admin_authz.py -v
"""
import pytest
from fastapi.testclient import TestClient

import database
import models
from auth import hash_password, create_access_token


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    session = database.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(db, username, role="player"):
    u = models.User(
        username=username,
        email=f"{username}@test.local",
        hashed_password=hash_password("password"),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user):
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


# ─── Player blocked from all three endpoints ──────────────────────────────────

def test_player_cannot_access_stats(client, db):
    player = _make_user(db, "admin_authz_stats_player")
    resp = client.get("/api/admin/stats", headers=_auth(player))
    assert resp.status_code == 403


def test_player_cannot_access_users(client, db):
    player = _make_user(db, "admin_authz_users_player")
    resp = client.get("/api/admin/users", headers=_auth(player))
    assert resp.status_code == 403


def test_player_cannot_access_sessions(client, db):
    player = _make_user(db, "admin_authz_sessions_player")
    resp = client.get("/api/admin/sessions", headers=_auth(player))
    assert resp.status_code == 403


# ─── Admin allowed on all three endpoints ─────────────────────────────────────

def test_admin_can_access_stats(client, db):
    admin = _make_user(db, "admin_authz_stats_admin", role="admin")
    resp = client.get("/api/admin/stats", headers=_auth(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_sessions" in data


def test_admin_can_access_users(client, db):
    admin = _make_user(db, "admin_authz_users_admin", role="admin")
    resp = client.get("/api/admin/users", headers=_auth(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_admin_can_access_sessions(client, db):
    admin = _make_user(db, "admin_authz_sessions_admin", role="admin")
    resp = client.get("/api/admin/sessions", headers=_auth(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
