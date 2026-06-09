import logging
import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import engine, settings, get_db, _is_sqlite
from limiter import limiter
import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("theater")

# Create all tables
models.Base.metadata.create_all(bind=engine)

# Add columns introduced after initial schema.
# Each entry maps a table to {column_name: sql_type}. REAL/DOUBLE picks the
# right floating-point type per backend; everything else is TEXT.
_MIGRATIONS = {
    "game_sessions": {
        "ai_personality_overrides": "TEXT",
        "previous_game_state": "TEXT",
    },
    "token_usage": {
        "user_id": "TEXT",
        "session_id": "TEXT",
        "total_cost_usd": "REAL" if _is_sqlite else "DOUBLE PRECISION",
        "claude_model": "TEXT",
    },
    "scenarios": {
        "is_published": "BOOLEAN DEFAULT FALSE",
        "published_by_user_id": "TEXT",
        "published_at": "TEXT",
        "usage_count": "INTEGER DEFAULT 0",
        "is_official": "BOOLEAN DEFAULT FALSE",
    },
}

def _run_migrations():
    with engine.connect() as conn:
        for table, cols in _MIGRATIONS.items():
            if _is_sqlite:
                # SQLite: use PRAGMA to list existing columns
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                existing = {row[1] for row in result}
                for col, col_type in cols.items():
                    if col not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                        conn.commit()
            else:
                # PostgreSQL: use information_schema to check column existence
                for col, col_type in cols.items():
                    result = conn.execute(text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = :table AND column_name = :col"
                    ), {"table": table, "col": col})
                    if not result.fetchone():
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
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

# Redirect HTTP → HTTPS in production (Railway sets x-forwarded-proto)
@app.middleware("http")
async def https_redirect(request: Request, call_next):
    if request.headers.get("x-forwarded-proto") == "http":
        url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url, status_code=301)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
from routers import auth, scenarios, sessions, red_team, monte_carlo, aar, admin, export

app.include_router(auth.router)
app.include_router(scenarios.router)
app.include_router(sessions.router)
app.include_router(red_team.router)
app.include_router(monte_carlo.router)
app.include_router(aar.router)
app.include_router(admin.router)
app.include_router(export.router)

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok", "model": settings.claude_model}

# Serve the React frontend (production: static files are built into ./static)
# Assets (JS/CSS) are mounted first; a catch-all returns index.html for all
# other paths so React Router can handle client-side navigation.
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    _assets_dir = os.path.join(_static_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(_static_dir, "index.html"))
