"""Per-turn probabilistic forecasting — the deterministic scoring core.

Players may, before a turn is adjudicated, assign explicit probabilities to four
binary outcomes. After adjudication the actual outcomes are resolved and the forecast
is scored with the Brier score (Brier, 1950) — the standard meteorological / super-
forecasting accuracy metric. This module is the single source of truth for that math:
pure functions, no DB or network, mirroring briefing.py / rules_engine.py so it can be
exercised in isolation.

Brier score convention (two-class, 0 = perfect, 2 = worst):
    For one binary question with forecast p and outcome o in {0, 1}, the squared error
    is counted for BOTH the event and its complement:
        (p - o)^2 + ((1 - p) - (1 - o))^2  =  2 * (p - o)^2
    The turn score is the mean of that over the four questions, so a perfect forecast
    scores 0, a maximally-wrong forecast scores 2, and a 0.5 guess scores 0.5. This is
    the Good-Judgment / superforecasting convention.
"""
from __future__ import annotations

# Forecast field (probability) -> resolved outcome field (boolean).
QUESTIONS = {
    "p_blue_wins": "blue_achieved",
    "p_red_wins": "red_achieved",
    "p_escalation": "escalation_occurred",
    "p_key_objective_captured": "key_objective_captured",
}

BRIER_NOTE = (
    "Brier score (Brier, 1950) measures probabilistic forecast accuracy: 0 = perfect, "
    "2 = worst, ~0.5 = no better than a coin flip. Lower is better. It is the standard "
    "scoring rule in meteorology and superforecasting research."
)

# Calibration-in-the-large tolerance: how far mean forecast may drift from mean
# outcome before the player reads as over-/under-confident.
_CALIBRATION_TOLERANCE = 0.10


def _clamp01(x) -> float:
    """Coerce to a float probability in [0, 1]; non-numeric -> 0.5 (max ignorance)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, v))


def brier_score(forecast: dict, outcome: dict) -> float:
    """Two-class Brier score over the four questions; 0 = perfect, 2 = worst.

    `forecast` maps probability fields -> estimates; `outcome` maps the resolved
    boolean fields -> truth values. Both are read by name via QUESTIONS, so callers
    may pass dicts or any mapping.
    """
    components = []
    for p_field, o_field in QUESTIONS.items():
        p = _clamp01(forecast.get(p_field))
        o = 1.0 if bool(outcome.get(o_field)) else 0.0
        components.append(2.0 * (p - o) ** 2)
    return round(sum(components) / len(components), 4)


def resolve_outcomes(result: dict, prev_state: dict, new_state: dict, side_map: dict) -> dict:
    """Resolve the four binary outcomes from an adjudication result + game-state diff.

    Heuristics (documented so they are defensible and testable):
      - blue/red_achieved: that side's total faction score rose this turn.
      - escalation_occurred: any casualties, OR a unit broke (will_to_fight -> Broken),
        OR a unit lost command-and-control (c2 -> Lost).
      - key_objective_captured: at least one terrain control change occurred.
    """
    result = result or {}
    blue_before, red_before = _side_score_totals(prev_state, side_map)
    blue_after, red_after = _side_score_totals(new_state, side_map)

    escalation = (
        bool(result.get("casualties"))
        or any((c or {}).get("to") == "Broken" for c in result.get("will_to_fight_changes", []) or [])
        or any((c or {}).get("to") == "Lost" for c in result.get("c2_changes", []) or [])
    )

    return {
        "blue_achieved": blue_after > blue_before,
        "red_achieved": red_after > red_before,
        "escalation_occurred": escalation,
        "key_objective_captured": len(result.get("terrain_changes", []) or []) > 0,
    }


def _side_score_totals(state: dict, side_map: dict):
    """(blue_total, red_total) summing faction_scores[].score by side."""
    blue = red = 0.0
    for fs in (state or {}).get("faction_scores", []) or []:
        if not isinstance(fs, dict):
            continue
        side = side_map.get(fs.get("faction_id"))
        score = fs.get("score", 0) or 0
        if side == "Blue":
            blue += score
        elif side == "Red":
            red += score
    return blue, red


def calibration_rating(mean_forecast: float, mean_outcome: float) -> str:
    """Calibration-in-the-large label from the gap between mean forecast and mean outcome.

    A positive gap (predicted more than happened) reads as overconfident; a negative
    gap as underconfident; within tolerance as well-calibrated.
    """
    err = mean_forecast - mean_outcome
    if err > _CALIBRATION_TOLERANCE:
        return "Overconfident"
    if err < -_CALIBRATION_TOLERANCE:
        return "Underconfident"
    return "Well-calibrated"


def _get(row, field):
    """Read a field from an ORM row or a plain dict."""
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def build_forecasting_summary(forecast_rows: list, total_turns=None) -> dict:
    """Assemble the forecasting-summary payload from TurnForecast rows (ORM or dict).

    Only resolved forecasts contribute to the Brier average and calibration; unresolved
    ones still appear in the turn-by-turn list (with null outcomes) so a forecast made
    for the current, not-yet-adjudicated turn is visible.
    """
    rows = list(forecast_rows or [])
    rows.sort(key=lambda r: (_get(r, "turn_number") or 0))

    turn_by_turn = []
    resolved_briers = []
    forecast_probs = []   # every (p, outcome) pair across resolved forecasts
    outcome_truths = []
    for r in rows:
        brier = _get(r, "brier_score")
        turn_by_turn.append({
            "turn_num": _get(r, "turn_number"),
            "p_blue_wins": _get(r, "p_blue_wins"),
            "blue_achieved": _get(r, "blue_achieved"),
            "p_red_wins": _get(r, "p_red_wins"),
            "red_achieved": _get(r, "red_achieved"),
            "p_escalation": _get(r, "p_escalation"),
            "escalation_occurred": _get(r, "escalation_occurred"),
            "p_key_objective_captured": _get(r, "p_key_objective_captured"),
            "key_objective_captured": _get(r, "key_objective_captured"),
            "brier_score": brier,
            "rationale": _get(r, "rationale"),
        })
        if brier is not None:
            resolved_briers.append(brier)
            for p_field, o_field in QUESTIONS.items():
                forecast_probs.append(_clamp01(_get(r, p_field)))
                outcome_truths.append(1.0 if bool(_get(r, o_field)) else 0.0)

    avg_brier = round(sum(resolved_briers) / len(resolved_briers), 4) if resolved_briers else None
    if forecast_probs:
        mean_forecast = sum(forecast_probs) / len(forecast_probs)
        mean_outcome = sum(outcome_truths) / len(outcome_truths)
        rating = calibration_rating(mean_forecast, mean_outcome)
    else:
        rating = "Insufficient data"

    return {
        "total_turns": total_turns if total_turns is not None else len(rows),
        "forecasts_submitted": len(rows),
        "forecasts_resolved": len(resolved_briers),
        "average_brier_score": avg_brier,
        "calibration_rating": rating,
        "brier_note": BRIER_NOTE,
        "turn_by_turn": turn_by_turn,
    }


# Human-readable label for each forecast question, used in the briefing accuracy block.
QUESTION_LABELS = {
    "p_blue_wins": "Blue achieves objectives",
    "p_red_wins": "Red achieves objectives",
    "p_escalation": "Escalatory action occurs",
    "p_key_objective_captured": "Key terrain changes hands",
}

METHODOLOGY_NOTE = (
    "Brier scores measure probabilistic calibration (0=perfect, 2=worst). "
    "A score below 0.25 indicates good calibration."
)

# Below this overall Brier, calibration reads as "good" (matches METHODOLOGY_NOTE).
_GOOD_CALIBRATION_BRIER = 0.25
# A single question's Brier component this high means |estimate - outcome| >= 0.5,
# i.e. the forecaster was confidently wrong — worth surfacing as a misprediction.
_NOTABLE_COMPONENT_THRESHOLD = 0.5
_MAX_NOTABLE = 5


def _calibration_summary(rating: str, overall_brier: float) -> str:
    """One-line plain-language calibration verdict for the briefing."""
    quality = "good calibration" if overall_brier < _GOOD_CALIBRATION_BRIER else "room for improvement"
    base = f"{rating} (overall Brier {overall_brier:.3f} — {quality})."
    tail = {
        "Well-calibrated": " Stated probabilities tracked actual outcomes closely.",
        "Overconfident": " Estimates ran higher than events warranted — temper confidence when evidence is thin.",
        "Underconfident": " Estimates hedged below what outcomes warranted — commit harder when evidence is strong.",
    }.get(rating, "")
    return base + tail


def build_forecasting_accuracy(forecast_rows: list) -> dict | None:
    """Richer forecasting-accuracy block for the briefing export.

    Returns None when no forecast has been resolved yet (so a session with forecasting
    enabled but no adjudicated turns simply omits the section). Shape:
        overall_brier_score, calibration_summary, notable_mispredictions[],
        methodology_note, turn_calibration[]  (turn_calibration drives the PDF chart).
    """
    resolved = [r for r in (forecast_rows or []) if _get(r, "brier_score") is not None]
    if not resolved:
        return None
    resolved.sort(key=lambda r: (_get(r, "turn_number") or 0))

    briers = [_get(r, "brier_score") for r in resolved]
    overall = round(sum(briers) / len(briers), 4)

    all_p, all_o = [], []
    components = []        # every question, for notable-misprediction selection
    turn_calibration = []  # per-turn estimate-vs-outcome aggregate, for the chart
    for r in resolved:
        turn = _get(r, "turn_number")
        t_p, t_o = [], []
        for p_field, o_field in QUESTIONS.items():
            p = _clamp01(_get(r, p_field))
            o = 1.0 if bool(_get(r, o_field)) else 0.0
            all_p.append(p); all_o.append(o)
            t_p.append(p); t_o.append(o)
            components.append({
                "turn_num": turn,
                "question": QUESTION_LABELS[p_field],
                "estimate": round(p, 2),
                "outcome": bool(o),
                "brier_component": round(2.0 * (p - o) ** 2, 4),
            })
        turn_calibration.append({
            "turn_num": turn,
            "mean_estimate": round(sum(t_p) / len(t_p), 3),
            "actual_rate": round(sum(t_o) / len(t_o), 3),
            "brier_score": _get(r, "brier_score"),
        })

    rating = calibration_rating(sum(all_p) / len(all_p), sum(all_o) / len(all_o))
    notable = sorted(
        (c for c in components if c["brier_component"] >= _NOTABLE_COMPONENT_THRESHOLD),
        key=lambda c: c["brier_component"], reverse=True,
    )[:_MAX_NOTABLE]

    return {
        "overall_brier_score": overall,
        "calibration_summary": _calibration_summary(rating, overall),
        "notable_mispredictions": notable,
        "methodology_note": METHODOLOGY_NOTE,
        "turn_calibration": turn_calibration,
    }
