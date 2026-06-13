import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_db
from auth import get_current_user, require_role
from permissions import require_session_access, has_session_access
from game_consts import MOVEMENT_RATES, haversine_km
import rules_engine
import forecasting
import models

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

MUNITIONS_DEFAULTS = {
    "Air Defense": {"count": 8, "max": 8, "type": "interceptors"},
    "Aviation":    {"count": 16, "max": 16, "type": "Hellfire missiles"},
}

MUNITIONS_BY_CAPABILITY = {
    "himars": {"count": 6, "max": 6, "type": "GMLRS rockets"},
    "mlrs":   {"count": 12, "max": 12, "type": "MLRS rockets"},
    "guided mlrs": {"count": 6, "max": 6, "type": "GMLRS rockets"},
}

def _seed_munitions(unit: dict):
    unit_type = unit.get("type", "")
    if unit_type in MUNITIONS_DEFAULTS:
        return dict(MUNITIONS_DEFAULTS[unit_type])
    caps_lower = [c.lower() for c in unit.get("capabilities", [])]
    for cap_key, munitions in MUNITIONS_BY_CAPABILITY.items():
        if any(cap_key in c for c in caps_lower):
            return dict(munitions)
    return None

def _wtf_from_posture(faction: dict) -> str:
    posture_map = {
        "Offensive": "High",
        "Defensive": "Moderate",
        "Economy of Force": "Low",
        "Shaping": "Low",
        "Ambiguous": "Moderate",
    }
    posture = faction.get("starting_posture", "")
    if posture in posture_map:
        return posture_map[posture]
    return "High" if faction.get("side") == "Red" else "Moderate"

def _parse_duration_hours(timeframe: str) -> Optional[int]:
    """Extract total hours from timeframe strings like '7 days', '72 hours, March 2026', '6 months'."""
    if not timeframe:
        return None
    tf = timeframe.lower()
    m = re.search(r'(\d+\.?\d*)\s*month', tf)
    if m:
        return int(float(m.group(1)) * 30 * 24)
    m = re.search(r'(\d+\.?\d*)\s*week', tf)
    if m:
        return int(float(m.group(1)) * 7 * 24)
    m = re.search(r'(\d+\.?\d*)\s*day', tf)
    if m:
        return int(float(m.group(1)) * 24)
    m = re.search(r'(\d+\.?\d*)\s*hour', tf)
    if m:
        return int(float(m.group(1)))
    return None

class SessionCreate(BaseModel):
    scenario_id: str
    title: str
    faction_assignments: list = []
    max_turns: int = 8
    time_per_turn_hours: int = 0  # 0 = auto-derive from scenario timeframe
    forecasting_enabled: bool = False  # opt-in probabilistic forecasting overlay

class MoveSubmit(BaseModel):
    faction_id: str
    moves: dict

class GMNote(BaseModel):
    notes: str

class ForecastSubmit(BaseModel):
    p_blue_wins: float
    p_red_wins: float
    p_escalation: float
    p_key_objective_captured: float
    rationale: Optional[str] = None

def serialize_turn(t: models.TurnLog) -> dict:
    return {
        "id": t.id,
        "session_id": t.session_id,
        "turn_number": t.turn_number,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        "player_moves": json.loads(t.player_moves or "[]"),
        "ai_moves": json.loads(t.ai_moves or "[]"),
        "adjudication": json.loads(t.adjudication or "{}"),
        "injects_triggered": json.loads(t.injects_triggered or "[]"),
        "game_master_notes": t.game_master_notes,
    }

def serialize_session(s: models.GameSession) -> dict:
    return {
        "id": s.id,
        "scenario_id": s.scenario_id,
        "title": s.title,
        "status": s.status,
        "current_turn": s.current_turn,
        "max_turns": s.max_turns,
        "time_per_turn_hours": s.time_per_turn_hours,
        "faction_assignments": json.loads(s.faction_assignments or "[]"),
        "current_game_state": json.loads(s.current_game_state or "{}"),
        "previous_game_state": json.loads(s.previous_game_state or "{}"),
        "forecasting_enabled": bool(s.forecasting_enabled),
        "total_brier_score": s.total_brier_score,
        "created_by": s.created_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "turn_logs": [serialize_turn(t) for t in s.turn_logs] if s.turn_logs else [],
    }

@router.post("")
def create_session(
    req: SessionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    scenario = db.query(models.Scenario).filter(models.Scenario.id == req.scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    factions = json.loads(scenario.factions or "[]")
    win_cond = json.loads(scenario.win_conditions or "{}")

    # Auto-derive max_turns from scenario win_conditions if not overridden
    max_turns = req.max_turns if req.max_turns != 8 else win_cond.get("duration_turns", req.max_turns)

    # Auto-calculate time_per_turn_hours from scenario timeframe when not explicitly set
    time_per_turn_hours = req.time_per_turn_hours
    if time_per_turn_hours == 0:
        duration_hours = _parse_duration_hours(scenario.timeframe or "")
        if duration_hours and max_turns > 0:
            time_per_turn_hours = max(1, round(duration_hours / max_turns))
        else:
            time_per_turn_hours = 24  # sensible default: 1 day per turn

    initial_state = {
        "faction_scores": [
            {"faction_id": f["faction_id"], "name": f["name"], "side": f["side"],
             "score": 0, "objective_status": "In Progress"}
            for f in factions
        ],
        "unit_status": [
            {
                "unit_id": u["unit_id"],
                "name": u["name"],
                "faction_id": f["faction_id"],
                "type": u.get("type", "Infantry"),
                "strength": u.get("strength", "Full"),
                "location": u.get("location", {}),
                "status": "Active",
                "supply": {
                    "ammo": 100,
                    "fuel": 100,
                    "maintenance": 100,
                    "munitions": _seed_munitions(u),
                },
                "will_to_fight": _wtf_from_posture(f),
                "c2_status": "Nominal",
                "detected_by": [f["faction_id"]],
                "manning": 100,
            }
            for f in factions
            for u in f.get("order_of_battle", {}).get("units", [])
        ],
        "controlled_terrain": [],
        "turn_start_time": "H+00:00"
    }

    session = models.GameSession(
        scenario_id=req.scenario_id,
        title=req.title,
        status="Active",
        current_turn=1,
        max_turns=max_turns,
        time_per_turn_hours=time_per_turn_hours,
        faction_assignments=json.dumps(req.faction_assignments),
        current_game_state=json.dumps(initial_state),
        forecasting_enabled=req.forecasting_enabled,
        created_by=user.id if user else None
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return serialize_session(session)

@router.get("")
def list_sessions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sessions = db.query(models.GameSession).order_by(models.GameSession.created_at.desc()).all()
    if user.role not in ("admin", "game_master"):
        sessions = [s for s in sessions if has_session_access(user, s)]
    return [serialize_session(s) for s in sessions]

@router.get("/{session_id}")
def get_session(session_id: str, faction_id: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Session not found")
    require_session_access(user, s)
    data = serialize_session(s)
    if faction_id:
        state = data.get("current_game_state", {})
        state["unit_status"] = [
            u for u in state.get("unit_status", [])
            if u.get("faction_id") == faction_id
            or faction_id in u.get("detected_by", [])
        ]
        data["current_game_state"] = state
    return data

@router.post("/{session_id}/moves")
def submit_moves(
    session_id: str,
    req: MoveSubmit,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Submit player moves for the current turn."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    if session.status != "Active":
        raise HTTPException(400, "Session is not active")

    # Verify the submitted faction is Player-controlled (not AI) in this session
    faction_assignments = json.loads(session.faction_assignments or "[]")
    fa_map = {fa["faction_id"]: fa.get("role", "Player") for fa in faction_assignments if isinstance(fa, dict)}
    if fa_map and fa_map.get(req.faction_id) == "AI":
        raise HTTPException(403, f"Faction {req.faction_id} is AI-controlled; players cannot submit moves for it")

    # Validate maneuver and fires orders against supply/movement constraints
    game_state = json.loads(session.current_game_state or "{}")
    unit_map = {u["unit_id"]: u for u in game_state.get("unit_status", [])}
    state_mutated = False

    for order in req.moves.get("maneuver", []):
        uid = order.get("unit_id")
        unit = unit_map.get(uid)
        if not unit:
            continue
        supply = unit.get("supply", {})
        if supply.get("fuel", 100) < 20:
            raise HTTPException(400, f"Unit '{unit.get('name', uid)}' has insufficient fuel to maneuver (fuel: {supply.get('fuel', 0)}/100).")
        to_lat = order.get("to_lat")
        to_lng = order.get("to_lng")
        if to_lat is not None and to_lng is not None:
            try:
                to_lat = float(to_lat)
                to_lng = float(to_lng)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Invalid coordinates for unit '{unit.get('name', uid)}'")
            if not (-90 <= to_lat <= 90) or not (-180 <= to_lng <= 180):
                raise HTTPException(400, f"Destination coordinates for unit '{unit.get('name', uid)}' are out of range")
            loc = unit.get("location", {})
            from_lat = loc.get("lat")
            from_lng = loc.get("lng")
            if from_lat is not None and from_lng is not None:
                dist_km = haversine_km(float(from_lat), float(from_lng), to_lat, to_lng)
                rate = MOVEMENT_RATES.get(unit.get("type", ""), 20)
                max_km = rate * session.time_per_turn_hours
                if max_km == 0:
                    raise HTTPException(400, f"Unit '{unit.get('name', uid)}' ({unit.get('type')}) cannot move.")
                if dist_km > max_km:
                    raise HTTPException(
                        400,
                        f"Unit '{unit.get('name', uid)}' cannot reach destination: {dist_km:.1f} km exceeds maximum range of {max_km:.0f} km ({rate} km/h × {session.time_per_turn_hours}h)."
                    )

    for order in req.moves.get("fires", []):
        uid = order.get("unit_id")
        if not uid:
            continue
        unit = unit_map.get(uid)
        if not unit:
            continue
        supply = unit.get("supply", {})
        munitions = supply.get("munitions")
        if munitions is not None:
            if munitions.get("count", 0) <= 0:
                raise HTTPException(400, f"Unit '{unit.get('name', uid)}' has expended all {munitions.get('type', 'munitions')} (0 remaining).")
            munitions["count"] = max(0, munitions["count"] - 1)
            state_mutated = True
        else:
            if supply.get("ammo", 100) < 20:
                raise HTTPException(400, f"Unit '{unit.get('name', uid)}' has insufficient ammo to fire (ammo: {supply.get('ammo', 0)}/100).")

    if state_mutated:
        problems = rules_engine.validate_game_state(game_state)
        if problems:
            raise HTTPException(422, {"message": "Move submission produced invalid game state", "problems": problems})
        session.current_game_state = json.dumps(game_state)

    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == session.current_turn
    ).first()

    if not turn_log:
        turn_log = models.TurnLog(
            session_id=session_id,
            turn_number=session.current_turn,
            player_moves=json.dumps([])
        )
        db.add(turn_log)

    existing = json.loads(turn_log.player_moves or "[]")
    existing = [m for m in existing if m.get("faction_id") != req.faction_id]
    existing.append({"faction_id": req.faction_id, "moves": req.moves, "submitted_at": datetime.utcnow().isoformat()})
    turn_log.player_moves = json.dumps(existing)
    db.commit()
    return {"success": True, "message": f"Moves submitted for {req.faction_id}, Turn {session.current_turn}"}

@router.post("/{session_id}/turns/{turn_number}/gm-notes")
def save_gm_notes(
    session_id: str,
    turn_number: int,
    req: GMNote,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == turn_number
    ).first()
    if not turn_log:
        raise HTTPException(404, "Turn not found")
    turn_log.game_master_notes = req.notes
    db.commit()
    return {"success": True}

def _check_ally_arrivals(session: models.GameSession, scenario_data: dict, next_turn: int) -> list:
    """Return inject entries for any allied forces scheduled to arrive on next_turn."""
    injects = []
    assumptions = scenario_data.get("situation", {}).get("planning_assumptions", {})
    allied = assumptions.get("allied_involvement", {})
    if not allied.get("enabled"):
        return injects
    for ally in allied.get("allies", []):
        if ally.get("arrival_turn") == next_turn:
            injects.append({
                "inject_id": f"ALLY-ARRIVAL-{ally.get('nation', 'UNKNOWN')}-T{next_turn}",
                "type": "Event",
                "description": (
                    f"Allied forces arrive: {ally.get('nation')} "
                    f"({ally.get('commitment_level', 'Unknown')} commitment). "
                    f"{ally.get('arrival_description', '')} "
                    f"Forces: {ally.get('forces_description', 'unspecified')}."
                ),
                "affected_factions": ["all"],
                "turn_trigger": next_turn,
            })
    return injects


@router.post("/{session_id}/advance-turn")
def advance_turn(session_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Advance to the next turn. Requires adjudication to have run first."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    if session.status == "Complete":
        raise HTTPException(400, "Session is already complete")

    # Guard: if a turn log exists for the current turn, it must have been adjudicated
    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == session.current_turn
    ).first()
    if turn_log and not turn_log.adjudication:
        raise HTTPException(400, "Cannot advance: adjudicate this turn first before advancing")

    if session.current_turn >= session.max_turns:
        session.status = "Complete"
        db.commit()
        db.refresh(session)
        return serialize_session(session)

    next_turn = session.current_turn + 1
    session.current_turn = next_turn

    # Auto game-over: if 60%+ of Blue units are Destroyed or Critical, end the session
    scenario = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()
    if scenario:
        factions_data = json.loads(scenario.factions or "[]")
        blue_ids = {f["faction_id"] for f in factions_data if f.get("side") == "Blue"}
        game_state = json.loads(session.current_game_state or "{}")
        blue_units = [u for u in game_state.get("unit_status", []) if u.get("faction_id") in blue_ids]
        if blue_units:
            degraded = sum(1 for u in blue_units if u.get("strength") in ("Destroyed", "Critical"))
            if degraded / len(blue_units) >= 0.6:
                session.status = "Complete"

    # Check for allied arrivals and create an inject in the new turn's log
    if scenario:
        scenario_data = {
            "situation": json.loads(scenario.situation or "{}"),
        }
        ally_injects = _check_ally_arrivals(session, scenario_data, next_turn)
        if ally_injects:
            new_turn_log = models.TurnLog(
                session_id=session_id,
                turn_number=next_turn,
                injects_triggered=json.dumps(ally_injects),
                player_moves=json.dumps([]),
            )
            db.add(new_turn_log)

    db.commit()
    db.refresh(session)
    return serialize_session(session)

@router.put("/{session_id}/status")
def update_status(
    session_id: str,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    if status not in ("Setup", "Active", "Paused", "Complete"):
        raise HTTPException(400, "Invalid status")
    session.status = status
    db.commit()
    return {"success": True, "status": status}

@router.put("/{session_id}/game-state")
def update_game_state(
    session_id: str,
    state: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    problems = rules_engine.validate_game_state(state)
    if problems:
        raise HTTPException(422, {"message": "Invalid game state", "problems": problems})
    session.current_game_state = json.dumps(state)
    db.commit()
    return {"success": True}

class CapitulateRequest(BaseModel):
    faction_id: str

@router.post("/{session_id}/capitulate")
def capitulate(
    session_id: str,
    req: CapitulateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Declare defeat for a faction, ending the session."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    if session.status != "Active":
        raise HTTPException(400, "Session is not active")
    session.status = "Complete"

    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == session.current_turn
    ).first()
    if not turn_log:
        turn_log = models.TurnLog(
            session_id=session_id,
            turn_number=session.current_turn,
            player_moves=json.dumps([])
        )
        db.add(turn_log)
    note = f"[CAPITULATION] {req.faction_id} has surrendered."
    turn_log.game_master_notes = ((turn_log.game_master_notes or "") + "\n" + note).strip()

    db.commit()
    db.refresh(session)
    return serialize_session(session)

@router.get("/{session_id}/turns/{turn_number}/audit")
def get_turn_audit(
    session_id: str,
    turn_number: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return the verbatim AI audit trail for a specific turn."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == turn_number,
    ).first()
    if not turn_log:
        raise HTTPException(404, "Turn not found")
    audit = db.query(models.AdjudicationLog).filter(
        models.AdjudicationLog.turn_id == turn_log.id,
    ).first()
    if not audit:
        raise HTTPException(404, "No audit log for this turn")
    return {
        "turn_number": turn_number,
        "function_name": audit.function_name,
        "timestamp": audit.timestamp.isoformat() if audit.timestamp else None,
        "inputs": json.loads(audit.ai_inputs or "{}"),
        "system_prompt": audit.ai_system_prompt,
        "user_message": audit.ai_user_message,
        "reasoning": audit.ai_reasoning,
        "full_response": json.loads(audit.ai_response_full or "[]"),
        "outcome": json.loads(audit.turn_outcome or "{}"),
    }

@router.post("/{session_id}/turns/{turn_num}/forecast")
def submit_forecast(
    session_id: str,
    turn_num: int,
    req: ForecastSubmit,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit a pre-turn probability forecast for the current, un-adjudicated turn.

    Optional overlay — only allowed when the session has forecasting enabled, for the
    current turn, before it has been adjudicated. One forecast per (session, turn, user):
    re-submitting overwrites the prior estimate.
    """
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    if not session.forecasting_enabled:
        raise HTTPException(400, "Forecasting is not enabled for this session")
    if turn_num != session.current_turn:
        raise HTTPException(400, "You can only forecast the current turn")

    turn_log = db.query(models.TurnLog).filter(
        models.TurnLog.session_id == session_id,
        models.TurnLog.turn_number == turn_num,
    ).first()
    if turn_log and turn_log.adjudication:
        raise HTTPException(409, "Turn has already been adjudicated — forecast must precede adjudication")

    fc = db.query(models.TurnForecast).filter(
        models.TurnForecast.session_id == session_id,
        models.TurnForecast.turn_number == turn_num,
        models.TurnForecast.user_id == (user.id if user else None),
    ).first()
    if not fc:
        fc = models.TurnForecast(
            session_id=session_id,
            turn_number=turn_num,
            user_id=user.id if user else None,
        )
        db.add(fc)

    fc.p_blue_wins = req.p_blue_wins
    fc.p_red_wins = req.p_red_wins
    fc.p_escalation = req.p_escalation
    fc.p_key_objective_captured = req.p_key_objective_captured
    fc.rationale = req.rationale
    fc.submitted_at = datetime.utcnow()
    if turn_log:
        fc.turn_id = turn_log.id
    # Re-submission before adjudication resets any (shouldn't exist) resolution.
    fc.resolved_at = None
    fc.brier_score = None

    db.commit()
    db.refresh(fc)
    return {"forecast_id": fc.id, "submitted_at": fc.submitted_at.isoformat()}

@router.get("/{session_id}/forecasting-summary")
def forecasting_summary(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Forecast accuracy summary: per-turn estimates vs outcomes, Brier avg, calibration."""
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(user, session)
    rows = db.query(models.TurnForecast).filter(
        models.TurnForecast.session_id == session_id,
    ).all()
    return forecasting.build_forecasting_summary(rows, total_turns=session.current_turn)

@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    require_session_access(current_user, session)
    if session.created_by != current_user.id and current_user.role not in ("admin", "gamemaster"):
        raise HTTPException(403, "Not authorized to delete this session")
    db.query(models.TurnForecast).filter(models.TurnForecast.session_id == session_id).delete()
    db.query(models.TurnLog).filter(models.TurnLog.session_id == session_id).delete()
    db.query(models.AARReport).filter(models.AARReport.session_id == session_id).delete()
    db.query(models.MonteCarloResult).filter(models.MonteCarloResult.session_id == session_id).delete()
    db.delete(session)
    db.commit()
