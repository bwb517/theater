import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from database import get_db
from auth import get_optional_user
from limiter import limiter
import models
import ai_client

router = APIRouter(prefix="/api/monte-carlo", tags=["monte-carlo"])

class MonteCarloRequest(BaseModel):
    scenario_id: Optional[str] = None
    session_id: Optional[str] = None
    num_runs: int = Field(default=10, ge=1, le=50)
    verbosity: int = 2

@router.post("/run")
@limiter.limit("5/hour")
async def run_monte_carlo(
    request: Request,
    req: MonteCarloRequest,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user)
):
    """Run Monte Carlo probability analysis on a scenario or active session."""
    scenario_obj = None
    session_state = None

    if req.session_id:
        session = db.query(models.GameSession).filter(models.GameSession.id == req.session_id).first()
        if not session:
            raise HTTPException(404, "Session not found")
        scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()
        session_state = {
            "current_turn": session.current_turn,
            "max_turns": session.max_turns,
            "game_state": json.loads(session.current_game_state or "{}"),
            "turns_played": len(session.turn_logs)
        }
    elif req.scenario_id:
        scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == req.scenario_id).first()

    if not scenario_obj:
        raise HTTPException(404, "Scenario not found")

    scenario = {
        "title": scenario_obj.title,
        "scenario_type": scenario_obj.scenario_type,
        "timeframe": scenario_obj.timeframe,
        "geography": json.loads(scenario_obj.geography or "{}"),
        "situation": json.loads(scenario_obj.situation or "{}"),
        "factions": json.loads(scenario_obj.factions or "[]"),
        "win_conditions": json.loads(scenario_obj.win_conditions or "{}"),
        "ai_notes": scenario_obj.ai_notes
    }

    try:
        results = await ai_client.run_monte_carlo(
            scenario=scenario,
            session_state=session_state,
            num_runs=req.num_runs,
            verbosity=req.verbosity
        )
    except Exception as e:
        raise HTTPException(500, f"Monte Carlo analysis failed: {str(e)}")

    mc_record = models.MonteCarloResult(
        session_id=req.session_id,
        scenario_id=scenario_obj.id,
        results=json.dumps(results)
    )
    db.add(mc_record)
    db.commit()
    db.refresh(mc_record)

    return {"id": mc_record.id, "results": results}

@router.get("/{mc_id}")
def get_results(mc_id: str, db: Session = Depends(get_db)):
    mc = db.query(models.MonteCarloResult).filter(models.MonteCarloResult.id == mc_id).first()
    if not mc:
        raise HTTPException(404, "Monte Carlo result not found")
    return {
        "id": mc.id,
        "session_id": mc.session_id,
        "scenario_id": mc.scenario_id,
        "results": json.loads(mc.results or "{}"),
        "created_at": mc.created_at.isoformat()
    }

@router.get("/session/{session_id}/latest")
def get_session_mc(session_id: str, db: Session = Depends(get_db)):
    mc = db.query(models.MonteCarloResult).filter(
        models.MonteCarloResult.session_id == session_id
    ).order_by(models.MonteCarloResult.created_at.desc()).first()
    if not mc:
        raise HTTPException(404, "No Monte Carlo results for this session")
    return {
        "id": mc.id,
        "results": json.loads(mc.results or "{}"),
        "created_at": mc.created_at.isoformat()
    }

@router.get("/scenario/{scenario_id}/latest")
def get_scenario_mc(scenario_id: str, db: Session = Depends(get_db)):
    mc = db.query(models.MonteCarloResult).filter(
        models.MonteCarloResult.scenario_id == scenario_id
    ).order_by(models.MonteCarloResult.created_at.desc()).first()
    if not mc:
        raise HTTPException(404, "No Monte Carlo results for this scenario")
    return {
        "id": mc.id,
        "results": json.loads(mc.results or "{}"),
        "created_at": mc.created_at.isoformat()
    }
