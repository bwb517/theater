import json
import re
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models
from routers.scenarios import serialize_scenario

router = APIRouter(prefix="/api", tags=["export"])


def _session_or_404(session_id: str, db: Session) -> models.GameSession:
    s = db.query(models.GameSession).filter(models.GameSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.get("/sessions/{session_id}/export/json")
def export_session_json(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    session = _session_or_404(session_id, db)
    scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()

    turns = [
        {
            "turn_number": t.turn_number,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "player_moves": json.loads(t.player_moves or "[]"),
            "ai_moves": json.loads(t.ai_moves or "[]"),
            "adjudication": json.loads(t.adjudication or "{}"),
            "injects_triggered": json.loads(t.injects_triggered or "[]"),
            "game_master_notes": t.game_master_notes,
        }
        for t in session.turn_logs
    ]

    creator_name = None
    if session.created_by:
        u = db.query(models.User).filter(models.User.id == session.created_by).first()
        creator_name = u.username if u else None

    payload = {
        "version": "1.0",
        "schema_version": "v5",
        "scenario": serialize_scenario(scenario_obj) if scenario_obj else {},
        "turns": turns,
        "metadata": {
            "session_id": session.id,
            "session_title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "created_by": creator_name,
            "final_status": session.status,
            "current_turn": session.current_turn,
            "max_turns": session.max_turns,
            "faction_assignments": json.loads(session.faction_assignments or "[]"),
            "time_per_turn_hours": session.time_per_turn_hours,
            "exported_at": datetime.utcnow().isoformat(),
        },
    }

    filename = f"theater_session_{session_id[:8]}_{date.today().strftime('%Y%m%d')}.json"
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sessions/{session_id}/export/markdown")
def export_session_markdown(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    session = _session_or_404(session_id, db)
    scenario_obj = db.query(models.Scenario).filter(models.Scenario.id == session.scenario_id).first()

    sc_title = scenario_obj.title if scenario_obj else "Unknown Scenario"
    sc_type = scenario_obj.scenario_type if scenario_obj else ""
    timeframe = scenario_obj.timeframe if scenario_obj else ""
    situation = json.loads(scenario_obj.situation or "{}") if scenario_obj else {}
    factions = json.loads(scenario_obj.factions or "[]") if scenario_obj else []
    win_conditions = json.loads(scenario_obj.win_conditions or "{}") if scenario_obj else {}

    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        "# THEATER WARGAMING PLATFORM",
        "## AFTER ACTION REVIEW — STRUCTURED TURN LOG",
        "",
        f"**{sc_title.upper()}**",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Exercise Type | {sc_type} |",
        f"| Timeframe | {timeframe} |",
        f"| Session Status | {session.status} |",
        f"| Turns Completed | {session.current_turn} / {session.max_turns} |",
        f"| Exported | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} |",
        "",
        "> UNCLASSIFIED // FOR EXERCISE PURPOSES ONLY",
        "",
    ]

    # ── Section 1: Scenario Overview ────────────────────────────────────────
    lines += ["---", "", "## SECTION 1: SCENARIO OVERVIEW", ""]
    overview = situation.get("summary") or situation.get("background") or situation.get("description", "")
    if overview:
        lines.append(overview)
    lines.append("")

    # ── Section 2: Order of Battle ───────────────────────────────────────────
    lines += ["## SECTION 2: ORDER OF BATTLE", ""]
    for f in factions:
        name = f.get("name") or f.get("faction_id", "Unknown")
        side = f.get("side", "?")
        posture = f.get("starting_posture", "")
        units = f.get("units", [])
        lines.append(f"### [{side}] {name}")
        if posture:
            lines.append(f"*Starting posture: {posture}*")
        if units:
            lines.append(f"*{len(units)} units*")
        lines.append("")

    # ── Section 3: Win Conditions ────────────────────────────────────────────
    lines += ["## SECTION 3: WIN CONDITIONS", ""]
    for label, key in [("BLUE WIN", "blue_wins"), ("RED WIN", "red_wins")]:
        for i, cond in enumerate(win_conditions.get(key, []), 1):
            text = cond.get("condition", cond) if isinstance(cond, dict) else cond
            lines.append(f"**{label} {i}:** {text}")
    lines.append("")

    # ── Section 4: Chronological Turn Log ───────────────────────────────────
    lines += ["## SECTION 4: CHRONOLOGICAL TURN LOG", ""]
    for t in session.turn_logs:
        ts = t.timestamp.strftime("%Y-%m-%d %H:%M UTC") if t.timestamp else "—"
        lines.append(f"### TURN {t.turn_number}  ·  {ts}")
        lines.append("")

        player_moves = json.loads(t.player_moves or "[]")
        ai_moves = json.loads(t.ai_moves or "[]")
        adjudication = json.loads(t.adjudication or "{}")
        injects = json.loads(t.injects_triggered or "[]")

        if player_moves:
            lines.append("#### Player Orders")
            for m in player_moves:
                faction_id = m.get("faction_id", "?")
                move_data = m.get("moves", m)
                for wf in ("maneuver", "fires", "intelligence", "logistics", "information_ops"):
                    val = move_data.get(wf)
                    if val:
                        lines.append(f"- **[{faction_id}] {wf.replace('_', ' ').title()}:** {val}")
            lines.append("")

        if ai_moves:
            lines.append("#### AI / Red Force Moves")
            for m in ai_moves:
                faction_id = m.get("faction_id", "Red")
                summary = m.get("summary") or m.get("coa_summary") or str(m)[:200]
                lines.append(f"- **[{faction_id}]** {summary}")
            lines.append("")

        if adjudication:
            lines.append("#### Adjudication")
            narrative = adjudication.get("narrative") or adjudication.get("summary", "")
            if narrative:
                lines.append(narrative)
                lines.append("")
            casualties = adjudication.get("casualties", {})
            if casualties:
                lines.append("**Casualties:**")
                for side, data in casualties.items():
                    lines.append(f"- {side}: {data}")
                lines.append("")

        if injects:
            lines.append("#### Injects Triggered")
            for inj in injects:
                text = inj.get("title", inj) if isinstance(inj, dict) else inj
                lines.append(f"- {text}")
            lines.append("")

        if t.game_master_notes:
            lines.append("#### GM Notes")
            lines.append(t.game_master_notes)
            lines.append("")

    # ── Section 5: Final Game State ──────────────────────────────────────────
    lines += ["## SECTION 5: FINAL GAME STATE", ""]
    final = json.loads(session.current_game_state or "{}")
    for fid, fdata in final.get("factions", {}).items():
        if isinstance(fdata, dict):
            wtf = fdata.get("will_to_fight", "?")
            units = fdata.get("units", [])
            active = sum(1 for u in units if not u.get("destroyed"))
            lines.append(f"**{fid}** — Will to Fight: {wtf} | Active Units: {active}/{len(units)}")
    lines.append("")

    lines += ["---", "", "*Generated by THEATER Wargaming Platform | UNCLASSIFIED*"]

    slug = re.sub(r"[^a-z0-9]+", "_", sc_title.lower())[:30].strip("_")
    filename = f"theater_{slug}_{date.today().strftime('%Y%m%d')}.md"
    return Response(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/scenarios/{scenario_id}/export/template")
def export_scenario_template(
    scenario_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    s = db.query(models.Scenario).filter(models.Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")

    payload = {
        "export_version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        # Fields needed to re-import via POST /api/scenarios
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
        # id, created_by, created_at, published metadata intentionally omitted
    }

    slug = re.sub(r"[^a-z0-9]+", "_", s.title.lower())[:30].strip("_")
    filename = f"theater_scenario_{slug}_{date.today().strftime('%Y%m%d')}.json"
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
