import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from database import get_db
from auth import get_current_user
from limiter import limiter
import models
import ai_client

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=2000)
    verbosity: int = 2

class UnitTemplateCreate(BaseModel):
    name: str
    type: str
    echelon: str
    nation_group: str
    capabilities: list = []
    limitations: list = []
    typical_strength: int = 0

# ─────────────────────────────────────────────────────────────────────────────

class ScenarioCreate(BaseModel):
    title: str
    scenario_type: str = "Tactical"
    timeframe: str = ""
    geography: dict = {}
    situation: dict = {}
    factions: list = []
    injects: list = []
    win_conditions: dict = {}
    ai_notes: str = ""
    is_template: bool = False

def serialize_scenario(s: models.Scenario) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "classification": s.classification,
        "scenario_type": s.scenario_type,
        "timeframe": s.timeframe,
        "geography": json.loads(s.geography or "{}"),
        "situation": json.loads(s.situation or "{}"),
        "factions": json.loads(s.factions or "[]"),
        "injects": json.loads(s.injects or "[]"),
        "win_conditions": json.loads(s.win_conditions or "{}"),
        "ai_notes": s.ai_notes,
        "is_template": s.is_template,
        "template_name": s.template_name,
        "created_by": s.created_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }

@router.post("/generate")
@limiter.limit("10/hour")
async def generate_scenario(request: Request, req: GenerateRequest, user=Depends(get_current_user)):
    """Generate a scenario from natural language using Claude."""
    try:
        scenario_data = await ai_client.generate_scenario(
            req.prompt,
            verbosity=req.verbosity,
            user_id=user.id if user else None,
        )
        return {"success": True, "scenario": scenario_data}
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {str(e)}")

@router.get("")
def list_scenarios(
    is_template: Optional[bool] = None,
    scenario_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(models.Scenario)
    if is_template is not None:
        q = q.filter(models.Scenario.is_template == is_template)
    if scenario_type:
        q = q.filter(models.Scenario.scenario_type == scenario_type)
    scenarios = q.order_by(models.Scenario.created_at.desc()).all()
    return [serialize_scenario(s) for s in scenarios]

@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    return serialize_scenario(s)

@router.post("")
def create_scenario(
    req: ScenarioCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    s = models.Scenario(
        title=req.title,
        scenario_type=req.scenario_type,
        timeframe=req.timeframe,
        geography=json.dumps(req.geography),
        situation=json.dumps(req.situation),
        factions=json.dumps(req.factions),
        injects=json.dumps(req.injects),
        win_conditions=json.dumps(req.win_conditions),
        ai_notes=req.ai_notes,
        is_template=req.is_template,
        created_by=user.id if user else None
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return serialize_scenario(s)

@router.put("/{scenario_id}")
def update_scenario(
    scenario_id: str,
    req: ScenarioCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    s = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    if s.created_by != user.id and user.role not in ("admin", "gamemaster"):
        raise HTTPException(403, "Not authorized to edit this scenario")
    s.title = req.title
    s.scenario_type = req.scenario_type
    s.timeframe = req.timeframe
    s.geography = json.dumps(req.geography)
    s.situation = json.dumps(req.situation)
    s.factions = json.dumps(req.factions)
    s.injects = json.dumps(req.injects)
    s.win_conditions = json.dumps(req.win_conditions)
    s.ai_notes = req.ai_notes
    s.is_template = req.is_template
    db.commit()
    db.refresh(s)
    return serialize_scenario(s)

@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    db.delete(s)
    db.commit()
    return {"success": True}

@router.get("/units/library")
def get_unit_library(
    nation_group: Optional[str] = None,
    unit_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.UnitTemplate)
    if nation_group:
        q = q.filter(models.UnitTemplate.nation_group == nation_group)
    if unit_type:
        q = q.filter(models.UnitTemplate.type == unit_type)
    units = q.all()
    return [{
        "id": u.id,
        "name": u.name,
        "type": u.type,
        "echelon": u.echelon,
        "nation_group": u.nation_group,
        "capabilities": json.loads(u.capabilities or "[]"),
        "limitations": json.loads(u.limitations or "[]"),
        "typical_strength": u.typical_strength
    } for u in units]


@router.post("/units/library")
def add_unit_to_library(
    req: UnitTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Add a custom unit template to the reusable unit library."""
    unit = models.UnitTemplate(
        name=req.name,
        type=req.type,
        echelon=req.echelon,
        nation_group=req.nation_group,
        capabilities=json.dumps(req.capabilities),
        limitations=json.dumps(req.limitations),
        typical_strength=req.typical_strength,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return {
        "id": unit.id,
        "name": unit.name,
        "type": unit.type,
        "echelon": unit.echelon,
        "nation_group": unit.nation_group,
        "capabilities": json.loads(unit.capabilities or "[]"),
        "limitations": json.loads(unit.limitations or "[]"),
        "typical_strength": unit.typical_strength,
    }
