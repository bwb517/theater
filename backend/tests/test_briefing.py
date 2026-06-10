"""Tests for the deterministic briefing-export builder.

Pure-logic tests for backend/briefing.py (turning-point detection, outcome
thresholds, format consistency) plus PDF-robustness tests for
routers.aar.build_briefing_pdf. The briefing has no LLM in the loop, so every
assertion here is exact and reproducible — that determinism is the whole point of
the feature.

Run from backend/:  python -m pytest tests/test_briefing.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import briefing


# ---------------------------------------------------------------------------
# Builders for synthetic game data
# ---------------------------------------------------------------------------

SCENARIO = {
    "title": "Test Scenario",
    "scenario_type": "Tactical",
    "classification": "UNCLASSIFIED",
    "factions": [
        {"faction_id": "BLUE", "side": "Blue", "name": "Blue Force"},
        {"faction_id": "RED", "side": "Red", "name": "Red Force"},
    ],
}


def _units(blue_manning, red_manning):
    return [
        {"unit_id": "BLU-1", "faction_id": "BLUE", "manning": blue_manning},
        {"unit_id": "RED-1", "faction_id": "RED", "manning": red_manning},
    ]


def _row(turn_number, blue_manning, red_manning, outcome=None):
    """One AdjudicationLog-shaped row: unit_status is the START-of-turn snapshot."""
    return {
        "turn_number": turn_number,
        "ai_inputs": {
            "unit_status": _units(blue_manning, red_manning),
            "blue_moves": [],
            "red_moves": [],
        },
        "turn_outcome": outcome or {"turn_number": turn_number},
    }


def _final(blue_manning, red_manning, blue_score, red_score):
    return {
        "unit_status": _units(blue_manning, red_manning),
        "faction_scores": [
            {"faction_id": "BLUE", "name": "Blue Force", "score": blue_score, "objective_status": "Achieved"},
            {"faction_id": "RED", "name": "Red Force", "score": red_score, "objective_status": "In Progress"},
        ],
    }


META = {"session_id": "s1", "session_title": "Test", "status": "Complete",
        "current_turn": 4, "max_turns": 6}


# ---------------------------------------------------------------------------
# Turning-point correctness
# ---------------------------------------------------------------------------

def test_largest_strength_collapse_is_top_turning_point():
    # Red collapses during turn 3 (start-of-turn4 snapshot drops 96 -> 50).
    rows = [
        _row(1, 100, 100),
        _row(2, 99, 98, {"turn_number": 2, "terrain_changes": [{"location": "Hill A", "to_faction": "BLUE"},
                                                                {"location": "Hill B", "to_faction": "BLUE"}]}),
        _row(3, 98, 96),
        _row(4, 97, 50),
    ]
    final_state = _final(96, 45, 60, 40)
    b = briefing.build_briefing(SCENARIO, rows, final_state, META)

    tps = b["turning_points"]
    assert tps[0]["turn_number"] == 3, "turn 3's Red collapse must rank first"
    # Turn 2 carries two terrain flips -> second-biggest impact.
    assert tps[1]["turn_number"] == 2
    assert tps[0]["impact_score"] > tps[1]["impact_score"]
    assert "Decisive" in tps[0]["impact_on_outcome"]


def test_turning_points_capped_at_three():
    rows = [_row(i, 100 - i, 100 - 2 * i) for i in range(1, 6)]
    b = briefing.build_briefing(SCENARIO, rows, _final(94, 88, 55, 45), META)
    assert len(b["turning_points"]) == briefing.TOP_N_TURNING_POINTS == 3


def test_single_turn_game_yields_at_most_one_turning_point():
    rows = [_row(1, 100, 80)]
    b = briefing.build_briefing(SCENARIO, rows, _final(100, 60, 55, 45), META)
    assert len(b["turning_points"]) <= 1


def test_tie_break_is_stable_on_turn_number():
    # Two turns with identical impact (one terrain flip each) -> lower turn first.
    metrics = [
        {"turn_number": 5, "blue_delta": 0, "red_delta": 0, "force_ratio_delta": 0,
         "net_score_swing": 0, "terrain_count": 1, "morale_c2_count": 0, "decisive_moment": None},
        {"turn_number": 2, "blue_delta": 0, "red_delta": 0, "force_ratio_delta": 0,
         "net_score_swing": 0, "terrain_count": 1, "morale_c2_count": 0, "decisive_moment": None},
    ]
    tps = briefing.identify_turning_points(metrics)
    assert [t["turn_number"] for t in tps] == [2, 5]
    assert tps[0]["impact_score"] == tps[1]["impact_score"]


# ---------------------------------------------------------------------------
# Outcome thresholds
# ---------------------------------------------------------------------------

def test_outcome_blue_won():
    b = briefing.build_briefing(SCENARIO, [_row(1, 100, 90)], _final(100, 80, 60, 40), META)
    assert b["outcome"] == "Blue won"


def test_outcome_red_won():
    b = briefing.build_briefing(SCENARIO, [_row(1, 90, 100)], _final(80, 100, 40, 60), META)
    assert b["outcome"] == "Red won"


def test_outcome_stalemate_within_threshold():
    # |50 - 48| = 2 <= STALEMATE_THRESHOLD (5)
    b = briefing.build_briefing(SCENARIO, [_row(1, 90, 90)], _final(85, 85, 50, 48), META)
    assert b["outcome"] == "Stalemate"


def test_stalemate_boundary_is_inclusive():
    assert briefing._determine_outcome(50, 45) == "Stalemate"   # diff == threshold
    assert briefing._determine_outcome(51, 45) == "Blue won"    # diff > threshold


# ---------------------------------------------------------------------------
# Strength metric
# ---------------------------------------------------------------------------

def test_unit_health_prefers_manning_then_strength_enum():
    assert briefing.unit_health({"manning": 73}) == 73.0
    assert briefing.unit_health({"strength": "Full"}) == 100.0
    assert briefing.unit_health({"strength": "Destroyed"}) == 0.0
    assert briefing.unit_health({}) is None


def test_side_strength_is_mean_and_none_when_absent():
    side_map = {"BLUE": "Blue", "RED": "Red"}
    units = _units(80, 40)
    assert briefing.side_strength(units, side_map, "Blue") == 80.0
    assert briefing.side_strength([], side_map, "Blue") is None


# ---------------------------------------------------------------------------
# Markdown / JSON consistency (same data, different formats)
# ---------------------------------------------------------------------------

def test_markdown_matches_json_content():
    rows = [
        _row(1, 100, 100),
        _row(2, 98, 80, {"turn_number": 2, "decisive_moment": "Red armor ambushed",
                         "terrain_changes": [{"location": "Ford", "to_faction": "BLUE"}]}),
        _row(3, 97, 60),
    ]
    b = briefing.build_briefing(SCENARIO, rows, _final(96, 55, 62, 38), META)
    md = briefing.briefing_to_markdown(b)

    # Outcome string identical across formats.
    assert b["outcome"] in md
    # Same number of timeline turns rendered (timeline headers carry no em-dash,
    # unlike turning-point headers "### Turn N — ...").
    timeline_headers = [l for l in md.splitlines()
                        if l.startswith("### Turn ") and "—" not in l]
    assert len(timeline_headers) == len(b["timeline"])
    # Every turning-point description appears verbatim.
    for tp in b["turning_points"]:
        assert tp["description"] in md
    # Executive summary carried through.
    assert b["executive_summary"] in md


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

def test_no_rows_still_builds_valid_briefing():
    b = briefing.build_briefing(SCENARIO, [], _final(90, 70, 55, 45), META)
    assert b["turning_points"] == []
    assert b["timeline"] == []
    assert b["outcome"] == "Blue won"
    assert len(b["state_evolution"]) == 1   # final snapshot only


def test_rows_without_unit_status_skip_strength_deltas():
    # Fallback shape (TurnLog-derived): no unit_status -> no strength deltas.
    rows = [{"turn_number": 1, "ai_inputs": {"unit_status": [], "blue_moves": [], "red_moves": []},
             "turn_outcome": {"turn_number": 1, "narrative": "Quiet turn."}}]
    b = briefing.build_briefing(SCENARIO, rows, _final(90, 70, 55, 45), META)
    assert len(b["timeline"]) == 1
    assert b["timeline"][0]["state_changes"]["blue_strength_delta"] is None
    assert b["turning_points"] == []


# ---------------------------------------------------------------------------
# PDF robustness (don't crash on edge cases)
# ---------------------------------------------------------------------------

def _import_pdf_builder():
    from routers.aar import build_briefing_pdf
    return build_briefing_pdf


def test_pdf_builds_for_normal_briefing():
    build_briefing_pdf = _import_pdf_builder()
    b = briefing.build_briefing(SCENARIO, [_row(1, 100, 80), _row(2, 95, 60)],
                                _final(90, 55, 60, 40), META)
    pdf = build_briefing_pdf(b)
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000


def test_pdf_survives_long_names_and_special_characters():
    build_briefing_pdf = _import_pdf_builder()
    nasty_scenario = {
        "title": "A & B <Recon> \"Quotes\" " + "X" * 200,
        "scenario_type": "Gray-Zone & <Hybrid>",
        "classification": "UNCLASSIFIED",
        "factions": [
            {"faction_id": "BLUE", "side": "Blue", "name": "Blue & <Allies>"},
            {"faction_id": "RED", "side": "Red", "name": "Red \"OPFOR\" ⬛"},
        ],
    }
    outcome = {"turn_number": 1, "decisive_moment": "Strike on grid <047> & <052>",
               "narrative": "Fires & maneuver <combined> caused 50% losses",
               "terrain_changes": [{"location": "Hill <A&B>", "to_faction": "BLUE"}]}
    rows = [_row(1, 100, 100, outcome), _row(2, 90, 40, outcome)]
    b = briefing.build_briefing(nasty_scenario, rows, _final(85, 30, 70, 20), META)
    pdf = build_briefing_pdf(b)
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000


def test_pdf_builds_for_empty_game():
    build_briefing_pdf = _import_pdf_builder()
    b = briefing.build_briefing(SCENARIO, [], {}, META)
    pdf = build_briefing_pdf(b)
    assert pdf[:4] == b"%PDF"
