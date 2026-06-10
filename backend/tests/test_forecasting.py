"""Tests for the per-turn probabilistic forecasting overlay.

Run from backend/:  python -m pytest tests/test_forecasting.py -v

Covers the deterministic scoring core (Brier, outcome resolution, calibration) plus
the API surface (submission guards, summary) and the optional AAR/briefing integration.
"""
import json
import pytest
from fastapi.testclient import TestClient

import database
import models
import forecasting
import briefing
from auth import hash_password, create_access_token


# ─── Fixtures / helpers ─────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    session = database.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


def _make_user(db, username="forecaster", role="game_master"):
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
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _make_scenario(db, user):
    factions = [
        {"faction_id": "blue_force", "name": "Blue", "side": "Blue", "role": "Player"},
        {"faction_id": "red_force", "name": "Red", "side": "Red", "role": "AI-controlled"},
    ]
    s = models.Scenario(
        title="Forecast Scenario",
        scenario_type="Tactical",
        timeframe="72 hours",
        geography=json.dumps({"region": "Baltics"}),
        situation=json.dumps({"summary": "Test."}),
        factions=json.dumps(factions),
        injects=json.dumps([]),
        win_conditions=json.dumps({"duration_turns": 6}),
        ai_notes="",
        created_by=user.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_session(db, user, scenario, forecasting_enabled=True, current_turn=1):
    sess = models.GameSession(
        scenario_id=scenario.id,
        title=scenario.title,
        status="Active",
        current_turn=current_turn,
        max_turns=6,
        time_per_turn_hours=12,
        faction_assignments=json.dumps([]),
        current_game_state=json.dumps({"faction_scores": []}),
        forecasting_enabled=forecasting_enabled,
        created_by=user.id,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


# ─── Brier score correctness ────────────────────────────────────────────────────

def test_brier_perfect_forecast_is_zero():
    forecast = {"p_blue_wins": 1.0, "p_red_wins": 0.0, "p_escalation": 1.0, "p_key_objective_captured": 0.0}
    outcome = {"blue_achieved": True, "red_achieved": False, "escalation_occurred": True, "key_objective_captured": False}
    assert forecasting.brier_score(forecast, outcome) == 0.0


def test_brier_worst_forecast_is_two():
    # Every probability maximally wrong: p=0 when it happens, p=1 when it doesn't.
    forecast = {"p_blue_wins": 0.0, "p_red_wins": 1.0, "p_escalation": 0.0, "p_key_objective_captured": 1.0}
    outcome = {"blue_achieved": True, "red_achieved": False, "escalation_occurred": True, "key_objective_captured": False}
    assert forecasting.brier_score(forecast, outcome) == 2.0


def test_brier_coinflip_is_half():
    forecast = {k: 0.5 for k in forecasting.QUESTIONS}
    outcome = {v: True for v in forecasting.QUESTIONS.values()}
    assert forecasting.brier_score(forecast, outcome) == 0.5


def test_brier_edge_p0_outcome1_component_is_two():
    # Single question wrong-at-the-extreme contributes 2.0; the other three perfect.
    forecast = {"p_blue_wins": 0.0, "p_red_wins": 0.0, "p_escalation": 0.0, "p_key_objective_captured": 0.0}
    outcome = {"blue_achieved": True, "red_achieved": False, "escalation_occurred": False, "key_objective_captured": False}
    # components: 2*(0-1)^2=2, 0, 0, 0 -> mean 0.5
    assert forecasting.brier_score(forecast, outcome) == 0.5


def test_brier_edge_p1_outcome0_component_is_two():
    forecast = {"p_blue_wins": 1.0, "p_red_wins": 0.0, "p_escalation": 0.0, "p_key_objective_captured": 0.0}
    outcome = {"blue_achieved": False, "red_achieved": False, "escalation_occurred": False, "key_objective_captured": False}
    assert forecasting.brier_score(forecast, outcome) == 0.5


def test_brier_clamps_out_of_range_probabilities():
    # p>1 clamps to 1, p<0 clamps to 0 — perfect forecast despite bad input.
    forecast = {"p_blue_wins": 5.0, "p_red_wins": -3.0, "p_escalation": 1.5, "p_key_objective_captured": -0.2}
    outcome = {"blue_achieved": True, "red_achieved": False, "escalation_occurred": True, "key_objective_captured": False}
    assert forecasting.brier_score(forecast, outcome) == 0.0


# ─── Binary outcome resolution heuristics ───────────────────────────────────────

_SIDE_MAP = {"blue_force": "Blue", "red_force": "Red"}


def _state(blue, red):
    return {"faction_scores": [
        {"faction_id": "blue_force", "score": blue},
        {"faction_id": "red_force", "score": red},
    ]}


def test_resolve_blue_achieved_when_blue_score_rises():
    out = forecasting.resolve_outcomes({}, _state(10, 10), _state(20, 10), _SIDE_MAP)
    assert out["blue_achieved"] is True
    assert out["red_achieved"] is False


def test_resolve_red_achieved_when_red_score_rises():
    out = forecasting.resolve_outcomes({}, _state(10, 10), _state(10, 25), _SIDE_MAP)
    assert out["red_achieved"] is True
    assert out["blue_achieved"] is False


def test_resolve_escalation_from_casualties():
    result = {"casualties": [{"unit_id": "u1", "strength_change": "Full→Critical"}]}
    out = forecasting.resolve_outcomes(result, _state(0, 0), _state(0, 0), _SIDE_MAP)
    assert out["escalation_occurred"] is True


def test_resolve_escalation_from_broken_morale_and_lost_c2():
    out_wtf = forecasting.resolve_outcomes(
        {"will_to_fight_changes": [{"unit_id": "u1", "to": "Broken"}]},
        _state(0, 0), _state(0, 0), _SIDE_MAP)
    out_c2 = forecasting.resolve_outcomes(
        {"c2_changes": [{"unit_id": "u1", "to": "Lost"}]},
        _state(0, 0), _state(0, 0), _SIDE_MAP)
    assert out_wtf["escalation_occurred"] is True
    assert out_c2["escalation_occurred"] is True


def test_resolve_no_escalation_when_quiet_turn():
    out = forecasting.resolve_outcomes({}, _state(0, 0), _state(0, 0), _SIDE_MAP)
    assert out["escalation_occurred"] is False
    assert out["key_objective_captured"] is False


def test_resolve_key_objective_from_terrain_change():
    result = {"terrain_changes": [{"location": "Hill 401", "to_faction": "blue_force"}]}
    out = forecasting.resolve_outcomes(result, _state(0, 0), _state(0, 0), _SIDE_MAP)
    assert out["key_objective_captured"] is True


# ─── Calibration rating thresholds ──────────────────────────────────────────────

def test_calibration_well_calibrated_within_tolerance():
    assert forecasting.calibration_rating(0.55, 0.50) == "Well-calibrated"


def test_calibration_overconfident_when_forecast_exceeds_outcome():
    assert forecasting.calibration_rating(0.80, 0.40) == "Overconfident"


def test_calibration_underconfident_when_forecast_below_outcome():
    assert forecasting.calibration_rating(0.30, 0.70) == "Underconfident"


# ─── Summary builder ────────────────────────────────────────────────────────────

def test_summary_averages_only_resolved_forecasts():
    rows = [
        {"turn_number": 1, "p_blue_wins": 1.0, "p_red_wins": 0.0, "p_escalation": 1.0,
         "p_key_objective_captured": 0.0, "blue_achieved": True, "red_achieved": False,
         "escalation_occurred": True, "key_objective_captured": False, "brier_score": 0.0,
         "rationale": "sure"},
        {"turn_number": 2, "p_blue_wins": 0.5, "p_red_wins": 0.5, "p_escalation": 0.5,
         "p_key_objective_captured": 0.5, "brier_score": None, "rationale": None},  # unresolved
    ]
    summary = forecasting.build_forecasting_summary(rows, total_turns=2)
    assert summary["forecasts_submitted"] == 2
    assert summary["forecasts_resolved"] == 1
    assert summary["average_brier_score"] == 0.0
    assert len(summary["turn_by_turn"]) == 2


def test_summary_empty_is_insufficient_data():
    summary = forecasting.build_forecasting_summary([], total_turns=0)
    assert summary["average_brier_score"] is None
    assert summary["calibration_rating"] == "Insufficient data"


# ─── API: submission guards ─────────────────────────────────────────────────────

_PAYLOAD = {"p_blue_wins": 0.6, "p_red_wins": 0.3, "p_escalation": 0.5,
            "p_key_objective_captured": 0.2, "rationale": "test"}


def test_forecast_submission_succeeds_before_adjudication(client, db):
    user = _make_user(db, "fc_submit")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=1)
    resp = client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                       json=_PAYLOAD, headers=_auth_header(user))
    assert resp.status_code == 200
    assert "forecast_id" in resp.json()


def test_forecast_rejected_when_forecasting_disabled(client, db):
    user = _make_user(db, "fc_disabled")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, forecasting_enabled=False, current_turn=1)
    resp = client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                       json=_PAYLOAD, headers=_auth_header(user))
    assert resp.status_code == 400


def test_forecast_rejected_for_non_current_turn(client, db):
    user = _make_user(db, "fc_wrongturn")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=3)
    resp = client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                       json=_PAYLOAD, headers=_auth_header(user))
    assert resp.status_code == 400


def test_forecast_rejected_after_turn_adjudicated(client, db):
    user = _make_user(db, "fc_adjudicated")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=1)
    db.add(models.TurnLog(
        session_id=session.id, turn_number=1,
        player_moves=json.dumps([]),
        adjudication=json.dumps({"narrative": "done"}),
    ))
    db.commit()
    resp = client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                       json=_PAYLOAD, headers=_auth_header(user))
    assert resp.status_code == 409


def test_forecast_resubmission_overwrites(client, db):
    user = _make_user(db, "fc_resubmit")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=1)
    h = _auth_header(user)
    client.post(f"/api/sessions/{session.id}/turns/1/forecast", json=_PAYLOAD, headers=h)
    client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                json={**_PAYLOAD, "p_blue_wins": 0.9}, headers=h)
    rows = db.query(models.TurnForecast).filter(
        models.TurnForecast.session_id == session.id).all()
    assert len(rows) == 1
    assert rows[0].p_blue_wins == 0.9


def test_forecasting_summary_endpoint_shape(client, db):
    user = _make_user(db, "fc_summary")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=1)
    client.post(f"/api/sessions/{session.id}/turns/1/forecast",
                json=_PAYLOAD, headers=_auth_header(user))
    resp = client.get(f"/api/sessions/{session.id}/forecasting-summary",
                     headers=_auth_header(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["forecasts_submitted"] == 1
    assert body["forecasts_resolved"] == 0  # not yet adjudicated
    assert "turn_by_turn" in body


# ─── Briefing integration ───────────────────────────────────────────────────────

def _resolved_forecast_row(turn=1):
    return {
        "turn_number": turn, "p_blue_wins": 1.0, "p_red_wins": 0.0, "p_escalation": 1.0,
        "p_key_objective_captured": 0.0, "blue_achieved": True, "red_achieved": False,
        "escalation_occurred": True, "key_objective_captured": False, "brier_score": 0.0,
        "rationale": "confident",
    }


_SCENARIO = {"title": "S", "factions": [
    {"faction_id": "blue_force", "side": "Blue"},
    {"faction_id": "red_force", "side": "Red"}]}
_META = {"session_id": "x", "session_title": "S", "status": "Active", "current_turn": 1, "max_turns": 6}


def test_briefing_includes_forecasting_accuracy_when_present():
    b = briefing.build_briefing(_SCENARIO, [], {}, _META, forecasts=[_resolved_forecast_row()])
    fa = b["forecasting_accuracy"]
    assert fa is not None
    assert fa["overall_brier_score"] == 0.0
    assert "methodology_note" in fa
    assert "calibration_summary" in fa
    assert fa["notable_mispredictions"] == []  # a perfect forecast has none
    md = briefing.briefing_to_markdown(b)
    assert "Forecasting Accuracy" in md
    assert "Notable Mispredictions" in md


def test_briefing_omits_forecasting_accuracy_without_forecasts():
    b = briefing.build_briefing(_SCENARIO, [], {}, _META)
    assert b["forecasting_accuracy"] is None
    md = briefing.briefing_to_markdown(b)
    assert "Forecasting Accuracy" not in md


def test_briefing_omits_forecasting_accuracy_with_only_unresolved():
    # A forecast submitted but not yet adjudicated (brier_score None) yields no block.
    unresolved = {"turn_number": 1, "p_blue_wins": 0.5, "p_red_wins": 0.5,
                  "p_escalation": 0.5, "p_key_objective_captured": 0.5, "brier_score": None}
    b = briefing.build_briefing(_SCENARIO, [], {}, _META, forecasts=[unresolved])
    assert b["forecasting_accuracy"] is None


def test_forecasting_accuracy_flags_confident_misprediction():
    # p_blue_wins=1.0 but Blue did NOT achieve -> component 2.0, a notable misprediction.
    row = {"turn_number": 2, "p_blue_wins": 1.0, "p_red_wins": 0.0, "p_escalation": 0.0,
           "p_key_objective_captured": 0.0, "blue_achieved": False, "red_achieved": False,
           "escalation_occurred": False, "key_objective_captured": False, "brier_score": 0.5}
    fa = forecasting.build_forecasting_accuracy([row])
    assert fa["overall_brier_score"] == 0.5
    notable = fa["notable_mispredictions"]
    assert len(notable) == 1
    assert notable[0]["question"] == "Blue achieves objectives"
    assert notable[0]["outcome"] is False
    assert notable[0]["brier_component"] == 2.0
    assert len(fa["turn_calibration"]) == 1


def test_briefing_pdf_renders_with_forecasting_chart():
    from routers import aar
    b = briefing.build_briefing(_SCENARIO, [], {}, _META, forecasts=[
        _resolved_forecast_row(turn=1),
        {"turn_number": 2, "p_blue_wins": 0.9, "p_red_wins": 0.1, "p_escalation": 0.2,
         "p_key_objective_captured": 0.8, "blue_achieved": False, "red_achieved": True,
         "escalation_occurred": False, "key_objective_captured": False, "brier_score": 1.34},
    ])
    pdf = aar.build_briefing_pdf(b)
    assert pdf[:4] == b"%PDF"


# ─── AAR Section 8 integration ──────────────────────────────────────────────────

_FAKE_AAR = {
    "metadata": {"exercise_title": "T", "duration_turns": 1},
    "section_1_executive_summary": {"bottom_line_up_front": "x", "scenario_overview": "x", "outcome": "x"},
    "section_6_implications": {"doctrine_implications": "x"},
}


async def _fake_generate_aar(*a, **k):
    return dict(_FAKE_AAR)


async def _fake_narrative(*a, **k):
    return "You were well-calibrated."


def test_aar_section_8_absent_without_forecasts(client, db, monkeypatch):
    import ai_client
    monkeypatch.setattr(ai_client, "generate_aar", _fake_generate_aar)
    user = _make_user(db, "aar_nofc")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, forecasting_enabled=False, current_turn=2)
    resp = client.post(f"/api/sessions/{session.id}/aar", json={}, headers=_auth_header(user))
    assert resp.status_code == 200
    assert "section_8_forecasting_accuracy" not in resp.json()["content"]


def test_aar_section_8_present_with_forecasts(client, db, monkeypatch):
    import ai_client
    monkeypatch.setattr(ai_client, "generate_aar", _fake_generate_aar)
    monkeypatch.setattr(ai_client, "forecasting_narrative", _fake_narrative)
    user = _make_user(db, "aar_fc")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, forecasting_enabled=True, current_turn=2)
    db.add(models.TurnForecast(
        session_id=session.id, turn_number=1, user_id=user.id,
        p_blue_wins=1.0, p_red_wins=0.0, p_escalation=1.0, p_key_objective_captured=0.0,
        blue_achieved=True, red_achieved=False, escalation_occurred=True,
        key_objective_captured=False, brier_score=0.0,
    ))
    db.commit()
    resp = client.post(f"/api/sessions/{session.id}/aar", json={}, headers=_auth_header(user))
    assert resp.status_code == 200
    s8 = resp.json()["content"].get("section_8_forecasting_accuracy")
    assert s8 is not None
    assert s8["average_brier_score"] == 0.0
    assert s8["narrative"] == "You were well-calibrated."
    assert len(s8["turn_by_turn"]) == 1


# ─── Resolution hook in /adjudicate ─────────────────────────────────────────────

def test_adjudicate_resolves_forecast_and_scores_brier(client, db, monkeypatch):
    import ai_client

    # Mock the Claude adjudication: Blue gains 10 points, no escalation, no terrain change.
    async def _fake_adjudicate(*a, **k):
        result = {
            "narrative": "Blue advances.",
            "score_changes": [{"faction_id": "blue_force", "dimension": "objectives", "change": 10}],
            "casualties": [], "terrain_changes": [], "will_to_fight_changes": [], "c2_changes": [],
            "detection_updates": [], "logistics_impacts": [],
        }
        audit = {
            "function_name": "adjudicate_turn", "ai_inputs": "{}", "ai_system_prompt": "",
            "ai_user_message": "", "ai_response_full": "[]", "ai_reasoning": "",
        }
        return result, audit

    monkeypatch.setattr(ai_client, "adjudicate_turn", _fake_adjudicate)

    user = _make_user(db, "adj_resolve")
    scenario = _make_scenario(db, user)
    session = _make_session(db, user, scenario, current_turn=1)
    # Seed faction scores so a Blue gain is measurable.
    session.current_game_state = json.dumps({
        "faction_scores": [
            {"faction_id": "blue_force", "side": "Blue", "score": 0},
            {"faction_id": "red_force", "side": "Red", "score": 0},
        ],
        "unit_status": [],
    })
    db.add(models.TurnForecast(
        session_id=session.id, turn_number=1, user_id=user.id,
        p_blue_wins=0.8, p_red_wins=0.2, p_escalation=0.1, p_key_objective_captured=0.1,
    ))
    db.commit()

    resp = client.post(f"/api/sessions/{session.id}/adjudicate",
                       json={"turn_number": 1, "blue_moves": [], "red_moves": []},
                       headers=_auth_header(user))
    assert resp.status_code == 200

    db.expire_all()
    fc = db.query(models.TurnForecast).filter(
        models.TurnForecast.session_id == session.id).first()
    assert fc.resolved_at is not None
    assert fc.blue_achieved is True
    assert fc.escalation_occurred is False
    assert fc.key_objective_captured is False
    assert fc.brier_score is not None
    refreshed = db.query(models.GameSession).filter(
        models.GameSession.id == session.id).first()
    assert refreshed.total_brier_score is not None
