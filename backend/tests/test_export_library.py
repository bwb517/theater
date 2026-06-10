"""Tests for scenario export, public library, publish, and clone.

Run from backend/:  python -m pytest tests/test_export_library.py -v
"""
import json
import pytest
from fastapi.testclient import TestClient

import database
import models
from auth import hash_password, create_access_token


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    session = database.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


def _make_user(db, username="tester", role="game_master"):
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


def _auth_header(user):
    # get_current_user resolves the token subject against User.id (matching the
    # real login/register flow in routers/auth.py), not the username.
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _make_scenario(db, user, title="Test Scenario", published=False):
    factions = [
        {"faction_id": "blue_force", "name": "US Army", "side": "Blue", "role": "Player", "units": [
            {"id": "unit-1", "name": "1st Infantry", "type": "Infantry", "strength": 800}
        ]},
        {"faction_id": "red_force", "name": "OpFor", "side": "Red", "role": "AI-controlled", "units": []},
    ]
    win_conditions = {
        "duration_turns": 6,
        "blue_wins": [{"condition": "Capture objective"}],
        "red_wins": [{"condition": "Hold all objectives"}],
    }
    s = models.Scenario(
        title=title,
        scenario_type="Tactical",
        timeframe="72 hours",
        geography=json.dumps({"region": "Eastern Europe"}),
        situation=json.dumps({"summary": "Test situation briefing."}),
        factions=json.dumps(factions),
        injects=json.dumps([]),
        win_conditions=json.dumps(win_conditions),
        ai_notes="Test notes",
        is_template=False,
        created_by=user.id,
        is_published=published,
        published_by_user_id=user.id if published else None,
        usage_count=0,
        is_official=False,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_session(db, user, scenario):
    sess = models.GameSession(
        scenario_id=scenario.id,
        title=scenario.title,
        status="Complete",
        current_turn=2,
        max_turns=6,
        time_per_turn_hours=12,
        faction_assignments=json.dumps([
            {"faction_id": "blue_force", "type": "Player"},
            {"faction_id": "red_force", "type": "AI"},
        ]),
        current_game_state=json.dumps({
            "factions": {
                "blue_force": {"will_to_fight": "High", "units": [{"id": "unit-1", "destroyed": False}]},
                "red_force": {"will_to_fight": "Moderate", "units": []},
            }
        }),
        created_by=user.id,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    for turn_num in (1, 2):
        tl = models.TurnLog(
            session_id=sess.id,
            turn_number=turn_num,
            player_moves=json.dumps([{"faction_id": "blue_force", "moves": {"maneuver": "Advance north"}}]),
            ai_moves=json.dumps([{"faction_id": "red_force", "summary": "Defend in place"}]),
            adjudication=json.dumps({"narrative": f"Turn {turn_num} resolved.", "casualties": {}}),
            injects_triggered=json.dumps([]),
            game_master_notes=None,
        )
        db.add(tl)
    db.commit()
    return sess


# ─── Export: session JSON ──────────────────────────────────────────────────────

def test_session_export_json_schema(client, db):
    user = _make_user(db, "export_json_user")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario)

    resp = client.get(
        f"/api/sessions/{session.id}/export/json",
        headers=_auth_header(user),
    )
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]

    data = resp.json()
    assert data["version"] == "1.0"
    assert data["schema_version"] == "v5"
    assert "scenario" in data
    assert "turns" in data
    assert "metadata" in data


def test_session_export_json_turn_count(client, db):
    user = _make_user(db, "export_turns_user")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario)

    resp = client.get(f"/api/sessions/{session.id}/export/json", headers=_auth_header(user))
    data = resp.json()
    assert len(data["turns"]) == 2
    assert data["turns"][0]["turn_number"] == 1
    assert data["turns"][1]["turn_number"] == 2


def test_session_export_json_roundtrip(client, db):
    """Export JSON, re-import scenario via POST, assert structural equality."""
    user = _make_user(db, "roundtrip_user")
    scenario = _make_scenario(db, user, title="Roundtrip Scenario")
    session = _make_session(db, user, scenario)

    export_resp = client.get(
        f"/api/sessions/{session.id}/export/json",
        headers=_auth_header(user),
    )
    export_data = export_resp.json()
    exported_scenario = export_data["scenario"]

    # Re-import via the create endpoint
    reimport_resp = client.post(
        "/api/scenarios",
        json={
            "title": exported_scenario["title"],
            "scenario_type": exported_scenario["scenario_type"],
            "timeframe": exported_scenario["timeframe"],
            "geography": exported_scenario["geography"],
            "situation": exported_scenario["situation"],
            "factions": exported_scenario["factions"],
            "injects": exported_scenario["injects"],
            "win_conditions": exported_scenario["win_conditions"],
            "ai_notes": exported_scenario["ai_notes"],
        },
        headers=_auth_header(user),
    )
    assert reimport_resp.status_code == 200
    reimported = reimport_resp.json()

    assert reimported["title"] == exported_scenario["title"]
    assert reimported["scenario_type"] == exported_scenario["scenario_type"]
    assert reimported["factions"] == exported_scenario["factions"]
    assert reimported["win_conditions"] == exported_scenario["win_conditions"]
    # IDs must differ — it's a new row
    assert reimported["id"] != exported_scenario["id"]


# ─── Export: session markdown ──────────────────────────────────────────────────

def test_session_export_markdown_content(client, db):
    user = _make_user(db, "md_export_user")
    scenario = _make_scenario(db, user, title="Markdown Export Test")
    session = _make_session(db, user, scenario)

    resp = client.get(
        f"/api/sessions/{session.id}/export/markdown",
        headers=_auth_header(user),
    )
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    text = resp.text
    assert "THEATER WARGAMING PLATFORM" in text
    assert "TURN 1" in text
    assert "TURN 2" in text
    assert "Advance north" in text   # player move
    assert "Defend in place" in text  # AI move


# ─── Export: scenario template ─────────────────────────────────────────────────

def test_scenario_template_export_strips_metadata(client, db):
    user = _make_user(db, "tmpl_export_user")
    scenario = _make_scenario(db, user, title="Template Export Test", published=True)

    resp = client.get(
        f"/api/scenarios/{scenario.id}/export/template",
        headers=_auth_header(user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["export_version"] == "1.0"
    assert "exported_at" in data
    assert data["title"] == scenario.title

    # Sensitive / identity fields must be absent
    for field in ("id", "created_by", "created_at", "is_published",
                  "published_by_user_id", "published_at", "usage_count"):
        assert field not in data, f"Field {field!r} should not appear in template export"


# ─── Library: publish ─────────────────────────────────────────────────────────

def test_publish_requires_gamemaster_or_admin(client, db):
    gm = _make_user(db, "pub_gm")
    player = _make_user(db, "pub_player", role="player")
    scenario = _make_scenario(db, gm)

    # Player should be forbidden
    resp = client.post(f"/api/scenarios/{scenario.id}/publish", headers=_auth_header(player))
    assert resp.status_code == 403

    # Gamemaster should succeed
    resp = client.post(f"/api/scenarios/{scenario.id}/publish", headers=_auth_header(gm))
    assert resp.status_code == 200
    body = resp.json()
    assert body["published"] is True
    assert body["scenario_id"] == scenario.id
    assert "published_at" in body


def test_publish_appears_in_library(client, db):
    gm = _make_user(db, "lib_gm")
    scenario = _make_scenario(db, gm, title="Published Library Scenario")

    client.post(f"/api/scenarios/{scenario.id}/publish", headers=_auth_header(gm))

    resp = client.get("/api/scenarios/library")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert scenario.id in ids


# ─── Library: clone ────────────────────────────────────────────────────────────

def test_clone_preserves_fields_resets_metadata(client, db):
    gm = _make_user(db, "clone_gm")
    src = _make_scenario(db, gm, title="Clone Source", published=True)

    player = _make_user(db, "clone_player", role="player")
    resp = client.post(f"/api/scenarios/{src.id}/clone", headers=_auth_header(player))
    assert resp.status_code == 200
    clone = resp.json()

    # Content preserved
    assert clone["title"] == "Clone Source (Clone)"
    assert clone["scenario_type"] == src.scenario_type
    assert clone["factions"] == json.loads(src.factions)
    assert clone["win_conditions"] == json.loads(src.win_conditions)

    # Identity fields reset
    assert clone["id"] != src.id
    assert clone["is_published"] is False
    assert clone["usage_count"] == 0
    assert clone["is_official"] is False
    assert clone["published_by_user_id"] is None


def test_clone_increments_usage_count(client, db):
    gm = _make_user(db, "usage_gm")
    src = _make_scenario(db, gm, title="Usage Count Scenario", published=True)
    client.post(f"/api/scenarios/{src.id}/publish", headers=_auth_header(gm))

    # Initial count should be 0
    lib = client.get("/api/scenarios/library").json()
    src_entry = next(i for i in lib["items"] if i["id"] == src.id)
    before = src_entry["usage_count"]

    client.post(f"/api/scenarios/{src.id}/clone", headers=_auth_header(gm))
    client.post(f"/api/scenarios/{src.id}/clone", headers=_auth_header(gm))

    lib2 = client.get("/api/scenarios/library").json()
    src_entry2 = next(i for i in lib2["items"] if i["id"] == src.id)
    assert src_entry2["usage_count"] == before + 2


# ─── Library: search ──────────────────────────────────────────────────────────

def test_library_search_by_title(client, db):
    gm = _make_user(db, "search_gm")
    s1 = _make_scenario(db, gm, title="Taiwan Strait Crisis", published=True)
    s2 = _make_scenario(db, gm, title="Baltic Defense Exercise", published=True)

    resp = client.get("/api/scenarios/library?q=Taiwan")
    data = resp.json()
    returned_ids = {i["id"] for i in data["items"]}
    assert s1.id in returned_ids
    assert s2.id not in returned_ids


def test_library_pagination(client, db):
    gm = _make_user(db, "page_gm")
    for i in range(5):
        _make_scenario(db, gm, title=f"Paged Scenario {i}", published=True)

    p1 = client.get("/api/scenarios/library?limit=3&page=1").json()
    p2 = client.get("/api/scenarios/library?limit=3&page=2").json()

    assert len(p1["items"]) == 3
    p1_ids = {i["id"] for i in p1["items"]}
    p2_ids = {i["id"] for i in p2["items"]}
    assert p1_ids.isdisjoint(p2_ids), "Pages must not overlap"


def test_library_unpublished_excluded(client, db):
    gm = _make_user(db, "unp_gm")
    private = _make_scenario(db, gm, title="Private Scenario — should not appear")

    resp = client.get("/api/scenarios/library")
    ids = {i["id"] for i in resp.json()["items"]}
    assert private.id not in ids
