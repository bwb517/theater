from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, get_settings
from auth import get_current_user, require_role
import models

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {
        "total_scenarios": db.query(models.Scenario).count(),
        "template_scenarios": db.query(models.Scenario).filter(models.Scenario.is_template == True).count(),
        "total_sessions": db.query(models.GameSession).count(),
        "active_sessions": db.query(models.GameSession).filter(models.GameSession.status == "Active").count(),
        "completed_sessions": db.query(models.GameSession).filter(models.GameSession.status == "Complete").count(),
        "total_users": db.query(models.User).count(),
        "total_aars": db.query(models.AARReport).count(),
        "total_monte_carlos": db.query(models.MonteCarloResult).count(),
    }

@router.get("/users")
def list_users(db: Session = Depends(get_db), user=Depends(get_current_user)):
    users = db.query(models.User).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat()
    } for u in users]

@router.get("/token-usage")
def get_token_usage(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    row = db.query(
        func.coalesce(func.sum(models.TokenUsage.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(models.TokenUsage.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(models.TokenUsage.cache_read_tokens), 0).label("cache_read_tokens"),
        func.coalesce(func.sum(models.TokenUsage.cache_write_tokens), 0).label("cache_write_tokens"),
    ).first()
    budget = get_settings().token_budget
    total = row.input_tokens + row.output_tokens
    return {
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "cache_write_tokens": row.cache_write_tokens,
        "total_tokens": total,
        "token_budget": budget,
        "tokens_remaining": max(0, budget - total),
    }

@router.get("/sessions")
def list_all_sessions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sessions = db.query(models.GameSession).order_by(models.GameSession.created_at.desc()).all()
    return [{
        "id": s.id,
        "title": s.title,
        "status": s.status,
        "current_turn": s.current_turn,
        "max_turns": s.max_turns,
        "created_at": s.created_at.isoformat()
    } for s in sessions]
