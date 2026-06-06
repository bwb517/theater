"""Deterministic validation/rules layer between LLM adjudication and game state.

The LLM proposes turn outcomes; this module is the single authority that decides
which of those proposed mutations are physically legal before they touch the
persisted game state. It is pure (no DB, no network, no I/O) so it can be unit
tested in isolation.

Two entry points:
  - validate_game_state(state) -> list[str]   (schema/sanity check)
  - apply_adjudication(state, result, ...) -> (new_state, list[RuleViolation])
"""
from __future__ import annotations

import copy
import re

from game_consts import (
    MOVEMENT_RATES,
    DEFAULT_MOVEMENT_RATE,
    DEFAULT_TURN_HOURS,
    STRENGTH_RANK,
    VALID_STRENGTHS,
    VALID_WTF,
    VALID_C2,
    haversine_km,
    initial_bearing_deg,
    point_at_distance,
)

# Largest score swing a single faction may take in one turn before it's capped.
MAX_SCORE_CHANGE_PER_TURN = 25


def _violation(category: str, unit_id, detail: str) -> dict:
    return {"category": category, "unit_id": unit_id, "detail": detail}


def parse_new_strength(raw: str):
    """Resulting strength from 'Old->New', 'Old→New', or bare 'New'. None if invalid."""
    if not raw:
        return None
    parts = re.split(r"[→>\-]+", str(raw))
    candidate = parts[-1].strip().title()
    return candidate if candidate in VALID_STRENGTHS else None


# ---------------------------------------------------------------------------
# State schema validation
# ---------------------------------------------------------------------------

def validate_game_state(state: dict) -> list[str]:
    """Return a list of human-readable problems with a game state. Empty == valid."""
    problems: list[str] = []
    if not isinstance(state, dict):
        return ["game_state is not an object"]

    units = state.get("unit_status", [])
    if not isinstance(units, list):
        return ["unit_status must be a list"]

    seen_ids: set = set()
    faction_ids: set = set()
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            problems.append(f"unit_status[{i}] is not an object")
            continue
        uid = u.get("unit_id")
        if not uid:
            problems.append(f"unit_status[{i}] missing unit_id")
        elif uid in seen_ids:
            problems.append(f"duplicate unit_id '{uid}'")
        else:
            seen_ids.add(uid)
        fid = u.get("faction_id")
        if not fid:
            problems.append(f"unit '{uid}' missing faction_id")
        else:
            faction_ids.add(fid)

        strength = u.get("strength")
        if strength is not None and strength not in VALID_STRENGTHS:
            problems.append(f"unit '{uid}' has invalid strength '{strength}'")
        wtf = u.get("will_to_fight")
        if wtf is not None and wtf not in VALID_WTF:
            problems.append(f"unit '{uid}' has invalid will_to_fight '{wtf}'")
        c2 = u.get("c2_status")
        if c2 is not None and c2 not in VALID_C2:
            problems.append(f"unit '{uid}' has invalid c2_status '{c2}'")

        manning = u.get("manning")
        if manning is not None and (not isinstance(manning, (int, float)) or not (0 <= manning <= 100)):
            problems.append(f"unit '{uid}' manning out of range: {manning}")

        supply = u.get("supply")
        if isinstance(supply, dict):
            for key in ("ammo", "fuel", "maintenance"):
                v = supply.get(key)
                if v is not None and (not isinstance(v, (int, float)) or not (0 <= v <= 100)):
                    problems.append(f"unit '{uid}' supply.{key} out of range: {v}")

        loc = u.get("location")
        if isinstance(loc, dict):
            lat, lng = loc.get("lat"), loc.get("lng")
            if lat is not None and (not isinstance(lat, (int, float)) or not (-90 <= lat <= 90)):
                problems.append(f"unit '{uid}' latitude out of range: {lat}")
            if lng is not None and (not isinstance(lng, (int, float)) or not (-180 <= lng <= 180)):
                problems.append(f"unit '{uid}' longitude out of range: {lng}")

    # Note: faction_scores may reference factions that have no units yet
    # (e.g., reinforcements not yet arrived), so we don't cross-check against
    # faction_ids derived from unit_status here.

    return problems


# ---------------------------------------------------------------------------
# Order collection (used to authorize supply/munitions changes)
# ---------------------------------------------------------------------------

def _collect_orders(blue_moves: list, red_moves: list) -> tuple[dict, set]:
    """Return (fires_count_by_unit_id, resupplied_unit_ids) across both sides."""
    fires_by_unit: dict[str, int] = {}
    resupply_units: set = set()
    for side in (blue_moves or []) + (red_moves or []):
        if not isinstance(side, dict):
            continue
        moves = side.get("moves", {})
        if not isinstance(moves, dict):
            continue
        for f in moves.get("fires", []) or []:
            uid = f.get("unit_id") if isinstance(f, dict) else None
            if uid:
                fires_by_unit[uid] = fires_by_unit.get(uid, 0) + 1
        for lg in moves.get("logistics", []) or []:
            if not isinstance(lg, dict):
                continue
            uid = lg.get("unit_id") or lg.get("target_unit_id")
            if uid:
                resupply_units.add(uid)
    return fires_by_unit, resupply_units


def _bbox(geography) -> dict | None:
    """Extract a {min_lat,max_lat,min_lng,max_lng} bbox from scenario geography, if present."""
    if not isinstance(geography, dict):
        return None
    b = geography.get("bounds") or geography.get("bbox")
    if not isinstance(b, dict):
        return None
    try:
        return {
            "min_lat": float(b["min_lat"]), "max_lat": float(b["max_lat"]),
            "min_lng": float(b["min_lng"]), "max_lng": float(b["max_lng"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _clamp_position(unit, new_lat, new_lng, turn_hours, bbox, violations) -> bool:
    """Move `unit` toward (new_lat,new_lng), clamped to feasible range + bbox.

    Returns True if the unit's location was changed.
    """
    uid = unit.get("unit_id")
    try:
        new_lat = float(new_lat)
        new_lng = float(new_lng)
    except (TypeError, ValueError):
        violations.append(_violation("position", uid, "non-numeric coordinates; move ignored"))
        return False
    if not (-90 <= new_lat <= 90) or not (-180 <= new_lng <= 180):
        violations.append(_violation("position", uid, f"coordinates out of range ({new_lat},{new_lng}); move ignored"))
        return False

    loc = unit.get("location") or {}
    from_lat, from_lng = loc.get("lat"), loc.get("lng")
    rate = MOVEMENT_RATES.get(unit.get("type", ""), DEFAULT_MOVEMENT_RATE)

    if from_lat is not None and from_lng is not None:
        if rate == 0:
            violations.append(_violation("position", uid, f"unit type '{unit.get('type')}' cannot move; move ignored"))
            return False
        max_km = rate * turn_hours
        dist = haversine_km(float(from_lat), float(from_lng), new_lat, new_lng)
        if dist > max_km:
            bearing = initial_bearing_deg(float(from_lat), float(from_lng), new_lat, new_lng)
            new_lat, new_lng = point_at_distance(float(from_lat), float(from_lng), bearing, max_km)
            violations.append(_violation(
                "position", uid,
                f"requested {dist:.0f} km exceeds {max_km:.0f} km cap; clamped to reachable point",
            ))

    if bbox:
        clamped = False
        if new_lat < bbox["min_lat"]:
            new_lat, clamped = bbox["min_lat"], True
        elif new_lat > bbox["max_lat"]:
            new_lat, clamped = bbox["max_lat"], True
        if new_lng < bbox["min_lng"]:
            new_lng, clamped = bbox["min_lng"], True
        elif new_lng > bbox["max_lng"]:
            new_lng, clamped = bbox["max_lng"], True
        if clamped:
            violations.append(_violation("position", uid, "destination outside scenario bounds; clamped to edge"))

    new_loc = dict(loc)
    new_loc["lat"] = new_lat
    new_loc["lng"] = new_lng
    unit["location"] = new_loc
    return True


# ---------------------------------------------------------------------------
# Adjudication apply
# ---------------------------------------------------------------------------

def apply_adjudication(
    state: dict,
    result: dict,
    *,
    blue_moves: list | None = None,
    red_moves: list | None = None,
    turn_hours: float | None = None,
    geography: dict | None = None,
    score_max: float = 100,
) -> tuple[dict, list]:
    """Apply an LLM adjudication `result` to `state` under hard rule constraints.

    Returns (new_state, violations). `state` is not mutated; a deep copy is returned.
    """
    state = copy.deepcopy(state)
    violations: list = []
    turn_hours = turn_hours or DEFAULT_TURN_HOURS
    bbox = _bbox(geography)
    fires_by_unit, resupply_units = _collect_orders(blue_moves, red_moves)

    unit_map = {u["unit_id"]: u for u in state.get("unit_status", []) if isinstance(u, dict) and u.get("unit_id")}

    def _resolve(entry, key="unit_id"):
        uid = entry.get(key) if isinstance(entry, dict) else None
        unit = unit_map.get(uid)
        if uid and unit is None:
            violations.append(_violation("unknown_unit", uid, f"{key} not in game state; entry dropped"))
        return unit

    # --- Scores: clamp per-turn swing and final value to [0, score_max] ---
    for sc in result.get("score_changes", []) or []:
        fid = sc.get("faction_id")
        change = sc.get("change", 0) or 0
        if abs(change) > MAX_SCORE_CHANGE_PER_TURN:
            violations.append(_violation("score", fid, f"change {change} exceeds per-turn cap; clamped"))
            change = MAX_SCORE_CHANGE_PER_TURN if change > 0 else -MAX_SCORE_CHANGE_PER_TURN
        for fs in state.get("faction_scores", []) or []:
            if fs.get("faction_id") == fid:
                new_score = max(0, min(score_max, fs.get("score", 0) + change))
                fs["score"] = new_score

    # --- Casualties: monotonic strength degradation + manning ---
    for cas in result.get("casualties", []) or []:
        unit = _resolve(cas)
        if not unit:
            continue
        new_strength = parse_new_strength(cas.get("strength_change", ""))
        if new_strength:
            cur = unit.get("strength", "Full")
            cur_rank = STRENGTH_RANK.get(cur, 0)
            new_rank = STRENGTH_RANK[new_strength]
            if new_rank < cur_rank and not cas.get("reinforcement"):
                violations.append(_violation(
                    "strength", unit.get("unit_id"),
                    f"illegal upgrade {cur}->{new_strength} without reinforcement; kept {cur}",
                ))
            else:
                unit["strength"] = new_strength
                if new_strength == "Destroyed":
                    unit["manning"] = 0
                elif new_strength == "Critical":
                    unit["manning"] = min(unit.get("manning", 100), 35)
        mc = cas.get("manning_change", 0) or 0
        if mc:
            unit["manning"] = max(0, min(100, unit.get("manning", 100) + mc))

    # --- Supply / munitions: consumption allowed, increases need a resupply order ---
    for sc in result.get("supply_changes", []) or []:
        unit = _resolve(sc)
        if not unit:
            continue
        uid = unit.get("unit_id")
        supply = unit.setdefault("supply", {"ammo": 100, "fuel": 100, "maintenance": 100, "munitions": None})
        for key, delta_key in (("ammo", "ammo_delta"), ("fuel", "fuel_delta"), ("maintenance", "maintenance_delta")):
            delta = sc.get(delta_key, 0) or 0
            if delta > 0 and uid not in resupply_units:
                violations.append(_violation("supply", uid, f"{key} increase without resupply order; ignored"))
                delta = 0
            supply[key] = max(0, min(100, supply.get(key, 100) + delta))

        munitions = supply.get("munitions")
        mdelta = sc.get("munitions_delta", 0) or 0
        if munitions is not None and mdelta:
            if mdelta > 0 and uid not in resupply_units:
                violations.append(_violation("munitions", uid, "munitions increase without resupply order; ignored"))
                mdelta = 0
            elif mdelta < 0:
                issued = fires_by_unit.get(uid, 0)
                if abs(mdelta) > issued:
                    violations.append(_violation(
                        "munitions", uid,
                        f"claimed spend {abs(mdelta)} exceeds {issued} fires ordered; clamped",
                    ))
                    mdelta = -issued
            munitions["count"] = max(0, min(munitions.get("max", 99), munitions.get("count", 0) + mdelta))

    # --- Will-to-fight ---
    for wtf in result.get("will_to_fight_changes", []) or []:
        unit = _resolve(wtf)
        if unit and wtf.get("to") in VALID_WTF:
            unit["will_to_fight"] = wtf["to"]
        elif unit:
            violations.append(_violation("will_to_fight", unit.get("unit_id"), f"invalid value '{wtf.get('to')}'; ignored"))

    # --- C2 status ---
    for c2 in result.get("c2_changes", []) or []:
        unit = _resolve(c2)
        if unit and c2.get("to") in VALID_C2:
            unit["c2_status"] = c2["to"]
        elif unit:
            violations.append(_violation("c2", unit.get("unit_id"), f"invalid value '{c2.get('to')}'; ignored"))

    # --- Position updates (movement-clamped) ---
    position_updates = result.get("position_updates") or []
    for pu in position_updates:
        unit = _resolve(pu)
        if unit and pu.get("new_lat") is not None and pu.get("new_lng") is not None:
            if unit.get("strength") == "Destroyed":
                violations.append(_violation("position", unit.get("unit_id"), "destroyed unit cannot move; ignored"))
                continue
            _clamp_position(unit, pu["new_lat"], pu["new_lng"], turn_hours, bbox, violations)

    # --- Fallback: apply submitted player maneuver destinations if AI gave none ---
    if not position_updates:
        for side in blue_moves or []:
            if not isinstance(side, dict):
                continue
            for mv in side.get("moves", {}).get("maneuver", []) or []:
                unit = unit_map.get(mv.get("unit_id"))
                if unit and mv.get("to_lat") is not None and mv.get("to_lng") is not None and unit.get("strength") != "Destroyed":
                    _clamp_position(unit, mv["to_lat"], mv["to_lng"], turn_hours, bbox, violations)

    return state, violations
