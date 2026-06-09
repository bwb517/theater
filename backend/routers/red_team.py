import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from auth import get_current_user, get_optional_user, require_role
from limiter import limiter
from game_consts import haversine_km
import models
import ai_client
import rules_engine
from datetime import datetime

router = APIRouter(prefix="/api/sessions", tags=["red-team"])

class RedTeamRequest(BaseModel):
    faction_id: str
    player_moves: list = []
    injects: list = []
    verbosity: int = 2

class AdjudicateRequest(BaseModel):
    turn_number: int
    blue_moves: list = []
    red_moves: list = []
    verbosity: int = 2

class AIPersonalityUpdate(BaseModel):
    faction_id: str
    personality: str

def _require_session_access(user: models.User, session: models.GameSession):
    """Admin and game_master always allowed; player allowed if they created the session,
    if the session has no explicit user_id assignments (open/demo mode), or if their
    user_id appears in faction_assignments."""
    if user.role in ("admin", "game_master"):
        return
    # Session creator is always allowed
    if session.created_by and str(session.created_by) == str(user.id):
        return
    # faction_assignments is a JSON list of {"faction_id": ..., "user_id": ..., "type": ...}
    assignments = json.loads(session.faction_assignments or "[]")
    named = [a for a in assignments if isinstance(a, dict) and a.get("user_id")]
    # If no assignment carries a user_id the session is open to any authenticated user
    # (covers demo sessions and solo-play sessions created without explicit player assignment)
    if not named:
        return
    user_id_str = str(user.id)
    if not any(str(a["user_id"]) == user_id_str for a in named):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

@router.post("/{session_id}/red-team")
@limiter.limit("20/hour")
async def generate_red_team_moves(
    request: Request,
    session_id: str,
    req: RedTeamRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Generate AI adversary moves for a faction this turn."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    _require_session_access(user, session)

    scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()
    if not scenario_obj:
        raise HTTPException(404, "Scenario not found")

    scenario = {
        "title": scenario_obj.title,
        "scenario_type": scenario_obj.scenario_type,
        "timeframe": scenario_obj.timeframe,
        "geography": json.loads(scenario_obj.geography or "{}"),
        "situation": json.loads(scenario_obj.situation or "{}"),
    }

    factions = json.loads(scenario_obj.factions or "[]")
    faction = next((f for f in factions if f["faction_id"] == req.faction_id), None)
    if not faction:
        raise HTTPException(404, f"Faction {req.faction_id} not found in scenario")

    # Apply per-session personality override (stored on session, not scenario)
    personality_overrides = json.loads(session.ai_personality_overrides or "{}")
    if req.faction_id in personality_overrides:
        faction = dict(faction)
        faction["ai_personality"] = personality_overrides[req.faction_id]

    game_state = json.loads(session.current_game_state or "{}")
    turn_logs = [
        {
            "turn_number": t.turn_number,
            "adjudication": json.loads(t.adjudication or "{}"),
            "key_events": json.loads(t.adjudication or "{}").get("key_events", [])
        }
        for t in session.turn_logs
    ]

    try:
        result = await ai_client.generate_red_team_moves(
            scenario=scenario,
            faction=faction,
            game_state=game_state,
            player_moves=req.player_moves,
            turn_history=turn_logs,
            current_turn=session.current_turn,
            injects=req.injects,
            verbosity=req.verbosity,
            user_id=user.id if user else None,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(500, f"Red Team AI failed: {str(e)}")

    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == session.current_turn
    ).first()
    if not turn_log:
        turn_log = models.TurnLog(
            session_id=session_id,
            turn_number=session.current_turn,
            player_moves=json.dumps([]),
            ai_moves=json.dumps([])
        )
        db.add(turn_log)

    existing_ai = json.loads(turn_log.ai_moves or "[]")
    existing_ai = [m for m in existing_ai if m.get("faction_id") != req.faction_id]
    existing_ai.append({"faction_id": req.faction_id, "moves": result})
    turn_log.ai_moves = json.dumps(existing_ai)
    db.commit()

    return {"success": True, "faction_id": req.faction_id, "moves": result}

# Detection range (km) per unit type — how far a Blue unit can spot enemy units
_DETECTION_RANGES_KM = {
    "Infantry": 10, "Armor": 8, "Artillery": 15, "Aviation": 50,
    "Logistics": 5, "SF": 12, "EW": 20, "Cyber": 0, "Naval": 30,
    "Air Defense": 10, "Mechanized Infantry": 8,
}

def _apply_proximity_detection(unit_map: dict, factions: list):
    """Auto-detect Red units that are within Blue unit detection range."""
    faction_sides = {f["faction_id"]: f.get("side", "") for f in factions}
    blue_units = [
        u for u in unit_map.values()
        if faction_sides.get(u.get("faction_id", "")) == "Blue"
        and u.get("strength") != "Destroyed"
        and u.get("location", {}).get("lat") is not None
    ]
    for unit in unit_map.values():
        if faction_sides.get(unit.get("faction_id", "")) != "Red":
            continue
        if unit.get("strength") == "Destroyed":
            continue
        loc = unit.get("location", {})
        rlat, rlng = loc.get("lat"), loc.get("lng")
        if rlat is None or rlng is None:
            continue
        for blue in blue_units:
            det_range = _DETECTION_RANGES_KM.get(blue.get("type", ""), 8)
            if det_range == 0:
                continue
            bloc = blue.get("location", {})
            dist = haversine_km(float(bloc["lat"]), float(bloc["lng"]), float(rlat), float(rlng))
            if dist <= det_range:
                blue_fid = blue.get("faction_id")
                detected_by = unit.setdefault("detected_by", [])
                if blue_fid and blue_fid not in detected_by:
                    detected_by.append(blue_fid)

@router.post("/{session_id}/adjudicate")
@limiter.limit("20/hour")
async def adjudicate_turn(
    request: Request,
    session_id: str,
    req: AdjudicateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Run AI adjudication for the current turn."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    _require_session_access(user, session)

    # Always adjudicate the actual current turn — ignore client-supplied turn_number
    turn_number = session.current_turn

    # Guard: don't silently overwrite a completed adjudication
    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == turn_number
    ).first()
    if turn_log and turn_log.adjudication:
        raise HTTPException(409, "Turn has already been adjudicated. Advance to the next turn first.")

    scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()
    scenario = {
        "title": scenario_obj.title,
        "scenario_type": scenario_obj.scenario_type,
        "timeframe": scenario_obj.timeframe,
        "geography": json.loads(scenario_obj.geography or "{}"),
        "situation": json.loads(scenario_obj.situation or "{}"),
        "win_conditions": json.loads(scenario_obj.win_conditions or "{}"),
    }

    game_state = json.loads(session.current_game_state or "{}")

    # Use the moves stored in the turn log if the request body is empty (fallback)
    blue_moves = req.blue_moves or (json.loads(turn_log.player_moves or "[]") if turn_log else [])
    red_moves = req.red_moves or (json.loads(turn_log.ai_moves or "[]") if turn_log else [])

    try:
        result, audit_payload = await ai_client.adjudicate_turn(
            scenario=scenario,
            blue_moves=blue_moves,
            red_moves=red_moves,
            current_game_state=game_state,
            turn_number=turn_number,
            verbosity=req.verbosity,
            user_id=user.id if user else None,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(500, f"Adjudication failed: {str(e)}")

    # Apply the AI's proposed outcomes under deterministic rule constraints.
    # The rules engine is the single authority that mutates game state; it clamps
    # or drops physically illegal mutations and returns the violations it found.
    game_state, violations = rules_engine.apply_adjudication(
        game_state,
        result,
        blue_moves=blue_moves,
        red_moves=red_moves,
        turn_hours=session.time_per_turn_hours,
        geography=scenario.get("geography"),
    )
    if violations:
        result["rule_violations"] = violations

    # Ensure a TurnLog row exists — creates one if moves were submitted without going through
    # the normal red-team flow (e.g., direct adjudication via GM inject).
    if not turn_log:
        turn_log = models.TurnLog(
            session_id=session_id,
            turn_number=turn_number,
            player_moves=json.dumps(blue_moves),
            ai_moves=json.dumps(red_moves),
        )
        db.add(turn_log)
        db.flush()  # populate turn_log.id so AdjudicationLog.turn_id is set correctly

    turn_log.adjudication = json.dumps(result)

    unit_map = {u["unit_id"]: u for u in game_state.get("unit_status", [])}

    # Apply detection updates (fog of war) — not a rule-constrained mutation
    for det in result.get("detection_updates", []):
        unit = unit_map.get(det.get("detected_unit_id"))
        fid = det.get("detected_by_faction_id")
        if unit and fid:
            detected_by = unit.setdefault("detected_by", [])
            if fid not in detected_by:
                detected_by.append(fid)

    # Proximity-based detection: auto-reveal Red units within Blue detection range
    scenario_factions = json.loads(scenario_obj.factions or "[]")
    _apply_proximity_detection(unit_map, scenario_factions)

    # Accumulate logistics impacts in game state for display
    existing_logistics = game_state.get("logistics_impacts", [])
    for impact in result.get("logistics_impacts", []):
        existing_logistics.append({"turn": turn_number, **impact})
    game_state["logistics_impacts"] = existing_logistics[-20:]  # keep last 20

    session.previous_game_state = session.current_game_state
    session.current_game_state = json.dumps(game_state)

    # Write audit log in the same commit as turn_log.adjudication for atomicity.
    # turn_log is guaranteed non-None here (created above if missing).
    audit_log = models.AdjudicationLog(
        turn_id=turn_log.id,
        session_id=session_id,
        user_id=user.id if user else None,
        turn_outcome=json.dumps(result),
        **audit_payload,
    )
    db.add(audit_log)

    db.commit()

    return {"success": True, "adjudication": result}

@router.put("/{session_id}/personality")
def update_personality(
    session_id: str,
    req: AIPersonalityUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Update AI faction personality for this session only (does not affect the shared scenario)."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    overrides = json.loads(session.ai_personality_overrides or "{}")
    overrides[req.faction_id] = req.personality
    session.ai_personality_overrides = json.dumps(overrides)
    db.commit()
    return {"success": True, "faction_id": req.faction_id, "personality": req.personality}
