"""Tests for the deterministic rules layer.

Pure-module tests: import only rules_engine + game_consts (no DB/FastAPI), so they
run under bare python (`python backend/tests/test_rules_engine.py`) or pytest.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rules_engine
from game_consts import haversine_km


def _unit(uid="BLUE-1", **kw):
    u = {
        "unit_id": uid,
        "faction_id": "BLUE",
        "type": "Infantry",
        "strength": "Full",
        "manning": 100,
        "supply": {"ammo": 100, "fuel": 100, "maintenance": 100, "munitions": None},
        "location": {"lat": 50.0, "lng": 20.0},
    }
    u.update(kw)
    return u


def _state(units):
    return {"unit_status": units, "faction_scores": [{"faction_id": "BLUE", "score": 50}]}


# --- validate_game_state -------------------------------------------------

def test_validate_clean_state_ok():
    assert rules_engine.validate_game_state(_state([_unit()])) == []


def test_validate_flags_duplicate_unit_ids():
    problems = rules_engine.validate_game_state(_state([_unit("X"), _unit("X")]))
    assert any("duplicate" in p for p in problems)


def test_validate_flags_out_of_range_manning():
    problems = rules_engine.validate_game_state(_state([_unit(manning=150)]))
    assert any("manning" in p for p in problems)


def test_validate_flags_bad_enum_and_coords():
    bad = _unit(strength="Pristine", location={"lat": 200, "lng": 0})
    problems = rules_engine.validate_game_state(_state([bad]))
    assert any("strength" in p for p in problems)
    assert any("latitude" in p for p in problems)


# --- apply_adjudication: movement ---------------------------------------

def test_teleport_clamped_to_reachable_point():
    # Infantry @ 4 km/h * 24h = 96 km cap; asked to jump ~9000 km away.
    unit = _unit(type="Infantry", location={"lat": 50.0, "lng": 20.0})
    result = {"position_updates": [{"unit_id": "BLUE-1", "new_lat": 0.0, "new_lng": 100.0}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    moved = new_state["unit_status"][0]["location"]
    dist = haversine_km(50.0, 20.0, moved["lat"], moved["lng"])
    assert dist <= 96 + 1  # clamped to cap (+rounding tolerance)
    assert any(v["category"] == "position" for v in violations)


def test_destroyed_unit_cannot_move():
    unit = _unit(strength="Destroyed")
    result = {"position_updates": [{"unit_id": "BLUE-1", "new_lat": 50.1, "new_lng": 20.1}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["location"] == {"lat": 50.0, "lng": 20.0}
    assert any("destroyed" in v["detail"] for v in violations)


# --- apply_adjudication: unknown unit -----------------------------------

def test_unknown_unit_dropped_with_violation():
    result = {"casualties": [{"unit_id": "GHOST-9", "strength_change": "Full->Critical"}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([_unit()]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["strength"] == "Full"  # untouched
    assert any(v["category"] == "unknown_unit" for v in violations)


# --- apply_adjudication: strength ladder --------------------------------

def test_illegal_strength_upgrade_rejected():
    unit = _unit(strength="Critical")
    result = {"casualties": [{"unit_id": "BLUE-1", "strength_change": "Critical->Full"}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["strength"] == "Critical"
    assert any(v["category"] == "strength" for v in violations)


def test_strength_upgrade_allowed_with_reinforcement():
    unit = _unit(strength="Critical")
    result = {"casualties": [{"unit_id": "BLUE-1", "strength_change": "Critical->Degraded", "reinforcement": True}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["strength"] == "Degraded"


# --- apply_adjudication: munitions --------------------------------------

def test_munitions_overspend_clamped_to_fires_ordered():
    unit = _unit(type="Artillery", supply={"ammo": 100, "fuel": 100, "maintenance": 100,
                                            "munitions": {"count": 6, "max": 6, "type": "GMLRS"}})
    blue_moves = [{"faction_id": "BLUE", "moves": {"fires": [{"unit_id": "BLUE-1"}, {"unit_id": "BLUE-1"}]}}]
    result = {"supply_changes": [{"unit_id": "BLUE-1", "munitions_delta": -5}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=blue_moves, red_moves=[], turn_hours=24,
    )
    # only 2 fires ordered -> spend clamped to 2 -> count 6-2 = 4
    assert new_state["unit_status"][0]["supply"]["munitions"]["count"] == 4
    assert any(v["category"] == "munitions" for v in violations)


# --- apply_adjudication: supply -----------------------------------------

def test_supply_increase_without_resupply_order_ignored():
    unit = _unit(supply={"ammo": 30, "fuel": 100, "maintenance": 100, "munitions": None})
    result = {"supply_changes": [{"unit_id": "BLUE-1", "ammo_delta": 50}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["supply"]["ammo"] == 30  # unchanged
    assert any(v["category"] == "supply" for v in violations)


def test_supply_increase_allowed_with_resupply_order():
    unit = _unit(supply={"ammo": 30, "fuel": 100, "maintenance": 100, "munitions": None})
    blue_moves = [{"faction_id": "BLUE", "moves": {"logistics": [{"unit_id": "BLUE-1", "action": "Resupply"}]}}]
    result = {"supply_changes": [{"unit_id": "BLUE-1", "ammo_delta": 50}]}
    new_state, _ = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=blue_moves, red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["supply"]["ammo"] == 80


def test_supply_consumption_allowed_and_floored():
    unit = _unit(supply={"ammo": 20, "fuel": 100, "maintenance": 100, "munitions": None})
    result = {"supply_changes": [{"unit_id": "BLUE-1", "ammo_delta": -50}]}
    new_state, _ = rules_engine.apply_adjudication(
        _state([unit]), result, blue_moves=[], red_moves=[], turn_hours=24,
    )
    assert new_state["unit_status"][0]["supply"]["ammo"] == 0


# --- apply_adjudication: scores -----------------------------------------

def test_score_change_capped_per_turn():
    result = {"score_changes": [{"faction_id": "BLUE", "change": 999}]}
    new_state, violations = rules_engine.apply_adjudication(
        _state([_unit()]), result, blue_moves=[], red_moves=[], turn_hours=24, score_max=100,
    )
    # 50 + capped(25) = 75
    assert new_state["faction_scores"][0]["score"] == 75
    assert any(v["category"] == "score" for v in violations)


# --- standalone runner ---------------------------------------------------

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
