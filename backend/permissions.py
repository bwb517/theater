import json
from fastapi import HTTPException
import models


def has_session_access(user: models.User, session: models.GameSession) -> bool:
    """Return True if user may access session (read or write)."""
    if user.role in ("admin", "game_master"):
        return True
    if session.created_by and str(session.created_by) == str(user.id):
        return True
    assignments = json.loads(session.faction_assignments or "[]")
    named = [a for a in assignments if isinstance(a, dict) and a.get("user_id")]
    # No explicit user assignments → open/demo session, any authenticated user allowed
    if not named:
        return True
    return any(str(a["user_id"]) == str(user.id) for a in named)


def require_session_access(user: models.User, session: models.GameSession):
    """Raise HTTP 403 if user does not have access to session."""
    if not has_session_access(user, session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
