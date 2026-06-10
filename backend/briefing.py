"""Deterministic briefing-export builder for THEATER.

Turns a completed (or in-progress) game into a structured analyst memo: a decision
timeline, a quantified state-evolution series, algorithmically-detected turning
points, and an outcome. It is the factual counterpart to the AI-written AAR — and,
unlike the AAR, it is fully deterministic (no LLM), so the same game always yields
byte-identical output and the turning-point logic is unit-testable.

The single source of truth is the AdjudicationLog audit trail. The router feeds rows
shaped as:
    { "turn_number": int,
      "ai_inputs":  {... "unit_status": [...], "faction_scores": [...],
                         "blue_moves": [...], "red_moves": [...]},
      "turn_outcome": {... "casualties", "terrain_changes", "score_changes",
                           "decisive_moment", "key_events",
                           "will_to_fight_changes", "c2_changes", "narrative"} }
plus the session's final `current_game_state` and lightweight scenario/session metadata.

Pure module: no DB, no network, no I/O — mirrors rules_engine.py / game_consts.py so
it can be exercised in isolation.
"""
from __future__ import annotations

from datetime import datetime

from game_consts import STRENGTH_RANK, STRENGTH_LADDER

# --- tunable detection weights (documented so tests can pin them) -----------
# impact_score = abs(force_ratio_delta)            # strength balance swing, 0-100 pts
#              + W_SCORE   * abs(net_score_swing)  # victory-point swing toward one side
#              + W_TERRAIN * terrain_count         # key-terrain objectives that changed hands
#              + W_MORALE  * morale_c2_count        # units that broke or lost C2
W_SCORE = 0.5
W_TERRAIN = 8.0
W_MORALE = 3.0

# Number of turning points surfaced (fewer if the game is shorter).
TOP_N_TURNING_POINTS = 3

# |blue_total - red_total| at or below this final-score gap reads as a draw.
STALEMATE_THRESHOLD = 5

# One-line definition of the strength metric, surfaced in metadata so the UI,
# Markdown, and PDF all describe it identically.
STRENGTH_METRIC_NOTE = (
    "Mean force strength is the average unit health (0-100) across a side's units. "
    "A unit's health is its manning percentage, or — when manning is unavailable — a "
    "mapping from its strength state (Full=100, Degraded~67, Critical~33, Destroyed=0)."
)

# Impact-score buckets for the human-readable significance label.
_DECISIVE_AT = 40.0
_SIGNIFICANT_AT = 20.0

# Ordinal ladders for "did this get worse?" checks (lower index == healthier).
_WTF_RANK = {"High": 0, "Moderate": 1, "Low": 2, "Broken": 3}
_C2_RANK = {"Nominal": 0, "Degraded": 1, "Lost": 2}

# Strength enum -> health percentage when a unit carries no explicit `manning`.
_STRENGTH_HEALTH = {
    s: round(100.0 * (1 - STRENGTH_RANK[s] / (len(STRENGTH_LADDER) - 1)), 1)
    for s in STRENGTH_LADDER
}


# ---------------------------------------------------------------------------
# Side / strength helpers
# ---------------------------------------------------------------------------

def _norm_side(side) -> str | None:
    """Map a faction's free-text side to canonical 'Blue'/'Red' (others -> None)."""
    if not side:
        return None
    s = str(side).strip().lower()
    if s.startswith("blue"):
        return "Blue"
    if s.startswith("red"):
        return "Red"
    return None


def build_side_map(scenario: dict) -> dict:
    """faction_id -> 'Blue'/'Red' from scenario.factions[].side."""
    side_map: dict[str, str] = {}
    for f in (scenario or {}).get("factions", []) or []:
        if not isinstance(f, dict):
            continue
        fid = f.get("faction_id")
        side = _norm_side(f.get("side"))
        if fid and side:
            side_map[fid] = side
    return side_map


def unit_health(unit: dict) -> float | None:
    """A unit's health in [0,100]: explicit `manning` if present, else strength enum."""
    if not isinstance(unit, dict):
        return None
    manning = unit.get("manning")
    if isinstance(manning, (int, float)):
        return float(max(0.0, min(100.0, manning)))
    return _STRENGTH_HEALTH.get(unit.get("strength"))


def side_strength(unit_status: list, side_map: dict, side: str) -> float | None:
    """Mean unit health for one side (mean, so it's robust to unit count).

    None when that side has no units with a readable health in this snapshot —
    distinct from 0.0, which means present-but-destroyed.
    """
    healths = []
    for u in unit_status or []:
        if not isinstance(u, dict):
            continue
        if side_map.get(u.get("faction_id")) != side:
            continue
        h = unit_health(u)
        if h is not None:
            healths.append(h)
    if not healths:
        return None
    return round(sum(healths) / len(healths), 1)


def _strength_snapshot(unit_status: list, side_map: dict) -> dict:
    return {
        "blue": side_strength(unit_status, side_map, "Blue"),
        "red": side_strength(unit_status, side_map, "Red"),
    }


# ---------------------------------------------------------------------------
# Per-turn metric extraction
# ---------------------------------------------------------------------------

def _net_score_swing(turn_outcome: dict, side_map: dict) -> float:
    """Blue minus Red of summed score_changes[].change for this turn."""
    blue = red = 0.0
    for sc in (turn_outcome or {}).get("score_changes", []) or []:
        if not isinstance(sc, dict):
            continue
        try:
            change = float(sc.get("change", 0) or 0)
        except (TypeError, ValueError):
            continue
        side = side_map.get(sc.get("faction_id"))
        if side == "Blue":
            blue += change
        elif side == "Red":
            red += change
    return blue - red


def _terrain_count(turn_outcome: dict) -> int:
    tc = (turn_outcome or {}).get("terrain_changes", []) or []
    return len(tc) if isinstance(tc, list) else 0


def _morale_c2_count(turn_outcome: dict) -> int:
    """Units whose will-to-fight or C2 degraded this turn."""
    count = 0
    for w in (turn_outcome or {}).get("will_to_fight_changes", []) or []:
        if not isinstance(w, dict):
            continue
        a, b = _WTF_RANK.get(w.get("from")), _WTF_RANK.get(w.get("to"))
        if a is not None and b is not None and b > a:
            count += 1
    for c in (turn_outcome or {}).get("c2_changes", []) or []:
        if not isinstance(c, dict):
            continue
        a, b = _C2_RANK.get(c.get("from")), _C2_RANK.get(c.get("to"))
        if a is not None and b is not None and b > a:
            count += 1
    return count


def _key_decisions(turn_outcome: dict) -> list:
    """Decisive moment + key events, deduped, for the timeline."""
    out: list[str] = []
    dm = (turn_outcome or {}).get("decisive_moment")
    if dm:
        out.append(str(dm))
    for ev in (turn_outcome or {}).get("key_events", []) or []:
        if ev and str(ev) not in out:
            out.append(str(ev))
    return out


# ---------------------------------------------------------------------------
# Turning-point detection
# ---------------------------------------------------------------------------

def _impact_score(m: dict) -> float:
    return (
        abs(m["force_ratio_delta"])
        + W_SCORE * abs(m["net_score_swing"])
        + W_TERRAIN * m["terrain_count"]
        + W_MORALE * m["morale_c2_count"]
    )


def _significance(score: float, force_ratio_delta: float) -> str:
    if score >= _DECISIVE_AT:
        tier = "Decisive"
    elif score >= _SIGNIFICANT_AT:
        tier = "Significant"
    else:
        tier = "Moderate"
    if force_ratio_delta > 0.5:
        return f"{tier} swing in Blue's favor"
    if force_ratio_delta < -0.5:
        return f"{tier} swing in Red's favor"
    return f"{tier} shift with no clear beneficiary"


def _describe(m: dict) -> str:
    """Templated, deterministic prose for one turning point."""
    n = m["turn_number"]
    bd, rd = m["blue_delta"], m["red_delta"]
    clauses: list[str] = []
    if bd is not None and rd is not None:
        frd = m["force_ratio_delta"]
        beneficiary = "Blue" if frd > 0 else "Red" if frd < 0 else "neither side"
        clauses.append(
            f"Blue force strength changed {bd:+.1f} pts and Red {rd:+.1f} pts, "
            f"shifting the balance toward {beneficiary} ({frd:+.1f})"
        )
    if m["terrain_count"]:
        clauses.append(f"{m['terrain_count']} key-terrain objective(s) changed hands")
    if m["morale_c2_count"]:
        clauses.append(f"{m['morale_c2_count']} unit(s) suffered morale/C2 degradation")
    if abs(m["net_score_swing"]) >= 0.5:
        clauses.append(f"net victory-point swing of {m['net_score_swing']:+.1f}")
    body = "; ".join(clauses) if clauses else "marginal change across all dimensions"
    text = f"Turn {n}: {body}."
    if m.get("decisive_moment"):
        text += f" Decisive moment: {m['decisive_moment']}"
    return text


def _why_significant(m: dict) -> str:
    """Name the dominant contributor to this turn's impact score."""
    contributions = {
        "force-strength balance": abs(m["force_ratio_delta"]),
        "victory-point swing": W_SCORE * abs(m["net_score_swing"]),
        "key-terrain control": W_TERRAIN * m["terrain_count"],
        "morale/C2 collapse": W_MORALE * m["morale_c2_count"],
    }
    driver = max(contributions, key=contributions.get)
    if contributions[driver] <= 0:
        return "Flagged for relative magnitude; no single dimension dominated."
    return f"Primary driver: {driver}."


def identify_turning_points(turn_metrics: list) -> list:
    """Rank per-turn metric dicts and return the top turning points.

    `turn_metrics` is the list produced by build_briefing — one dict per turn with
    blue/red strength deltas and the per-turn outcome counts. Pure and sync so a
    synthetic game with known pivots can be asserted directly.

    Sort is by impact_score descending with a stable tie-break on turn_number
    (ascending), so equal-impact turns come out earliest-first and the result is
    deterministic.
    """
    scored = []
    for m in turn_metrics:
        score = round(_impact_score(m), 2)
        scored.append((score, m))
    # Stable secondary sort on turn_number first, then primary on -score.
    scored.sort(key=lambda x: x[1]["turn_number"])
    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for score, m in scored[:TOP_N_TURNING_POINTS]:
        if score <= 0:
            continue  # a zero-impact turn is not a turning point
        out.append({
            "turn_number": m["turn_number"],
            "description": _describe(m),
            "impact_on_outcome": _significance(score, m["force_ratio_delta"]),
            "why_significant": _why_significant(m),
            "impact_score": score,
        })
    return out


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------

def _final_side_scores(final_state: dict, side_map: dict) -> tuple[float, float]:
    blue = red = 0.0
    for fs in (final_state or {}).get("faction_scores", []) or []:
        if not isinstance(fs, dict):
            continue
        try:
            score = float(fs.get("score", 0) or 0)
        except (TypeError, ValueError):
            continue
        side = side_map.get(fs.get("faction_id"))
        if side == "Blue":
            blue += score
        elif side == "Red":
            red += score
    return blue, red


def _determine_outcome(blue_total: float, red_total: float) -> str:
    if abs(blue_total - red_total) <= STALEMATE_THRESHOLD:
        return "Stalemate"
    return "Blue won" if blue_total > red_total else "Red won"


def _objectives_achieved(final_state: dict, side_map: dict) -> list:
    out = []
    for fs in (final_state or {}).get("faction_scores", []) or []:
        if not isinstance(fs, dict):
            continue
        out.append({
            "faction_id": fs.get("faction_id"),
            "name": fs.get("name"),
            "side": side_map.get(fs.get("faction_id")),
            "score": fs.get("score"),
            "objective_status": fs.get("objective_status", "Unknown"),
        })
    return out


def _terrain_control(final_state: dict, adjudication_rows: list, side_map: dict) -> dict:
    """Net key-terrain by side. Uses controlled_terrain if present, else the
    cumulative to_faction of every terrain_changes entry across the game."""
    controlled = (final_state or {}).get("controlled_terrain") or []
    tally = {"Blue": 0, "Red": 0, "Other": 0}
    if isinstance(controlled, list) and controlled:
        for t in controlled:
            fid = t.get("faction_id") if isinstance(t, dict) else None
            tally[side_map.get(fid, "Other")] += 1
        return tally
    # Fallback: replay terrain_changes; last owner wins per location.
    owner_by_loc: dict[str, str] = {}
    for row in adjudication_rows:
        for tc in (row.get("turn_outcome") or {}).get("terrain_changes", []) or []:
            if isinstance(tc, dict) and tc.get("location"):
                owner_by_loc[tc["location"]] = tc.get("to_faction")
    for fid in owner_by_loc.values():
        tally[side_map.get(fid, "Other")] += 1
    return tally


# ---------------------------------------------------------------------------
# Move condensation (for the timeline)
# ---------------------------------------------------------------------------

def _condense_moves(moves: list) -> list:
    """Flatten a side's submitted moves into short '[faction] function: detail' lines."""
    lines: list[str] = []
    for entry in moves or []:
        if not isinstance(entry, dict):
            continue
        fid = entry.get("faction_id", "?")
        data = entry.get("moves", entry)
        if not isinstance(data, dict):
            continue
        for wf in ("maneuver", "fires", "intelligence", "logistics", "information_ops"):
            val = data.get(wf)
            if not val:
                continue
            label = wf.replace("_", " ").title()
            if isinstance(val, list):
                lines.append(f"[{fid}] {label}: {len(val)} order(s)")
            else:
                lines.append(f"[{fid}] {label}: {str(val)[:120]}")
    return lines


def _adjudication_summary(turn_outcome: dict) -> str:
    narrative = (turn_outcome or {}).get("narrative")
    if narrative:
        return str(narrative)
    dm = (turn_outcome or {}).get("decisive_moment")
    return str(dm) if dm else ""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def build_briefing(
    scenario: dict,
    adjudication_rows: list,
    final_state: dict,
    session_meta: dict,
) -> dict:
    """Assemble the full briefing dict. See module docstring for input shapes."""
    scenario = scenario or {}
    final_state = final_state or {}
    session_meta = session_meta or {}
    rows = [r for r in (adjudication_rows or []) if isinstance(r, dict)]
    rows.sort(key=lambda r: r.get("turn_number", 0))

    side_map = build_side_map(scenario)

    # --- per-turn snapshots (start of each turn) + final snapshot -----------
    snapshots = [_strength_snapshot((r.get("ai_inputs") or {}).get("unit_status", []), side_map)
                 for r in rows]
    final_snap = _strength_snapshot(final_state.get("unit_status", []), side_map)

    # --- state_evolution: initial point + one "after each turn" point -------
    state_evolution = []
    if rows:
        first_turn = rows[0].get("turn_number", 1)
        state_evolution.append({
            "turn": first_turn - 1,
            "blue_strength": snapshots[0]["blue"],
            "red_strength": snapshots[0]["red"],
        })
        for i, r in enumerate(rows):
            after = snapshots[i + 1] if i + 1 < len(snapshots) else final_snap
            state_evolution.append({
                "turn": r.get("turn_number"),
                "blue_strength": after["blue"],
                "red_strength": after["red"],
            })
    else:
        state_evolution.append({
            "turn": session_meta.get("current_turn", 0),
            "blue_strength": final_snap["blue"],
            "red_strength": final_snap["red"],
        })

    # --- per-turn metrics + timeline ---------------------------------------
    turn_metrics = []
    timeline = []
    for i, r in enumerate(rows):
        outcome = r.get("turn_outcome") or {}
        inputs = r.get("ai_inputs") or {}
        before = snapshots[i]
        after = snapshots[i + 1] if i + 1 < len(snapshots) else final_snap

        def _delta(key):
            b, a = before[key], after[key]
            return None if b is None or a is None else round(a - b, 1)

        blue_delta = _delta("blue")
        red_delta = _delta("red")
        force_ratio_delta = 0.0
        if blue_delta is not None and red_delta is not None:
            force_ratio_delta = round(blue_delta - red_delta, 1)

        metric = {
            "turn_number": r.get("turn_number"),
            "blue_delta": blue_delta,
            "red_delta": red_delta,
            "force_ratio_delta": force_ratio_delta,
            "net_score_swing": _net_score_swing(outcome, side_map),
            "terrain_count": _terrain_count(outcome),
            "morale_c2_count": _morale_c2_count(outcome),
            "decisive_moment": outcome.get("decisive_moment"),
        }
        turn_metrics.append(metric)

        timeline.append({
            "turn_number": r.get("turn_number"),
            "blue_moves": _condense_moves(inputs.get("blue_moves", [])),
            "red_response": _condense_moves(inputs.get("red_moves", [])),
            "key_decisions": _key_decisions(outcome),
            "state_changes": {
                "blue_strength_delta": blue_delta,
                "red_strength_delta": red_delta,
                "terrain_changes": outcome.get("terrain_changes", []) or [],
                "score_changes": outcome.get("score_changes", []) or [],
                "casualties": outcome.get("casualties", []) or [],
            },
            "adjudication_summary": _adjudication_summary(outcome),
        })

    turning_points = identify_turning_points(turn_metrics)

    # --- outcome ------------------------------------------------------------
    blue_total, red_total = _final_side_scores(final_state, side_map)
    outcome = _determine_outcome(blue_total, red_total)
    objectives = _objectives_achieved(final_state, side_map)
    terrain_control = _terrain_control(final_state, rows, side_map)

    final_block = {
        "blue_strength": final_snap["blue"],
        "red_strength": final_snap["red"],
        "terrain_control": terrain_control,
        "objectives_achieved": objectives,
    }

    return {
        "metadata": {
            "session_id": session_meta.get("session_id"),
            "session_title": session_meta.get("session_title"),
            "scenario_title": scenario.get("title", "Untitled Scenario"),
            "scenario_type": scenario.get("scenario_type", "—"),
            "classification": scenario.get("classification", "UNCLASSIFIED"),
            "turns_played": len(rows),
            "max_turns": session_meta.get("max_turns"),
            "status": session_meta.get("status"),
            "generated_at": datetime.utcnow().isoformat(),
            "strength_metric_note": STRENGTH_METRIC_NOTE,
        },
        "executive_summary": _executive_summary(
            scenario, session_meta, len(rows), outcome,
            blue_total, red_total, final_snap, turning_points,
        ),
        "timeline": timeline,
        "turning_points": turning_points,
        "state_evolution": state_evolution,
        "final_state": final_block,
        "outcome": outcome,
        "outcome_narrative": _outcome_narrative(
            outcome, blue_total, red_total, final_snap, objectives,
        ),
    }


# ---------------------------------------------------------------------------
# Templated prose
# ---------------------------------------------------------------------------

def _fmt_strength(v) -> str:
    return f"{v:.1f}" if isinstance(v, (int, float)) else "n/a"


def _executive_summary(scenario, session_meta, turns_played, outcome,
                       blue_total, red_total, final_snap, turning_points) -> str:
    title = scenario.get("title", "the scenario")
    stype = scenario.get("scenario_type", "wargame")
    parts = [
        f"This briefing summarizes a {stype.lower()} exercise on \"{title}\" spanning "
        f"{turns_played} adjudicated turn(s).",
        f"Final outcome: {outcome} "
        f"(Blue {blue_total:.0f} vs Red {red_total:.0f} victory points).",
        f"Closing force strength stood at Blue {_fmt_strength(final_snap['blue'])} / "
        f"Red {_fmt_strength(final_snap['red'])} (mean unit health, 0-100).",
    ]
    if turning_points:
        tp = turning_points[0]
        parts.append(
            f"The most pivotal moment was turn {tp['turn_number']} "
            f"({tp['impact_on_outcome'].lower()})."
        )
    else:
        parts.append("No decisive turning points were detected from the adjudication record.")
    return " ".join(parts)


def _outcome_narrative(outcome, blue_total, red_total, final_snap, objectives) -> str:
    parts = [
        f"Result: {outcome}.",
        f"Blue closed with {blue_total:.0f} victory points and mean force strength "
        f"{_fmt_strength(final_snap['blue'])}; Red closed with {red_total:.0f} points and "
        f"{_fmt_strength(final_snap['red'])}.",
    ]
    achieved = [o for o in objectives if str(o.get("objective_status", "")).lower()
                in ("achieved", "complete", "completed")]
    if achieved:
        names = ", ".join(o.get("name") or o.get("faction_id") or "?" for o in achieved)
        parts.append(f"Objectives marked achieved: {names}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Markdown renderer (pure -> enables format-consistency tests)
# ---------------------------------------------------------------------------

def briefing_to_markdown(briefing: dict) -> str:
    """Render a briefing dict to Markdown. Reads the same dict the JSON endpoint
    returns, so the two formats can never drift in content."""
    b = briefing or {}
    md = b.get("metadata", {})
    lines: list[str] = []

    lines += [
        f"# INTELLIGENCE BRIEFING — {md.get('scenario_title', 'Untitled')}",
        "",
        f"> {md.get('classification', 'UNCLASSIFIED')} // FOR EXERCISE PURPOSES ONLY",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Session | {md.get('session_title', '—')} |",
        f"| Exercise Type | {md.get('scenario_type', '—')} |",
        f"| Turns Played | {md.get('turns_played', 0)} |",
        f"| Status | {md.get('status', '—')} |",
        f"| Outcome | **{b.get('outcome', '—')}** |",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        b.get("executive_summary", ""),
        "",
        "## Outcome",
        "",
        b.get("outcome_narrative", ""),
        "",
    ]

    # Turning points — every description is reproduced verbatim (consistency test).
    lines += ["## Turning Points", ""]
    tps = b.get("turning_points", [])
    if tps:
        for tp in tps:
            lines.append(f"### Turn {tp.get('turn_number')} — {tp.get('impact_on_outcome', '')}")
            lines.append(tp.get("description", ""))
            lines.append(f"*{tp.get('why_significant', '')}* (impact score "
                         f"{tp.get('impact_score', 0)})")
            lines.append("")
    else:
        lines += ["_No turning points detected._", ""]

    # State evolution table.
    lines += ["## State Evolution (mean force strength)", "",
              f"_{STRENGTH_METRIC_NOTE}_", "",
              "| Turn | Blue | Red |", "|------|------|-----|"]
    for pt in b.get("state_evolution", []):
        lines.append(
            f"| {pt.get('turn')} | {_fmt_strength(pt.get('blue_strength'))} "
            f"| {_fmt_strength(pt.get('red_strength'))} |"
        )
    lines.append("")

    # Decision timeline.
    lines += ["## Decision Timeline", ""]
    for t in b.get("timeline", []):
        lines.append(f"### Turn {t.get('turn_number')}")
        sc = t.get("state_changes", {})
        lines.append(
            f"- Strength delta: Blue {sc.get('blue_strength_delta')}, "
            f"Red {sc.get('red_strength_delta')}"
        )
        if t.get("blue_moves"):
            lines.append("- **Blue moves:** " + "; ".join(t["blue_moves"]))
        if t.get("red_response"):
            lines.append("- **Red response:** " + "; ".join(t["red_response"]))
        if t.get("key_decisions"):
            lines.append("- **Key decisions:** " + "; ".join(t["key_decisions"]))
        if t.get("adjudication_summary"):
            lines.append(f"- **Adjudication:** {t['adjudication_summary']}")
        lines.append("")

    # Final state.
    fs = b.get("final_state", {})
    lines += ["## Final State", "",
              f"- Blue strength: {_fmt_strength(fs.get('blue_strength'))}",
              f"- Red strength: {_fmt_strength(fs.get('red_strength'))}",
              f"- Terrain control: {fs.get('terrain_control', {})}", ""]
    for o in fs.get("objectives_achieved", []):
        lines.append(
            f"- [{o.get('side') or '?'}] {o.get('name') or o.get('faction_id')}: "
            f"{o.get('objective_status')} (score {o.get('score')})"
        )
    lines += ["", "---", "", "*Generated deterministically by THEATER — no AI narrative.*"]

    return "\n".join(lines)
