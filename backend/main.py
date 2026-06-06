import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import engine, settings, get_db
from limiter import limiter
import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("theater")

# Create all tables
models.Base.metadata.create_all(bind=engine)

# Add columns introduced after initial schema (SQLite doesn't support ALTER TABLE in create_all)
def _run_migrations():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(game_sessions)"))
        existing = {row[1] for row in result}
        if "ai_personality_overrides" not in existing:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN ai_personality_overrides TEXT"))
            conn.commit()
        if "previous_game_state" not in existing:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN previous_game_state TEXT"))
            conn.commit()

_run_migrations()

_INSECURE_KEYS = {
    "theater-dev-secret-change-in-production",
    "your-super-secret-jwt-key-change-this-in-production",
    "",
}
if settings.secret_key in _INSECURE_KEYS:
    log.critical("SECRET_KEY is using an insecure default — set SECRET_KEY in .env before deploying to production")

app = FastAPI(
    title="THEATER Wargaming Platform API",
    version="1.0.0",
    description="AI-powered military scenario simulation and wargaming platform"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
from routers import auth, scenarios, sessions, red_team, monte_carlo, aar, admin

app.include_router(auth.router)
app.include_router(scenarios.router)
app.include_router(sessions.router)
app.include_router(red_team.router)
app.include_router(monte_carlo.router)
app.include_router(aar.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {"status": "THEATER API operational", "version": "1.0.0"}

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok", "model": settings.claude_model}
