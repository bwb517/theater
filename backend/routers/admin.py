from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from database import get_db, get_settings
from auth import get_current_user, require_role, hash_password
import models

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Sum of all four token buckets for a TokenUsage row — used by the stats endpoints.
_TOTAL_TOKENS = (
    models.TokenUsage.input_tokens
    + models.TokenUsage.output_tokens
    + models.TokenUsage.cache_read_tokens
    + models.TokenUsage.cache_write_tokens
)

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

@router.get("/token-stats")
def get_token_stats(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """Aggregate token spend for dashboards (Recharts-ready arrays).

    Returns:
      - daily:          [{date, cost_usd, total_tokens}]  -> line chart
      - per_function:   [{function, cost_usd, total_tokens, calls}]  -> bar chart
      - per_scenario_type: [{scenario_type, cost_usd, total_tokens, calls}]  -> bar chart
      - totals:         overall sums + token budget
    """
    # Daily spend (group by calendar day of created_at; works on SQLite + Postgres)
    day = func.date(models.TokenUsage.created_at)
    daily_rows = (
        db.query(
            day.label("date"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(_TOTAL_TOKENS), 0).label("tokens"),
        )
        .group_by(day)
        .order_by(day)
        .all()
    )
    daily = [
        {"date": str(r.date), "cost_usd": round(r.cost or 0.0, 6), "total_tokens": int(r.tokens or 0)}
        for r in daily_rows
    ]

    # Cost per ai_client function
    fn_rows = (
        db.query(
            models.TokenUsage.function_name.label("function"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(_TOTAL_TOKENS), 0).label("tokens"),
            func.count(models.TokenUsage.id).label("calls"),
        )
        .group_by(models.TokenUsage.function_name)
        .order_by(func.sum(models.TokenUsage.total_cost_usd).desc())
        .all()
    )
    per_function = [
        {
            "function": r.function or "unknown",
            "cost_usd": round(r.cost or 0.0, 6),
            "total_tokens": int(r.tokens or 0),
            "calls": int(r.calls or 0),
        }
        for r in fn_rows
    ]

    # Cost per scenario type — join TokenUsage -> GameSession -> Scenario.
    # Rows with no session (e.g. scenario generation) bucket as "Unattributed".
    st_rows = (
        db.query(
            models.Scenario.scenario_type.label("scenario_type"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(_TOTAL_TOKENS), 0).label("tokens"),
            func.count(models.TokenUsage.id).label("calls"),
        )
        .select_from(models.TokenUsage)
        .outerjoin(models.GameSession, models.TokenUsage.session_id == models.GameSession.id)
        .outerjoin(models.Scenario, models.GameSession.scenario_id == models.Scenario.id)
        .group_by(models.Scenario.scenario_type)
        .all()
    )
    per_scenario_type = [
        {
            "scenario_type": r.scenario_type or "Unattributed",
            "cost_usd": round(r.cost or 0.0, 6),
            "total_tokens": int(r.tokens or 0),
            "calls": int(r.calls or 0),
        }
        for r in st_rows
    ]

    totals_row = db.query(
        func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
        func.coalesce(func.sum(models.TokenUsage.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(models.TokenUsage.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(models.TokenUsage.cache_read_tokens), 0).label("cache_read_tokens"),
        func.coalesce(func.sum(models.TokenUsage.cache_write_tokens), 0).label("cache_write_tokens"),
        func.count(models.TokenUsage.id).label("calls"),
    ).first()
    total_tokens = (
        totals_row.input_tokens + totals_row.output_tokens
        + totals_row.cache_read_tokens + totals_row.cache_write_tokens
    )

    return {
        "daily": daily,
        "per_function": per_function,
        "per_scenario_type": per_scenario_type,
        "totals": {
            "cost_usd": round(totals_row.cost or 0.0, 6),
            "input_tokens": int(totals_row.input_tokens),
            "output_tokens": int(totals_row.output_tokens),
            "cache_read_tokens": int(totals_row.cache_read_tokens),
            "cache_write_tokens": int(totals_row.cache_write_tokens),
            "total_tokens": int(total_tokens),
            "calls": int(totals_row.calls or 0),
            "token_budget": get_settings().token_budget,
        },
    }


@router.get("/token-stats/by-user")
def get_token_stats_by_user(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """Per-user token spend, with lifetime + current-month breakdown (Recharts-ready).

    Note: THEATER has no first-class billing tier/allowance concept — `tier` is
    derived from the user's role, and `monthly_token_budget` is the shared
    informational TOKEN_BUDGET setting, surfaced so the UI can show a usage bar.
    """
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # Lifetime totals per user
    rows = (
        db.query(
            models.User.id.label("user_id"),
            models.User.username.label("username"),
            models.User.role.label("role"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(_TOTAL_TOKENS), 0).label("tokens"),
            func.count(models.TokenUsage.id).label("calls"),
        )
        .select_from(models.TokenUsage)
        .join(models.User, models.TokenUsage.user_id == models.User.id)
        .group_by(models.User.id, models.User.username, models.User.role)
        .order_by(func.sum(models.TokenUsage.total_cost_usd).desc())
        .all()
    )

    # Current-month totals per user (separate query, joined in Python)
    month_rows = (
        db.query(
            models.TokenUsage.user_id.label("user_id"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
            func.coalesce(func.sum(_TOTAL_TOKENS), 0).label("tokens"),
        )
        .filter(models.TokenUsage.created_at >= month_start)
        .filter(models.TokenUsage.user_id.isnot(None))
        .group_by(models.TokenUsage.user_id)
        .all()
    )
    month_by_user = {
        m.user_id: {"cost": round(m.cost or 0.0, 6), "tokens": int(m.tokens or 0)}
        for m in month_rows
    }

    _role_to_tier = {"admin": "Unlimited", "gamemaster": "Standard", "player": "Basic"}
    budget = get_settings().token_budget

    users = []
    for r in rows:
        month = month_by_user.get(r.user_id, {"cost": 0.0, "tokens": 0})
        users.append({
            "user_id": r.user_id,
            "username": r.username,
            "role": r.role,
            "tier": _role_to_tier.get(r.role, "Basic"),
            "cost_usd": round(r.cost or 0.0, 6),
            "total_tokens": int(r.tokens or 0),
            "calls": int(r.calls or 0),
            "month_cost_usd": month["cost"],
            "month_tokens": month["tokens"],
        })

    return {
        "users": users,
        "month_start": month_start.isoformat(),
        "monthly_token_budget": budget,
    }


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str,
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": f"Password reset for {user.username}"}

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
