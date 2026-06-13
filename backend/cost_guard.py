from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, get_settings
from auth import get_current_user
import models

me_router = APIRouter(prefix="/api/me", tags=["me"])

# Column expression summing the three token buckets that count against the daily cap.
# Cache-read tokens are intentionally excluded — they cost ~10× less than input tokens
# and would unfairly penalise sessions that benefit from prompt caching.
_BILLABLE_TOKENS = (
    models.TokenUsage.input_tokens
    + models.TokenUsage.output_tokens
    + models.TokenUsage.cache_write_tokens
)

# All four buckets summed for informational display in /token-status.
_ALL_TOKENS = (
    models.TokenUsage.input_tokens
    + models.TokenUsage.output_tokens
    + models.TokenUsage.cache_read_tokens
    + models.TokenUsage.cache_write_tokens
)


def _today_utc() -> datetime:
    """Return naive UTC midnight for today (SQLite stores naive datetimes)."""
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


async def check_token_budget(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency: enforce per-user daily token cap before any LLM call.

    Admins are exempt. All other roles are blocked with HTTP 429 once their
    billable token count (input + output + cache-write) for the current UTC day
    reaches settings.user_daily_token_limit.
    """
    if user.role == "admin":
        return user

    settings = get_settings()
    used = (
        db.query(func.coalesce(func.sum(_BILLABLE_TOKENS), 0))
        .filter(
            models.TokenUsage.user_id == user.id,
            models.TokenUsage.created_at >= _today_utc(),
        )
        .scalar()
        or 0
    )

    if used >= settings.user_daily_token_limit:
        raise HTTPException(
            status_code=429,
            detail="Daily token limit reached. Try again after midnight UTC.",
        )
    return user


@me_router.get("/token-status")
async def get_token_status(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return this user's token usage for today and their daily cap."""
    today = _today_utc()
    next_midnight = today + timedelta(days=1)
    settings = get_settings()
    is_admin = user.role == "admin"

    row = (
        db.query(
            func.coalesce(func.sum(_ALL_TOKENS), 0).label("tokens"),
            func.coalesce(func.sum(models.TokenUsage.total_cost_usd), 0.0).label("cost"),
        )
        .filter(
            models.TokenUsage.user_id == user.id,
            models.TokenUsage.created_at >= today,
        )
        .first()
    )

    return {
        "tokens_used_today": int(row.tokens or 0),
        "cost_used_today_usd": round(float(row.cost or 0.0), 6),
        "daily_limit_tokens": None if is_admin else settings.user_daily_token_limit,
        "limit_resets_at": next_midnight.isoformat() + "Z",
        "is_admin": is_admin,
    }
