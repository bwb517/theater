# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# THEATER

Full-stack AI military wargaming platform. FastAPI backend + React/Vite frontend + SQLite (dev) / PostgreSQL (prod). Uses Claude claude-sonnet-4-6 for scenario generation, red team AI, turn adjudication, Monte Carlo analysis, and AAR writing.

---

## Backend

| File | Purpose |
|------|---------|
| `backend/main.py` | App root — CORS middleware, `_run_migrations()` for SQLite ALTER TABLE, registers all 7 routers, `/health` endpoint |
| `backend/database.py` | SQLAlchemy engine/session (WAL mode for SQLite), Pydantic `Settings`, LRU-cached `get_settings()`, reads `.env` |
| `backend/models.py` | ORM models: `User`, `Scenario`, `GameSession`, `TurnLog`, `MonteCarloResult`, `AARReport`, `UnitTemplate`, `TokenUsage` — all UUID PKs |
| `backend/auth.py` | JWT + bcrypt: `hash_password`, `create_access_token`, `get_current_user` dependency, `get_optional_user` (public routes), `require_role` decorator |
| `backend/limiter.py` | slowapi `Limiter` instance — import and apply `@limiter.limit("N/period")` on expensive endpoints |
| `backend/ai_client.py` | **All Claude calls** — see AI Client section below |
| `backend/seed_data.py` | Demo users (admin/gamemaster/player1, pw: `theater123`), 50+ unit templates, 5 scenario templates, demo session with 4 turns |
| `backend/routers/auth.py` | `POST /register`, `POST /login`, `GET /me` |
| `backend/routers/scenarios.py` | Scenario CRUD, `POST /generate` (NL → AI), unit library, OOB import from text/file/Wikipedia |
| `backend/routers/sessions.py` | Session CRUD, submit moves, advance-turn, GM notes, game-state update |
| `backend/routers/red_team.py` | `POST /red-team` (AI moves), `POST /adjudicate`, `PUT /personality` |
| `backend/routers/monte_carlo.py` | `POST /run` (rate-limited 5/hour), `GET` by ID / session / scenario |
| `backend/routers/aar.py` | Generate 7-section AAR, PDF export via reportlab, public share token (no auth required) |
| `backend/routers/admin.py` | Stats, user list, session audit — admin role required |

---

## Frontend

| File | Purpose |
|------|---------|
| `frontend/src/App.jsx` | `AuthContext`, `BrowserRouter`, `ProtectedRoute` HOC, all route definitions |
| `frontend/src/api/client.js` | Axios instance, JWT Bearer interceptor, 401 auto-logout; all API helper functions (`authApi`, `scenariosApi`, `sessionsApi`, `redTeamApi`, `monteCarloApi`, `aarApi`) |
| `frontend/src/components/Layout.jsx` | Sidebar nav, classification banner (`UNCLASSIFIED // FOR DEMONSTRATION`), top bar with user/logout |
| `frontend/src/components/OperationalMap.jsx` | Leaflet + react-leaflet map, CartoDB Dark Matter basemap, faction-colored unit markers; artillery range rings, movement-arrow overlays for pending orders, destination-pick mode, force filter, key terrain overlay. `AutoFitBounds` fires **once** on initial load (ref-guarded) — does not re-fit on interaction. |
| `frontend/src/components/OrdersForm.jsx` | Player move submission — 5 warfighting function fields (Maneuver, Fires, Intelligence, Logistics, Information Ops); each fires/maneuver order includes a unit selector populated from player-faction OOB |
| `frontend/src/components/TurnDiffPanel.jsx` | Side-by-side prev/current turn state comparison |
| `frontend/src/pages/Login.jsx` | Auth form, stores JWT + user in localStorage |
| `frontend/src/pages/Dashboard.jsx` | Stats hub, recent sessions/scenarios, quick-create links |
| `frontend/src/pages/ScenarioLibrary.jsx` | Search/filter/clone/delete scenarios, OOB import |
| `frontend/src/pages/ScenarioBuilder.jsx` | NL prompt → AI scenario generation, JSON editor, live map preview |
| `frontend/src/pages/GameSession.jsx` | 5-tab gameplay: Operational Map, Player Moves, Turn Log, Intelligence, Scores |
| `frontend/src/pages/RedTeamConsole.jsx` | AI adversary control, personality config, COA display, manual GM inject |
| `frontend/src/pages/MonteCarloAnalyzer.jsx` | Recharts probability bars, decision points table, risk factors, sensitivity findings; run-count selector (5/10/20/30) |
| `frontend/src/pages/AARGenerator.jsx` | 7-section collapsible AAR, PDF/Markdown export, shareable link generation |
| `frontend/src/pages/Admin.jsx` | User management, session audit log — admin only |

---

## Architecture Patterns

- **All Claude calls live in `backend/ai_client.py`** — routers never import `anthropic` directly; add new AI features there
- **`extract_json()`** handles markdown code blocks, preamble, and truncation — use it for every new Claude call
- **Prompt caching**: every AI function puts its system prompt and JSON output schema in separate `system` blocks with `"cache_control": {"type": "ephemeral"}` — both blocks must be cached, not just the system text
- **`_log_tokens(function_name, response.usage)`** is called after every Claude API call and writes to the `TokenUsage` table — include this in any new AI function
- **Token efficiency helpers** (do not bypass these): `_slim_game_state()` strips non-essential unit fields before serializing to red-team/adjudication prompts; `_slim_scenario_for_mc()` strips unit capability arrays and verbose planning_assumptions fields before Monte Carlo
- **Monte Carlo batching**: `run_monte_carlo()` splits runs into parallel batches of 5 via `asyncio.gather()`. Batch 0 uses `MONTE_CARLO_SCHEMA` (full aggregate with narratives); subsequent batches use `MONTE_CARLO_LITE_SCHEMA` (runs + decision points/risk factors only). `_merge_monte_carlo_results()` combines them and computes outcome probabilities from binary run outcomes
- **Game state** stored as JSON in `GameSession.current_game_state`; turn logs are append-only for audit trail
- **Game state initialization** (`routers/sessions.py`): `MOVEMENT_RATES`, `MUNITIONS_DEFAULTS`, and `MUNITIONS_BY_CAPABILITY` dicts drive unit capability seeding at session creation; `_wtf_from_posture()` derives initial will-to-fight from faction starting posture
- **Auth**: `get_current_user` dependency on protected endpoints; `get_optional_user` for endpoints accessible both authenticated and anonymously (e.g. public AAR share); `require_role("admin")` decorator for admin gates
- **Schema migrations**: SQLite doesn't support `CREATE TABLE ... IF NOT EXISTS` for new columns — add new columns to `_run_migrations()` in `main.py` using `ALTER TABLE`, not to `create_all()`
- **Rate limiting**: import `limiter` from `backend/limiter.py` and decorate with `@limiter.limit("5/hour")` on AI-heavy endpoints — Monte Carlo is already rate-limited
- **All API helpers** belong in `frontend/src/api/client.js` — don't call axios directly from pages
- **Vite proxies** `/api` → `http://localhost:8000` in dev — no CORS issues locally
- **`faction_assignments`** on `GameSession` drives player unit visibility. `ScenarioLibrary.jsx` auto-derives it from `scenario.factions[].role` at session creation (`'AI-controlled'` → `'AI'`, everything else → `'Player'`). `GameSession.jsx` falls back to scenario roles when the array is empty (handles legacy sessions stored with `[]`)
- **`ai_personality_overrides`** on `GameSession` is a JSON column (faction_id → personality string) added via migration; `RedTeamConsole.jsx` reads/writes it via `PUT /api/red-team/personality`

---

## Dev Environment

```
# Backend
start_backend.bat              # Windows (creates venv, installs deps, seeds DB, starts uvicorn)
cd backend && uvicorn main:app --reload   # manual

# Frontend
start_frontend.bat             # Windows (npm install + vite dev on port 3000)
cd frontend && npm run dev     # manual

# Seed DB (run once with venv activated)
cd backend && python seed_data.py

# API docs
http://localhost:8000/docs
```

Key `.env` vars: `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` (default: `claude-sonnet-4-6`), `SECRET_KEY`, `DATABASE_URL` (default: `sqlite:///./theater.db`), `FRONTEND_URL` (default: `http://localhost:3000`), `TOKEN_BUDGET` (default: 1,000,000 — informational, not enforced automatically)

---

## Known Quirks

**Python 3.9 (Windows Store) — package version ceilings:**

| Package | Max version | Reason |
|---------|-------------|--------|
| `numpy` | 2.0.2 | 2.1.0+ requires Python 3.10 |
| `scipy` | 1.13.1 | 1.14.0+ requires Python 3.10 |
| `networkx` | 3.2.1 | 3.3.0+ requires Python 3.10 |
| `greenlet` | 3.1.1 | 3.2.5 has no cp39-win_amd64 wheel; SQLAlchemy 2.x pulls it in |
| `bcrypt` | 4.0.1 | 5.0.0 breaks passlib 1.7.4 `verify_password` |
| `uvicorn` | — | Use without `[standard]` extras (avoids watchfiles/greenlet compilation) |

- Python 3.10+ union type syntax `X | Y` — add `from __future__ import annotations` to any file using it
- Shell is **Command Prompt (cmd)**, not PowerShell — use `rd /s /q venv` not `Remove-Item`
- `theater.db` is created empty by `create_all()` on first startup even if seed hasn't run. `start_backend.bat` skips seeding if the file already exists. If demo users are missing, run `python seed_data.py` manually from `backend/` with the venv activated.
