"""Tests for per-session IDOR authorization in sessions.py.

Run from backend/:  python -m pytest tests/test_session_authz.py -v
"""
import json
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


def _make_scenario(db, owner):
    s = models.Scenario(
        title="Authz Test Scenario",
        scenario_type="Tactical",
        timeframe="72 hours",
        geography=json.dumps({"region": "Test"}),
        situation=json.dumps({"summary": "Test"}),
        factions=json.dumps([
            {
                "faction_id": "blue",
                "name": "Blue Force",
                "side": "Blue",
                "role": "Player",
                "order_of_battle": {"units": []},
            },
            {
                "faction_id": "red",
                "name": "Red Force",
                "side": "Red",
                "role": "AI-controlled",
                "order_of_battle": {"units": []},
            },
        ]),
        injects=json.dumps([]),
        win_conditions=json.dumps({"duration_turns": 6}),
        created_by=owner.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_session(db, owner, scenario, faction_assignments=None):
    """Create a session.

    If faction_assignments is omitted the session is *closed*: owner's user_id
    is the only named assignment, so only the owner (or admin/GM) may access it.
    Pass an explicit list to override — e.g. [{"faction_id": "blue"}] for an
    open session with no user_id in assignments.
    """
    if faction_assignments is None:
        faction_assignments = [
            {"faction_id": "blue", "role": "Player", "user_id": owner.id},
        ]
    sess = models.GameSession(
        scenario_id=scenario.id,
        title="Authz Test Session",
        status="Active",
        current_turn=1,
        max_turns=6,
        time_per_turn_hours=12,
        faction_assignments=json.dumps(faction_assignments),
        current_game_state=json.dumps({"faction_scores": [], "unit_status": []}),
        created_by=owner.id,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_player_cannot_get_another_players_session(client, db):
    """Player A must receive 403 when reading a closed session owned by Player B."""
    player_a = _make_user(db, "idor_get_a")
    player_b = _make_user(db, "idor_get_b")
    scenario = _make_scenario(db, player_b)
    session_b = _make_session(db, player_b, scenario)

    resp = client.get(f"/api/sessions/{session_b.id}", headers=_auth(player_a))
    assert resp.status_code == 403


def test_player_cannot_submit_moves_to_another_players_session(client, db):
    """Player A must receive 403 when submitting moves to Player B's session."""
    player_a = _make_user(db, "idor_moves_a")
    player_b = _make_user(db, "idor_moves_b")
    scenario = _make_scenario(db, player_b)
    session_b = _make_session(db, player_b, scenario)

    resp = client.post(
        f"/api/sessions/{session_b.id}/moves",
        json={"faction_id": "blue", "moves": {}},
        headers=_auth(player_a),
    )
    assert resp.status_code == 403


def test_admin_can_get_any_session(client, db):
    """Admin must receive 200 regardless of session ownership."""
    admin = _make_user(db, "idor_admin_user", role="admin")
    owner = _make_user(db, "idor_admin_owner")
    scenario = _make_scenario(db, owner)
    session = _make_session(db, owner, scenario)

    resp = client.get(f"/api/sessions/{session.id}", headers=_auth(admin))
    assert resp.status_code == 200


def test_game_master_can_get_any_session(client, db):
    """game_master must receive 200 regardless of session ownership."""
    gm = _make_user(db, "idor_gm_user", role="game_master")
    owner = _make_user(db, "idor_gm_owner")
    scenario = _make_scenario(db, owner)
    session = _make_session(db, owner, scenario)

    resp = client.get(f"/api/sessions/{session.id}", headers=_auth(gm))
    assert resp.status_code == 200


def test_creator_allowed_when_no_faction_assignments_carry_user_id(client, db):
    """Session creator must be allowed even when no faction_assignment has a user_id."""
    player = _make_user(db, "idor_creator_user")
    scenario = _make_scenario(db, player)
    # Open session: assignments have no user_id field
    session = _make_session(
        db, player, scenario,
        faction_assignments=[{"faction_id": "blue", "role": "Player"}],
    )

    resp = client.get(f"/api/sessions/{session.id}", headers=_auth(player))
    assert resp.status_code == 200


def test_list_sessions_returns_only_own_sessions_for_player(client, db):
    """A player's GET /api/sessions must include their own sessions and exclude closed sessions of others."""
    player_a = _make_user(db, "list_authz_player_a")
    player_b = _make_user(db, "list_authz_player_b")

    scenario_a = _make_scenario(db, player_a)
    scenario_b = _make_scenario(db, player_b)

    session_a = _make_session(db, player_a, scenario_a)
    # Closed session owned by player_b with only player_b in named assignments
    session_b = _make_session(db, player_b, scenario_b)

    resp = client.get("/api/sessions", headers=_auth(player_a))
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}

    assert session_a.id in ids, "player_a must see their own session"
    assert session_b.id not in ids, "player_a must not see player_b's closed session"
