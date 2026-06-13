"""Tests for per-user daily token budget enforcement and IP key extraction.

Run from backend/:  python -m pytest tests/test_cost_guard.py -v
"""
import asyncio
import pytest
from fastapi import HTTPException

import database
import models
from auth import hash_password, create_access_token
from cost_guard import check_token_budget
from limiter import _client_ip


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    session = database.SessionLocal()
    yield session
    session.close()


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


def _add_usage(db, user, input_tokens=0, output_tokens=0, cache_write_tokens=0):
    """Insert a TokenUsage row attributed to the given user."""
    row = models.TokenUsage(
        function_name="test",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=0,
        cache_write_tokens=cache_write_tokens,
        user_id=user.id,
        total_cost_usd=0.0,
    )
    db.add(row)
    db.commit()


def _run(coro):
    """Run a coroutine synchronously (avoids requiring pytest-asyncio)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# Mock request objects for _client_ip tests
class _MockClient:
    def __init__(self, host):
        self.host = host


class _MockRequest:
    def __init__(self, xff=None, host="127.0.0.1"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = _MockClient(host)


# ─── Budget check: allowed cases ──────────────────────────────────────────────

def test_budget_user_at_zero_tokens_is_allowed(db):
    """User with no usage today must pass check_token_budget."""
    user = _make_user(db, "cg_zero")
    result = _run(check_token_budget(user=user, db=db))
    assert result.id == user.id


def test_budget_user_below_limit_is_allowed(db):
    """User at 49 999 tokens (one below the 50 000 default) must be allowed."""
    user = _make_user(db, "cg_below")
    _add_usage(db, user, input_tokens=49_999)
    result = _run(check_token_budget(user=user, db=db))
    assert result.id == user.id


# ─── Budget check: blocked case ───────────────────────────────────────────────

def test_budget_user_at_limit_is_blocked(db):
    """User at exactly the daily limit must receive HTTP 429."""
    user = _make_user(db, "cg_at_limit")
    _add_usage(db, user, input_tokens=50_000)
    with pytest.raises(HTTPException) as exc_info:
        _run(check_token_budget(user=user, db=db))
    assert exc_info.value.status_code == 429
    assert "midnight UTC" in exc_info.value.detail


# ─── Budget check: admin exemption ───────────────────────────────────────────

def test_budget_admin_exempt_at_any_usage(db):
    """Admin-role users must always pass check_token_budget regardless of spend."""
    admin = _make_user(db, "cg_admin", role="admin")
    _add_usage(db, admin, input_tokens=1_000_000)
    result = _run(check_token_budget(user=admin, db=db))
    assert result.id == admin.id


# ─── /me/token-status endpoint ────────────────────────────────────────────────

def test_token_status_endpoint_returns_correct_structure(db):
    """/api/me/token-status must return all required keys with correct types."""
    from fastapi.testclient import TestClient
    from main import app

    user = _make_user(db, "cg_status_user")
    token = create_access_token({"sub": user.id, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    resp = TestClient(app).get("/api/me/token-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["tokens_used_today"], int)
    assert isinstance(data["cost_used_today_usd"], float)
    assert data["daily_limit_tokens"] == 50_000
    assert data["limit_resets_at"].endswith("Z")
    assert data["is_admin"] is False


def test_token_status_admin_shows_null_limit(db):
    """Admin must see daily_limit_tokens: null in /api/me/token-status."""
    from fastapi.testclient import TestClient
    from main import app

    admin = _make_user(db, "cg_status_admin", role="admin")
    token = create_access_token({"sub": admin.id, "role": admin.role})
    headers = {"Authorization": f"Bearer {token}"}

    resp = TestClient(app).get("/api/me/token-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["daily_limit_tokens"] is None
    assert data["is_admin"] is True


# ─── _client_ip: X-Forwarded-For parsing ─────────────────────────────────────

def test_xff_first_ip_extracted():
    """First IP in a multi-entry X-Forwarded-For header must be returned."""
    req = _MockRequest(xff="1.2.3.4, 5.6.7.8, 9.10.11.12")
    assert _client_ip(req) == "1.2.3.4"


def test_xff_strips_surrounding_whitespace():
    """Whitespace around the first IP must be stripped."""
    req = _MockRequest(xff=" 1.2.3.4 , 5.6.7.8")
    assert _client_ip(req) == "1.2.3.4"


def test_xff_absent_falls_back_to_client_host():
    """Without X-Forwarded-For the function must return request.client.host."""
    req = _MockRequest(host="10.0.0.1")
    assert _client_ip(req) == "10.0.0.1"
