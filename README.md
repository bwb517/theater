# THEATER — AI-Powered Wargaming & Military Scenario Simulation Platform

> **Classification: UNCLASSIFIED // FOR DEMONSTRATION PURPOSES**

THEATER is a full-stack professional wargaming platform that uses Claude AI to generate scenarios, play adversary roles, run probabilistic analysis, and produce structured after-action reviews. Designed for defense contractors, think tanks, military education institutions, and government agencies.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Configure the backend

```bash
cd backend
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start the backend (Windows)

```bat
start_backend.bat
```

### 2. Start the backend (Mac/Linux)

```bash
chmod +x start_backend.sh
./start_backend.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Seed the database with demo data (5 scenario templates, demo session, sample users)
- Start the FastAPI server on **http://localhost:8000**

### 3. Start the frontend (second terminal)

**Windows:**
```bat
start_frontend.bat
```

**Mac/Linux:**
```bash
chmod +x start_frontend.sh
./start_frontend.sh
```

This will:
- Install npm dependencies
- Start Vite dev server on **http://localhost:3000**

### 4. Log in

Open **http://localhost:3000** and log in with:

| Username | Password | Role |
|---|---|---|
| `admin` | `theater123` | Admin |
| `gamemaster` | `theater123` | Game Master |
| `player1` | `theater123` | Player |

---

## Architecture

```
theater/
├── backend/
│   ├── main.py              # FastAPI app + CORS + router registration
│   ├── database.py          # SQLAlchemy engine, session, Settings (pydantic)
│   ├── models.py            # ORM models: User, Scenario, GameSession, TurnLog,
│   │                        #   MonteCarloResult, AARReport, UnitTemplate
│   ├── auth.py              # JWT auth (python-jose + passlib)
│   ├── ai_client.py         # All Claude API calls (5 async functions)
│   ├── seed_data.py         # Demo data: users, scenarios, sessions, MC results, AAR
│   ├── requirements.txt
│   ├── .env.example
│   └── routers/
│       ├── auth.py          # POST /api/auth/register|login, GET /api/auth/me
│       ├── scenarios.py     # CRUD + POST /api/scenarios/generate
│       ├── sessions.py      # CRUD + moves + turn advancement
│       ├── red_team.py      # AI adversary move generation + adjudication
│       ├── monte_carlo.py   # Probabilistic analysis runs
│       ├── aar.py           # AAR generation + PDF export + share links
│       └── admin.py         # Stats, user list, session log
│
└── frontend/
    ├── index.html           # Leaflet CSS, Google Fonts
    ├── vite.config.js       # Port 3000, proxy /api → localhost:8000
    ├── tailwind.config.js   # Military color palette (theater-*)
    └── src/
        ├── App.jsx          # AuthContext, React Router, ProtectedRoute
        ├── api/client.js    # Axios + JWT interceptor + all API helpers
        ├── components/
        │   ├── Layout.jsx          # Sidebar nav + classification banner
        │   ├── LoadingSpinner.jsx  # LoadingSpinner + AIThinking animated
        │   ├── StatusBadge.jsx     # StatusBadge, StrengthBar, SideChip
        │   └── OperationalMap.jsx  # Leaflet + CartoDB Dark Matter + unit markers
        └── pages/
            ├── Login.jsx           # Auth form
            ├── Dashboard.jsx       # Stats, active sessions, scenario library
            ├── ScenarioLibrary.jsx # Search, templates, clone, import JSON
            ├── ScenarioBuilder.jsx # NL → AI → split-pane editor + map preview
            ├── GameSession.jsx     # 5-tab: Map/Moves/Log/Intel/Scores
            ├── RedTeamConsole.jsx  # AI adversary planning with COA development
            ├── MonteCarloAnalyzer.jsx # Probability charts + risk factors
            ├── AARGenerator.jsx    # 7-section AAR + PDF export + share
            └── Admin.jsx           # User management + system stats
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, React Router v6 |
| Maps | Leaflet 1.9, react-leaflet 4, CartoDB Dark Matter tiles |
| Charts | Recharts |
| Icons | lucide-react |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2, PostgreSQL (prod) / SQLite (dev) |
| Auth | python-jose (JWT), passlib (bcrypt) |
| AI | Anthropic Python SDK (`claude-sonnet-4-6`) |
| Simulation | numpy, scipy |
| Graph/OOB | networkx |
| PDF Export | reportlab |

---

## Core Modules

### 1. Scenario Builder
Natural language prompt → Claude generates a complete structured scenario including:
- Full situation narrative (background, precipitating event, current situation)
- Geography with key terrain features and coordinates
- Multi-faction Order of Battle with individual unit positions
- Turn-triggered injects (intel reports, friction events, decision points)
- Weighted victory conditions per faction
- AI designer notes

Leaflet map preview shows unit starting positions with faction-colored markers.

### 2. Game Session Engine
Turn-based adjudication loop:
- Blue (player) submits moves across warfighting functions (Maneuver, Fires, Intel, Logistics, Info Ops, C2)
- Optional: Red Team Console generates AI adversary moves
- Claude adjudicates the turn: produces narrative, casualty estimates, terrain changes, score delta
- Turn log records all moves and adjudication for AAR
- Victory condition tracker updates each turn

### 3. Red Team Console
AI adversary with configurable personality (Aggressive / Cautious / Opportunistic / Deceptive / Attrition-focused):
- Intelligence assessment of the current situation
- 2–3 COA development options with pros/cons
- Selected COA with detailed action tables by warfighting function
- Commander's intent and deception plan
- Manual inject field for game master friction events

### 4. Monte Carlo Analyzer
Runs N abbreviated scenario simulations (5–20) in a single Claude call:
- Outcome probability distribution (bar chart)
- Risk factor identification with frequency and mitigation
- Key decision points table (turn, decision, impact, # of runs it appears in)
- Sensitivity analysis narrative
- Most likely / best case / worst case narratives
- Individual simulation run accordion with assumptions and dominant factors

### 5. AAR Generator
Generates a professional 7-section After Action Review:
1. **Executive Summary** — BLUF + overall assessment
2. **Mission & Objectives** — stated objectives + achievement assessment
3. **Key Decisions** — chronological table of critical choices
4. **Tactical Analysis** — blue and red tactical findings + engagements
5. **Lessons Learned** — sustains and improves with priority/applicability
6. **Strategic Implications** — political/operational/informational dimensions
7. **Recommendations** — prioritized action items for future exercises

Exports to: PDF (via reportlab), Markdown (client-side), shareable link (UUID token).

---

## API Reference

Base URL: `http://localhost:8000/api`
Interactive docs: `http://localhost:8000/docs`

### Authentication
```
POST /auth/register    Create account
POST /auth/login       Get JWT token
GET  /auth/me          Current user info
```

### Scenarios
```
GET    /scenarios              List all scenarios
POST   /scenarios              Create scenario
GET    /scenarios/{id}         Get scenario
PUT    /scenarios/{id}         Update scenario
DELETE /scenarios/{id}         Delete scenario
POST   /scenarios/generate     NL prompt → AI scenario
GET    /scenarios/units/library  Unit template library
```

### Sessions
```
GET  /sessions                    List sessions
POST /sessions                    Create session
GET  /sessions/{id}               Get session with turn logs
POST /sessions/{id}/moves         Submit player moves
POST /sessions/{id}/advance-turn  Adjudicate and advance
PUT  /sessions/{id}/status        Update status
PUT  /sessions/{id}/game-state    Update game state JSON
```

### Red Team
```
POST /sessions/{id}/red-team       Generate AI adversary moves
POST /sessions/{id}/adjudicate     Adjudicate turn (standalone)
PUT  /sessions/{id}/personality    Update AI faction personality
```

### Monte Carlo
```
POST /monte-carlo/run                        Run simulation
GET  /monte-carlo/{id}                       Get result by ID
GET  /monte-carlo/session/{id}/latest        Latest for session
GET  /monte-carlo/scenario/{id}/latest       Latest for scenario
```

### AAR
```
POST /sessions/{id}/aar           Generate AAR
GET  /sessions/{id}/aar           Get existing AAR
GET  /sessions/{id}/aar/pdf       Download PDF
GET  /sessions/aar/share/{token}  Public share endpoint
```

### Admin
```
GET /admin/stats     System statistics
GET /admin/users     All users
GET /admin/sessions  All sessions
```

---

## Environment Variables

See `backend/.env.example`:

```env
ANTHROPIC_API_KEY=sk-ant-...           # Required: your Anthropic API key
CLAUDE_MODEL=claude-sonnet-4-6         # Claude model to use
SECRET_KEY=your-secret-key-here        # JWT signing secret (change in production)
DATABASE_URL=sqlite:///./theater.db    # SQLite path (or PostgreSQL URL)
FRONTEND_URL=http://localhost:3000     # CORS allowed origin
```

---

## Seed Data

Running `seed_data.py` populates:

**Users:** admin, gamemaster, player1 (password: `theater123`)

**Scenario Templates:**
| ID | Name | Type | Factions |
|---|---|---|---|
| IRON_WOLF | NATO vs Russia — Suwalki Gap | Conventional | NATO Brigade vs Russian Mechanized Army |
| STRAIT_GAME | China vs Taiwan — Strait Crossing | Joint | PLA vs ROC + US Forces |
| DESERT_THUNDER | Iran vs GCC — Gulf Straits | Asymmetric | IRGC vs Coalition Naval |
| SHADOW_CAMPAIGN | Cyber-enabled hybrid warfare | Cyber-Hybrid | APT Group vs Defender |


**Demo Session:** IRON WOLF with 4 completed turns, full Monte Carlo results (10 simulation runs), and partial AAR (Sections 1–3).

---

## Commercialization Notes

### SaaS Tiers

| Tier | Price | Features |
|---|---|---|
| **Analyst** | $299/mo | 3 active sessions, 50 AI calls/mo, standard scenarios |
| **Professional** | $999/mo | 20 active sessions, 500 AI calls/mo, custom scenarios, PDF export |
| **Enterprise** | $4,999/mo | Unlimited sessions, unlimited AI, SSO, audit logs, on-prem option |
| **Government** | Custom | Air-gapped deployment, CAC auth, NIPR/SIPR connectivity, FedRAMP |

### Government Licensing Pathway

1. **SBIR/STTR Phase I/II** — Prototype funding via DoD SBIR programs (e.g., SOCOM, DARPA, Army Futures Command)
2. **OTA (Other Transaction Authority)** — Rapid acquisition via Consortium OTAs (AFWERX, DIU, NavalX) — bypasses FAR/DFARS for prototypes
3. **GSA Schedule 70** — IT products and services on GSA MAS (Multiple Award Schedule) — required for civilian agency sales
4. **FedRAMP Authorization** — Required for cloud deployment to federal agencies; pursue FedRAMP Moderate via a 3PAO
5. **CMMC Level 2** — Required for DoD contractors handling CUI; needed before classified scenario content

### Target Customer Segments

- **Defense Contractors**: Raytheon, Lockheed, Northrop, SAIC — use for proposal wargaming and concept development
- **Think Tanks**: RAND, CNA, CNAS, CSIS — political-military analysis and scenario planning
- **Military Education**: NWC, Army War College, CGSC, NDU — professional military education and exercises
- **Government Agencies**: NSC staff, EUCOM/INDOPACOM J5, DIA — strategic planning exercises


### Key Differentiators

1. AI generates complete, militarily-accurate scenarios from plain English — eliminates weeks of manual scenario design
2. Red Team Engine produces doctrine-consistent adversary behavior (not random) — trains planners to anticipate real threats
3. Monte Carlo Analyzer reveals probability distributions — moves from anecdote-based AAR to quantitative analysis
4. Structured 7-section AAR meets joint doctrine standards (JP 3-55) — directly usable in professional reports
5. Fully on-prem deployable — air-gap compatible for classified networks (substitute local LLM for Anthropic API)

---

## Development Notes

### Adding a New AI Feature

1. Add an async function to `backend/ai_client.py` following the pattern:
   ```python
   async def my_feature(data: dict) -> dict:
       client = anthropic.AsyncAnthropic()
       msg = await client.messages.create(
           model=get_settings().claude_model,
           max_tokens=4096,
           system=[{"type": "text", "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}}],
           messages=[{"role": "user", "content": json.dumps(data)}]
       )
       return extract_json(msg.content[0].text)
   ```
2. Add a router endpoint in `backend/routers/`
3. Register it in `backend/main.py`
4. Add the API helper to `frontend/src/api/client.js`

### Switching to PostgreSQL

Change `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost/theater
```
`psycopg2-binary` is already in `requirements.txt` — no additional packages needed.

### Deploying to Production

1. Set `SECRET_KEY` to a cryptographically random value (32+ bytes)
2. Set `FRONTEND_URL` to your domain
3. Use a production WSGI server: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`
4. Serve frontend via nginx or Vercel/Netlify (set `VITE_API_URL` for production backend)
5. Use PostgreSQL instead of SQLite
6. Enable HTTPS — required for JWT security

---

*THEATER v1.0 — Built with Claude claude-sonnet-4-6*
*UNCLASSIFIED // NOT FOR OPERATIONAL USE*
