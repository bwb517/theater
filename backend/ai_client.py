"""
THEATER AI Client
All Anthropic Claude integrations: scenario generation, red team engine,
Monte Carlo simulation, adjudication, and AAR generation.
"""
from __future__ import annotations
import json
import logging
import asyncio
import re
from html.parser import HTMLParser
import anthropic
from database import settings, SessionLocal
import models as _models
import pricing

logger = logging.getLogger(__name__)

def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

def _response_text(response) -> str:
    """Safely extract text from an Anthropic API response."""
    if not response.content:
        raise ValueError("AI model returned an empty response (no content blocks).")
    block = response.content[0]
    text = getattr(block, "text", None)
    if text is None:
        raise ValueError(f"AI model returned unexpected content block type: {getattr(block, 'type', 'unknown')}")
    if response.stop_reason == "max_tokens":
        logger.warning("AI response was truncated (max_tokens reached). JSON may be incomplete.")
    return text

def _log_tokens(
    function_name: str,
    usage,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    model: str | None = None,
) -> None:
    """Persist a single Claude call's token usage + computed USD cost.

    Best-effort: any failure here is swallowed so a logging problem can never
    break the actual AI request. `model` defaults to the configured CLAUDE_MODEL,
    which is also what determines the per-token pricing.
    """
    db = None
    try:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        claude_model = model or settings.claude_model

        db = SessionLocal()
        record = _models.TokenUsage(
            function_name=function_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            user_id=user_id,
            session_id=session_id,
            claude_model=claude_model,
            total_cost_usd=pricing.compute_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_write,
                cache_read_tokens=cache_read,
                model=claude_model,
            ),
        )
        db.add(record)
        db.commit()
    except Exception:
        logger.exception("Failed to log token usage for %s", function_name)
    finally:
        if db is not None:
            db.close()

def extract_json(text: str) -> dict | list:
    """Extract JSON from Claude response, handling markdown code blocks and preamble text."""
    if not text or not text.strip():
        raise ValueError("AI model returned an empty response. The request may have been too large or the model is temporarily unavailable.")

    original = text
    text = text.strip()

    # 1. Try closed markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Try unclosed markdown code block (response truncated before closing ```)
    match = re.search(r"```(?:json)?\s*([\s\S]+)", text)
    if match:
        inner = match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            # Still useful — the inner text will be tried again in step 3 below
            text = inner if '{' in inner or '[' in inner else text

    # 3. Try parsing the whole stripped text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 5. Find the first { or [ and last } or ] — handles preamble/postamble text
    obj_start = text.find('{')
    arr_start = text.find('[')

    if obj_start == -1 and arr_start == -1:
        logger.error("No JSON found in AI response. First 500 chars: %s", original[:500])
        raise ValueError(f"AI response contained no JSON object or array. Response preview: {original[:200]}")

    candidates = []
    if obj_start != -1:
        end = text.rfind('}')
        if end > obj_start:
            candidates.append(text[obj_start:end + 1])
    if arr_start != -1:
        end = text.rfind(']')
        if end > arr_start:
            candidates.append(text[arr_start:end + 1])

    # Try longest candidate first (most likely the complete JSON)
    for candidate in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    logger.error("Could not parse JSON from AI response. First 500 chars: %s", original[:500])
    raise ValueError(
        "AI response was truncated before the JSON was complete. "
        "Try a simpler scenario description to reduce output size. "
        f"Response preview: {original[:200]}"
    )

def _verbosity_instruction(level: int) -> str:
    if level == 1:
        return (
            "\n\nVERBOSITY: TERSE. Keep every narrative/prose field to 1-2 sentences maximum. "
            "No padding, no flavor text, no historical tangents. JSON structure is unchanged — "
            "only shorten string values."
        )
    if level == 3:
        return (
            "\n\nVERBOSITY: VERBOSE. Expand all narrative and prose fields with rich detail, "
            "historical analogues, and analytical depth. Multi-paragraph responses are welcome."
        )
    return ""  # level 2 = normal, no instruction needed

def _slim_game_state(game_state: dict) -> dict:
    """Return a reduced game state with only the fields needed for AI move generation."""
    slim_units = []
    for unit in game_state.get("unit_status", []):
        slim_units.append({
            "unit_id": unit.get("unit_id"),
            "name": unit.get("name"),
            "strength": unit.get("strength"),
            "position": unit.get("position"),
            "status": unit.get("status"),
            "faction_id": unit.get("faction_id"),
            "supply": unit.get("supply"),
            "will_to_fight": unit.get("will_to_fight"),
            "c2_status": unit.get("c2_status"),
        })
    return {
        "unit_status": slim_units,
        "faction_scores": game_state.get("faction_scores", []),
    }

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1: SCENARIO GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_SYSTEM = """You are a professional military scenario designer with 20+ years of wargaming experience across NATO, Joint, and interagency exercises. Your scenarios are used by defense contractors, think tanks, and military education institutions.

Generate complete, realistic, and playable wargaming scenarios in JSON. Return ONLY valid JSON — no markdown, no explanations outside the JSON structure.

SCENARIO TYPES:
- Tactical: Brigade and below, hours to days, kinetic focus
- Operational: Division to Corps, days to weeks, combined arms
- Strategic: Theater-level, weeks to months, political-military
- Gray-Zone: Below threshold of armed conflict, hybrid/information operations

UNIT ECHELONS: Squad → Platoon → Company → Battalion → Brigade → Division → Corps → Army

FACTION SIDES: Blue (friendly/Western), Red (adversary), Green (third party/local), White (neutral/civilian)

AI PERSONALITIES:
- Aggressive: Offensive bias, accepts casualties for decisive results, exploits any gap
- Cautious: Force preservation priority, requires 3:1 odds before attacking, delays under uncertainty
- Opportunistic: Flexible objectives, rapidly exploits success, changes axis of advance when advantageous
- Deceptive: Information operations focus, feints, EMCON, uses decoys and concealment
- Attrition-focused: Trades space for time, fires-dominant, avoids decisiveness, exhausts enemy"""

SCENARIO_SCHEMA = """{
  "title": "string",
  "classification": "UNCLASSIFIED",
  "scenario_type": "Tactical|Operational|Strategic|Gray-Zone",
  "timeframe": "string (e.g., '72 hours, March 2026')",
  "geography": {
    "region": "string",
    "key_terrain": ["string"],
    "chokepoints": ["string"],
    "strategic_locations": ["string"]
  },
  "situation": {
    "background": "string (2-3 paragraphs geopolitical context)",
    "precipitating_event": "string",
    "current_situation": "string",
    "planning_assumptions": {
      "allied_involvement": {
        "enabled": false,
        "allies": [
          {
            "nation": "string",
            "commitment_level": "Full|Partial|Symbolic",
            "arrival_turn": 0,
            "arrival_description": "string (e.g., 'Polish 16th Mech Div crosses H+48')",
            "forces_description": "string (e.g., '1x Armored Brigade, 1x Artillery Regt')",
            "conditions_for_entry": "string (e.g., 'NATO Article 5 invoked')"
          }
        ]
      },
      "rules_of_engagement": "Permissive|Standard|Restrictive|Escalation-Limited",
      "political_constraints": "string (e.g., 'No strikes on Russian territory')",
      "intelligence_quality": "Excellent|Good|Adequate|Poor|Denied",
      "weather_conditions": "Clear|Degraded|Severe",
      "logistics_posture": "Robust|Adequate|Strained|Critical",
      "time_pressure": "None|Moderate|Extreme",
      "escalation_ceiling": "Conventional-only|Theater-nuclear-threshold|Full-spectrum",
      "reinforcement_policy": "Freely reinforceable|Limited reinforcement|No reinforcement",
      "designer_notes": "string (intent, historical context, adjudicator guidance)"
    }
  },
  "factions": [
    {
      "faction_id": "BLUE-01",
      "name": "string",
      "side": "Blue|Red|Green|White",
      "role": "Player|AI-controlled|Neutral",
      "objective_primary": "string",
      "objective_secondary": "string",
      "constraints": "string (ROE, political limits)",
      "victory_conditions": [
        {"condition": "string", "weight_pct": 40}
      ],
      "order_of_battle": {
        "units": [
          {
            "unit_id": "string",
            "name": "string",
            "type": "string (Infantry|Armor|Artillery|Aviation|Air Defense|Logistics|SF|Cyber|Naval|EW)",
            "echelon": "string",
            "parent_unit": "string or null",
            "strength": "Full|Degraded|Critical",
            "location": {"lat": 0.0, "lng": 0.0, "grid_reference": "string"},
            "capabilities": ["string"],
            "limitations": ["string"]
          }
        ],
        "enablers": ["string"],
        "logistics_state": "Robust|Adequate|Strained|Critical"
      },
      "starting_posture": "Offensive|Defensive|Economy of Force|Shaping|Ambiguous",
      "ai_personality": "Aggressive|Cautious|Opportunistic|Deceptive|Attrition-focused"
    }
  ],
  "injects": [
    {
      "inject_id": "INJ-01",
      "turn_trigger": 2,
      "condition_trigger": "string or null",
      "description": "string",
      "type": "Event|Intel|Friction|Decision",
      "affected_factions": ["faction_id"]
    }
  ],
  "win_conditions": {
    "duration_turns": 8,
    "adjudication_method": "Points|Objective-based|Narrative",
    "scoring_dimensions": [
      {"dimension": "string", "weight_pct": 30}
    ]
  },
  "ai_notes": "string (Claude analysis: key dynamics, historical analogues, likely friction points, designer intent)"
}"""

async def generate_scenario(
    user_prompt: str,
    verbosity: int = 2,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    client = get_client()
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=64000,
        system=[
            {"type": "text", "text": SCENARIO_SYSTEM, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"\nOUTPUT SCHEMA (return exactly this structure):\n{SCENARIO_SCHEMA}", "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{
            "role": "user",
            "content": f"""Generate a complete wargaming scenario for: {user_prompt}

Requirements:
- Include 2-4 factions appropriate to the scenario
- Populate all units with realistic coordinates (latitude/longitude) for the region
- Create 3-5 injects that introduce friction and decision points
- Make victory conditions specific and measurable
- AI notes should include at least one real historical analogue
- Ensure unit positions reflect realistic starting postures
- Red/adversary factions should have 'AI-controlled' role by default

Return ONLY the JSON object, nothing else.{_verbosity_instruction(verbosity)}"""
        }]
    )
    _log_tokens("generate_scenario", response.usage, user_id=user_id, session_id=session_id)
    return extract_json(_response_text(response))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2: RED TEAM ENGINE
# ─────────────────────────────────────────────────────────────────────────────

RED_TEAM_SYSTEM = """You are the AI commander for an AI-controlled faction in a professional wargaming exercise. Your specific faction identity and personality are provided in the turn briefing below — adopt them fully.

PERSONALITY GUIDANCE:
- Aggressive: Accept 30%+ casualties for decisive results. Always look for offensive opportunities. Strike when the enemy is off-balance.
- Cautious: Require favorable odds. Preserve force strength. Use fires before maneuver. Delay if uncertain.
- Opportunistic: Exploit any gap or weakness immediately. Change objectives dynamically based on enemy reactions. Surprise and tempo are primary tools.
- Deceptive: Use feints, decoys, and information operations to create false impressions. Conceal main effort until committed. Mask logistics and C2.
- Attrition-focused: Trade space for time. Use fires and obstacles. Avoid decisive engagements unless at favorable odds. Exhaust the enemy.

COMMANDER'S RESPONSIBILITIES:
1. Assess intelligence about enemy dispositions and intent
2. Develop 3 courses of action (COAs) reflecting your personality
3. Select the best COA with tactical reasoning
4. Issue specific, concrete orders organized by warfighting function
5. State commander's intent for next 2-3 turns
6. Describe any deception operations underway

Return ONLY valid JSON matching the schema provided."""

RED_TEAM_SCHEMA = """{
  "turn_number": 0,
  "faction_id": "string",
  "intelligence_assessment": "string (what you know/assess about enemy dispositions, intent, capabilities)",
  "coa_development": [
    {
      "coa_name": "string",
      "description": "string",
      "risk": "Low|Medium|High",
      "pros": ["string"],
      "cons": ["string"]
    }
  ],
  "selected_coa": {
    "name": "string",
    "rationale": "string",
    "risk": "Low|Medium|High",
    "actions": {
      "maneuver": [
        {"unit_id": "string", "action": "string", "from_location": "string", "to_location": "string", "rationale": "string"}
      ],
      "fires": [
        {"target": "string", "system": "string", "effect": "string", "rationale": "string"}
      ],
      "intelligence": [
        {"collection_task": "string", "asset": "string", "rationale": "string"}
      ],
      "logistics": [
        {"action": "string", "priority": "string", "rationale": "string"}
      ],
      "c2": [
        {"action": "string", "rationale": "string"}
      ],
      "information_ops": [
        {"action": "string", "target_audience": "string", "rationale": "string"}
      ]
    }
  },
  "commanders_intent": "string (what you are trying to achieve over the next 2-3 turns)",
  "deception_plan": "string (indicators you are generating to confuse the enemy)",
  "logistics_assessment": "string (fuel, ammunition, maintenance status)",
  "risk_assessment": "string (what could go wrong with your plan)"
}"""

async def generate_red_team_moves(
    scenario: dict,
    faction: dict,
    game_state: dict,
    player_moves: list,
    turn_history: list,
    current_turn: int,
    injects: list,
    verbosity: int = 2,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    client = get_client()
    personality = faction.get("ai_personality", "Opportunistic")

    # Keep the system prompt static so it caches across factions/personalities.
    # The faction identity + personality go in the dynamic turn briefing below.
    system = RED_TEAM_SYSTEM

    planning_assumptions = scenario.get("situation", {}).get("planning_assumptions", {})
    pa_context = f"\nPLANNING ASSUMPTIONS (respect these constraints in all actions):\n{json.dumps(planning_assumptions, indent=2)}\n" if planning_assumptions else ""

    slim_gs = _slim_game_state(game_state)
    slim_history = [
        {"turn": t.get("turn_number"), "events": t.get("key_events", [])}
        for t in (turn_history[-5:] if turn_history else [])
    ]

    context = f"""YOU ARE: {faction.get('name')} ({faction.get('faction_id')})
YOUR PERSONALITY: {personality} — apply the matching guidance from your system instructions.

SCENARIO: {scenario.get('title')}
TIMEFRAME: {scenario.get('timeframe')}
GEOGRAPHY: {json.dumps(scenario.get('geography', {}), indent=2)}
{pa_context}
YOUR FACTION: {json.dumps(faction, indent=2)}

CURRENT GAME STATE:
Turn: {current_turn}
Unit Status (includes supply, will_to_fight, c2_status — factor these into your decisions):
{json.dumps(slim_gs.get('unit_status', []), indent=2)}
Faction Scores: {json.dumps(slim_gs.get('faction_scores', []), indent=2)}

SUPPLY AWARENESS: Do not assign fires to units with ammo < 20 or munitions.count == 0. Do not assign maneuver to units with fuel < 20.
WILL-TO-FIGHT AWARENESS: Broken WTF units cannot execute offensive maneuver — assign them Hold or Withdraw only.
C2 AWARENESS: Units with c2_status Lost will act on last turn's orders regardless of new orders assigned.

BLUE FORCE ACTIONS THIS TURN:
{json.dumps(player_moves, indent=2)}

RECENT TURN HISTORY (last 5 turns, key events only):
{json.dumps(slim_history, indent=2)}

INJECTS TRIGGERED THIS TURN:
{json.dumps(injects, indent=2)}

Analyze the situation and generate your faction's moves for Turn {current_turn}. Be specific — name actual units, actual locations, actual effects sought. Return JSON matching the OUTPUT SCHEMA in your system instructions. Return ONLY JSON.{_verbosity_instruction(verbosity)}"""

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=32000,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"OUTPUT SCHEMA:\n{RED_TEAM_SCHEMA}", "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": context}]
    )
    _log_tokens("generate_red_team_moves", response.usage, user_id=user_id, session_id=session_id)
    result = extract_json(response.content[0].text)
    result["turn_number"] = current_turn
    result["faction_id"] = faction["faction_id"]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# ADJUDICATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

ADJUDICATION_SYSTEM = """You are a neutral wargame adjudicator for a professional military exercise. Your role is to determine what ACTUALLY HAPPENED when all factions executed their moves this turn.

Apply realistic military principles:
- Friction, fog of war, and Murphy's Law affect all operations
- Superior fires and C2 provide significant advantages
- Logistics failures cascade; ignore them and units culminate
- Electronic warfare degrades communications and targeting
- Weather, terrain, and time-of-day affect all operations
- Casualties should be realistic — 10-30% per engagement, not 90%
- Defenders have significant advantages in prepared positions

SUPPLY & MUNITIONS RULES:
- Fires deplete ammo; maneuver depletes fuel; heavy use degrades maintenance. Reflect this in supply_changes.
- Air Defense and missile/rocket units (HIMARS, MLRS, Patriot, etc.) have discrete munitions counts — decrement these when they engage (munitions_delta is negative).
- Logistics orders targeted at a specific unit_id replenish that unit's supply (ammo_delta/fuel_delta positive).
- Units with ammo < 20 should not be shown executing fires orders effectively.

WILL-TO-FIGHT RULES:
- A unit driven to Critical strength loses one WTF tier (High→Moderate, Moderate→Low, Low→Broken).
- Successful enemy Information Operations against a faction lower WTF for targeted units.
- Friendly successful objectives, allied arrivals, or resupply events can raise WTF one tier.
- Broken units: cannot execute offensive orders (Attack, Assault). They hold or withdraw only. Describe this in the narrative.

C2 DISRUPTION RULES:
- EW orders against an enemy HQ or command unit degrade that unit's c2_status (Nominal→Degraded).
- Fires directly on a command post can also degrade C2.
- C2 Degraded: approximately 50% chance orders for that unit are not transmitted this turn — describe the outcome probabilistically in the narrative.
- C2 Lost: the unit acts only on its last turn's orders; ignore any new orders submitted for it this turn.
- C2 can recover one tier per turn if not actively attacked (Degraded→Nominal).

FOG OF WAR RULES:
- ISR, SIGINT, HUMINT intelligence orders reveal enemy units. Add those unit_ids to detection_updates.
- Combat contact (when units engage each other) also reveals unit positions.
- Units not detected remain hidden from the opposing faction.

Return structured JSON with a narrative and quantified state changes."""

ADJUDICATION_OUTPUT_SCHEMA = """{
  "turn_number": 0,
  "narrative": "string (3-5 paragraph narrative of what happened this turn, written like an operations report)",
  "decisive_moment": "string (the single most important event this turn)",
  "casualties": [
    {"faction_id": "string", "unit_id": "string", "strength_change": "Full→Degraded", "cause": "string", "manning_change": -15}
  ],
  "position_updates": [
    {"unit_id": "string", "new_lat": 0.0, "new_lng": 0.0}
  ],
  "terrain_changes": [
    {"location": "string", "from_faction": "string", "to_faction": "string"}
  ],
  "score_changes": [
    {"faction_id": "string", "dimension": "string", "change": 0, "rationale": "string"}
  ],
  "intelligence_gained": [
    {"faction_id": "string", "intel_item": "string"}
  ],
  "logistics_impacts": [
    {"faction_id": "string", "impact": "string"}
  ],
  "key_events": ["string"],
  "next_turn_conditions": "string (what the situation looks like at start of next turn)",
  "supply_changes": [
    {"unit_id": "string", "ammo_delta": 0, "fuel_delta": 0, "maintenance_delta": 0, "munitions_delta": 0, "reason": "string"}
  ],
  "will_to_fight_changes": [
    {"unit_id": "string", "from": "High|Moderate|Low|Broken", "to": "High|Moderate|Low|Broken", "reason": "string"}
  ],
  "c2_changes": [
    {"unit_id": "string", "from": "Nominal|Degraded|Lost", "to": "Nominal|Degraded|Lost", "cause": "string"}
  ],
  "detection_updates": [
    {"detected_unit_id": "string", "detected_by_faction_id": "string"}
  ]
}"""

async def adjudicate_turn(
    scenario: dict,
    blue_moves: list,
    red_moves: list,
    current_game_state: dict,
    turn_number: int,
    verbosity: int = 2,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    client = get_client()
    planning_assumptions = scenario.get("situation", {}).get("planning_assumptions", {})
    pa_section = f"\nPLANNING ASSUMPTIONS (apply these constraints when adjudicating):\n{json.dumps(planning_assumptions, indent=2)}\n" if planning_assumptions else ""
    slim_gs = _slim_game_state(current_game_state)

    prompt = f"""ADJUDICATION REQUEST — Turn {turn_number}

SCENARIO: {scenario.get('title')} | {scenario.get('scenario_type')}
{pa_section}
BLUE FORCE ACTIONS:
{json.dumps(blue_moves, indent=2)}

RED FORCE ACTIONS:
{json.dumps(red_moves, indent=2)}

CURRENT GAME STATE (includes supply, will_to_fight, c2_status per unit):
{json.dumps(slim_gs, indent=2)}

Adjudicate this turn. Set "turn_number" to {turn_number}. Return JSON matching the OUTPUT SCHEMA in your system instructions. All arrays are required — use empty arrays if nothing applies. Return ONLY JSON.{_verbosity_instruction(verbosity)}"""

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=8000,
        system=[
            {"type": "text", "text": ADJUDICATION_SYSTEM, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"OUTPUT SCHEMA:\n{ADJUDICATION_OUTPUT_SCHEMA}", "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": prompt}]
    )
    _log_tokens("adjudicate_turn", response.usage, user_id=user_id, session_id=session_id)
    return extract_json(_response_text(response))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3: MONTE CARLO ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

MONTE_CARLO_SYSTEM = """You are a strategic analyst running rapid scenario simulations for wargame probability analysis. Your role: generate multiple abbreviated simulation runs to identify likely outcomes, key decision points, and risk factors.

Each simulation run should vary key assumptions (weather, intelligence quality, political constraints, logistics performance, friction events, leadership decisions) to explore the outcome space.

Think like a red team analyst who has run this scenario dozens of times and is synthesizing patterns."""

MONTE_CARLO_SCHEMA = """{
  "simulation_runs": [
    {
      "run_id": 1,
      "assumptions": {
        "weather": "string",
        "intelligence_quality": "string",
        "logistics": "string",
        "political_constraints": "string",
        "friction_level": "string",
        "other": "string"
      },
      "narrative": "string (3-4 sentences: how scenario plays out, key turning point, outcome)",
      "outcome": {
        "blue_achieves_primary": true,
        "blue_achieves_secondary": false,
        "red_achieves_primary": false,
        "dominant_factor": "string (what factor most determined this outcome)"
      }
    }
  ],
  "aggregate": {
    "outcome_probabilities": [
      {
        "scenario_outcome": "string (e.g., 'Blue holds, Red limited gains')",
        "probability_pct": 35,
        "description": "string"
      }
    ],
    "key_decision_points": [
      {
        "turn": 0,
        "decision": "string",
        "impact_rating": "Critical|High|Medium|Low",
        "appears_in_runs": 0,
        "rationale": "string"
      }
    ],
    "risk_factors": [
      {
        "factor": "string",
        "impact": "High|Medium|Low",
        "frequency": "Common|Occasional|Rare",
        "mitigation": "string"
      }
    ],
    "sensitivity_findings": "string (which assumptions changed outcomes most)",
    "most_likely_narrative": "string (2-3 paragraphs: the most probable way this plays out)",
    "best_case_narrative": "string (2-3 paragraphs: optimistic Blue outcome)",
    "worst_case_narrative": "string (2-3 paragraphs: pessimistic Blue outcome)",
    "analytical_bottom_line": "string (the single most important finding)"
  }
}"""

MONTE_CARLO_LITE_SCHEMA = """{
  "simulation_runs": [
    {
      "run_id": 1,
      "assumptions": {
        "weather": "string",
        "intelligence_quality": "string",
        "logistics": "string",
        "political_constraints": "string",
        "friction_level": "string",
        "other": "string"
      },
      "narrative": "string (3-4 sentences: how scenario plays out, key turning point, outcome)",
      "outcome": {
        "blue_achieves_primary": true,
        "blue_achieves_secondary": false,
        "red_achieves_primary": false,
        "dominant_factor": "string"
      }
    }
  ],
  "aggregate": {
    "key_decision_points": [
      {
        "turn": 0,
        "decision": "string",
        "impact_rating": "Critical|High|Medium|Low",
        "appears_in_runs": 0,
        "rationale": "string"
      }
    ],
    "risk_factors": [
      {
        "factor": "string",
        "impact": "High|Medium|Low",
        "frequency": "Common|Occasional|Rare",
        "mitigation": "string"
      }
    ]
  }
}"""

_MONTE_CARLO_BATCH_SIZE = 5


_PA_SCALAR_KEYS = {
    "rules_of_engagement", "political_constraints", "intelligence_quality",
    "weather_conditions", "logistics_posture", "time_pressure",
    "escalation_ceiling", "reinforcement_policy",
}


def _slim_scenario_for_mc(scenario: dict) -> dict:
    """Return a reduced scenario for Monte Carlo input (drops unit detail arrays and verbose planning fields)."""
    slim_factions = []
    for f in scenario.get("factions", []):
        oob = f.get("order_of_battle", {})
        slim_factions.append({
            "faction_id": f.get("faction_id"),
            "name": f.get("name"),
            "side": f.get("side"),
            "objective_primary": f.get("objective_primary"),
            "objective_secondary": f.get("objective_secondary"),
            "victory_conditions": f.get("victory_conditions"),
            "starting_posture": f.get("starting_posture"),
            "ai_personality": f.get("ai_personality"),
            "order_of_battle": {
                "units": [
                    {
                        "unit_id": u.get("unit_id"),
                        "name": u.get("name"),
                        "type": u.get("type"),
                        "echelon": u.get("echelon"),
                        "strength": u.get("strength"),
                    }
                    for u in oob.get("units", [])
                ],
                "logistics_state": oob.get("logistics_state"),
            },
        })

    # Keep only scalar constraint fields from planning_assumptions;
    # allied_involvement and designer_notes are verbose and not needed for MC variation.
    situation = scenario.get("situation", {})
    pa = situation.get("planning_assumptions", {})
    slim_situation = {k: v for k, v in situation.items() if k != "planning_assumptions"}
    if pa:
        slim_situation["planning_assumptions"] = {k: v for k, v in pa.items() if k in _PA_SCALAR_KEYS}

    return {
        "title": scenario.get("title"),
        "scenario_type": scenario.get("scenario_type"),
        "timeframe": scenario.get("timeframe"),
        "geography": scenario.get("geography"),
        "situation": slim_situation,
        "factions": slim_factions,
        "win_conditions": scenario.get("win_conditions"),
    }


def _merge_monte_carlo_results(batch_results: list) -> dict:
    """Merge results from multiple Monte Carlo batch calls into a single result."""
    all_runs: list = []
    all_decision_points: list = []
    all_risk_factors: list = []
    seen_decisions: set = set()
    seen_risks: set = set()

    for batch in batch_results:
        for run in batch.get("simulation_runs", []):
            run["run_id"] = len(all_runs) + 1
            all_runs.append(run)
        agg = batch.get("aggregate", {})
        for dp in agg.get("key_decision_points", []):
            key = dp.get("decision", "")[:50]
            if key not in seen_decisions:
                seen_decisions.add(key)
                all_decision_points.append(dp)
        for rf in agg.get("risk_factors", []):
            key = rf.get("factor", "")[:50]
            if key not in seen_risks:
                seen_risks.add(key)
                all_risk_factors.append(rf)

    # Derive outcome probabilities from binary run outcomes across all batches
    n = len(all_runs)
    blue_wins = sum(1 for r in all_runs if r.get("outcome", {}).get("blue_achieves_primary"))
    red_wins = sum(1 for r in all_runs if r.get("outcome", {}).get("red_achieves_primary"))
    both = sum(1 for r in all_runs
               if r.get("outcome", {}).get("blue_achieves_primary")
               and r.get("outcome", {}).get("red_achieves_primary"))

    def _pct(count: int) -> int:
        return round(count / n * 100) if n > 0 else 0

    blue_only = blue_wins - both
    red_only = red_wins - both
    stalemate = max(0, n - blue_only - red_only - both)

    raw_outcomes = [
        ("Blue Decisive Victory", blue_only, "Blue achieves primary objective; Red does not"),
        ("Red Decisive Victory", red_only, "Red achieves primary objective; Blue does not"),
        ("Mutual Achievement", both, "Both sides achieve their primary objectives"),
        ("Stalemate / Inconclusive", stalemate, "Neither side achieves primary objective"),
    ]
    outcome_probs = [
        {"scenario_outcome": name, "probability_pct": _pct(count), "description": desc}
        for name, count, desc in raw_outcomes if count > 0
    ]
    # Fix rounding drift so probabilities sum to exactly 100
    if outcome_probs:
        diff = 100 - sum(o["probability_pct"] for o in outcome_probs)
        outcome_probs[0]["probability_pct"] += diff

    # Use first batch's narrative/analytical fields (computed over its own runs)
    first_agg = batch_results[0].get("aggregate", {}) if batch_results else {}

    return {
        "simulation_runs": all_runs,
        "aggregate": {
            "outcome_probabilities": outcome_probs,
            "key_decision_points": all_decision_points[:12],
            "risk_factors": all_risk_factors[:8],
            "sensitivity_findings": first_agg.get("sensitivity_findings", ""),
            "most_likely_narrative": first_agg.get("most_likely_narrative", ""),
            "best_case_narrative": first_agg.get("best_case_narrative", ""),
            "worst_case_narrative": first_agg.get("worst_case_narrative", ""),
            "analytical_bottom_line": first_agg.get("analytical_bottom_line", ""),
        },
    }


async def _run_monte_carlo_batch(
    client,
    scenario: dict,
    state_context: str,
    base_assumptions_text: str,
    batch_size: int,
    run_offset: int,
    verbosity: int,
    is_primary: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Run a single batch of Monte Carlo simulations.

    is_primary=True (batch 0 only): uses the full schema including narrative fields.
    is_primary=False: uses the lite schema — simulation runs + decision points/risk factors only.
    """
    schema = MONTE_CARLO_SCHEMA if is_primary else MONTE_CARLO_LITE_SCHEMA
    aggregate_note = (
        "Ensure probability percentages in the aggregate sum to 100. "
        if is_primary else
        "Omit outcome_probabilities and narrative fields — include only key_decision_points and risk_factors in aggregate. "
    )

    prompt = f"""Run {batch_size} rapid simulations (numbered {run_offset + 1}–{run_offset + batch_size}) of this scenario and return results matching the OUTPUT SCHEMA in your system instructions.

SCENARIO: {json.dumps(scenario, indent=2)}
{state_context}
{base_assumptions_text}
For each simulation, vary one or more of these factors from the baseline above:
- Weather conditions (clear/degraded/severe)
- Intelligence quality (excellent/adequate/poor/deception-degraded)
- Logistics performance (smooth/friction/critical failure)
- Political constraints / ROE (full freedom of action/restricted/highly restricted)
- Allied involvement timing and commitment level
- Blue leadership decisions (aggressive/defensive/risk-averse)
- Friction events (minimal/moderate/severe)

{aggregate_note}Return ONLY JSON.{_verbosity_instruction(verbosity)}"""

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=32000,
        system=[
            {"type": "text", "text": MONTE_CARLO_SYSTEM, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"OUTPUT SCHEMA:\n{schema}", "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": prompt}]
    )
    _log_tokens("run_monte_carlo_batch", response.usage, user_id=user_id, session_id=session_id)
    return extract_json(_response_text(response))


async def run_monte_carlo(
    scenario: dict,
    session_state: dict = None,
    num_runs: int = 10,
    verbosity: int = 2,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    client = get_client()
    slim_scenario = _slim_scenario_for_mc(scenario)

    state_context = ""
    if session_state:
        state_context = f"\nCURRENT MID-GAME STATE:\n{json.dumps(session_state, indent=2)}"

    # Source from slim_scenario so allied_involvement/designer_notes are already excluded
    slim_pa = slim_scenario.get("situation", {}).get("planning_assumptions", {})
    base_assumptions_text = (
        f"\nBASELINE PLANNING ASSUMPTIONS (use these as the starting point — vary them across runs to explore sensitivity):\n{json.dumps(slim_pa, indent=2)}\n"
        if slim_pa else ""
    )

    batch_coros = [
        _run_monte_carlo_batch(
            client,
            slim_scenario,
            state_context,
            base_assumptions_text,
            min(_MONTE_CARLO_BATCH_SIZE, num_runs - offset),
            offset,
            verbosity,
            is_primary=(offset == 0),
            user_id=user_id,
            session_id=session_id,
        )
        for offset in range(0, num_runs, _MONTE_CARLO_BATCH_SIZE)
    ]

    batch_results = await asyncio.gather(*batch_coros)
    return _merge_monte_carlo_results(list(batch_results))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4: AAR GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

AAR_SYSTEM = """You are a professional military analyst writing a formal After Action Review (AAR) for a completed wargaming exercise. This document will be read by senior defense officials, analysts, and planners.

Write with professional military precision. Use active voice. Cite specific turns and events. Lead with findings. Avoid vague language.

Structure the AAR in the sections requested. Be analytical and specific — connect observations to doctrine, historical precedent, and operational implications."""

async def generate_aar(
    scenario: dict,
    turn_logs: list,
    final_state: dict,
    monte_carlo: dict = None,
    gm_notes: str = "",
    verbosity: int = 2,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    client = get_client()

    mc_section = ""
    if monte_carlo:
        mc_section = f"\nMONTE CARLO PRE-GAME ANALYSIS:\n{json.dumps(monte_carlo.get('aggregate', {}), indent=2)}"

    planning_assumptions = scenario.get("situation", {}).get("planning_assumptions", {})
    pa_aar = f"\nPLANNING ASSUMPTIONS USED IN THIS EXERCISE:\n{json.dumps(planning_assumptions, indent=2)}\n" if planning_assumptions else ""

    prompt = f"""Generate a complete After Action Review (AAR) for this wargaming exercise.

SCENARIO: {json.dumps(scenario, indent=2)}
{pa_aar}
COMPLETE TURN LOG:
{json.dumps(turn_logs, indent=2)}

FINAL GAME STATE:
{json.dumps(final_state, indent=2)}

GAME MASTER NOTES:
{gm_notes or "None provided."}
{mc_section}

Return JSON with this EXACT structure:
{{
  "metadata": {{
    "exercise_title": "string",
    "classification": "UNCLASSIFIED",
    "date_generated": "string",
    "scenario_type": "string",
    "duration_turns": 0,
    "participants": ["string"]
  }},
  "section_1_executive_summary": {{
    "scenario_overview": "string (2-3 sentences)",
    "outcome": "string (who achieved what)",
    "key_findings": [
      {{
        "finding_number": 1,
        "finding": "string",
        "confidence": "High|Medium|Low",
        "significance": "Critical|Important|Noteworthy"
      }}
    ],
    "bottom_line_up_front": "string"
  }},
  "section_2_chronological_narrative": {{
    "phase_narratives": [
      {{
        "phase": "string (e.g., 'Phase 1: Initial Contact, Turns 1-2')",
        "narrative": "string (detailed narrative of events in this phase)",
        "decisive_moments": ["string"],
        "turning_point": "string or null"
      }}
    ],
    "overall_flow": "string (how the game evolved from start to finish)"
  }},
  "section_3_blue_force_analysis": {{
    "coa_assessment": "string (was the chosen approach sound?)",
    "execution_quality": "string (where plans met reality)",
    "key_decisions": [
      {{
        "turn": 0,
        "decision": "string",
        "assessment": "Good|Acceptable|Poor",
        "rationale": "string",
        "alternative": "string (what should/could have been done)"
      }}
    ],
    "logistics_sustainment": "string",
    "information_operations": "string",
    "overall_grade": "Excellent|Above Average|Average|Below Average|Poor"
  }},
  "section_4_red_force_analysis": {{
    "strategy_assessment": "string",
    "most_effective_ttps": ["string"],
    "vulnerabilities_exploited": ["string"],
    "missed_opportunities": ["string"],
    "implications_for_real_world": "string"
  }},
  "section_5_lessons_learned": [
    {{
      "lesson_number": 1,
      "warfighting_function": "string (Maneuver|Fires|Intelligence|Logistics|C2|Protection|IO|Joint)",
      "observation": "string (what was observed)",
      "discussion": "string (why it matters, context)",
      "lesson_learned": "string (the specific lesson)",
      "recommendation": "string (actionable recommendation)"
    }}
  ],
  "section_6_implications": {{
    "doctrine_implications": "string",
    "capability_gaps_identified": ["string"],
    "planning_recommendations": ["string"],
    "follow_on_training": ["string"],
    "questions_for_further_study": ["string"]
  }},
  "section_7_appendices": {{
    "order_of_battle_summary": "string",
    "score_summary": [
      {{"faction": "string", "final_score": 0, "objectives_achieved": ["string"]}}
    ],
    "scenario_parameters": {{
      "turns_played": 0,
      "time_per_turn": "string",
      "total_game_time": "string"
    }}
  }}
}}

Return ONLY JSON. Write analytically — this is a professional deliverable.{_verbosity_instruction(verbosity)}"""

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=32000,
        system=[{"type": "text", "text": AAR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}]
    )
    _log_tokens("generate_aar", response.usage, user_id=user_id, session_id=session_id)
    return extract_json(_response_text(response))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5: OOB EXTRACTION FROM TEXT (Wikipedia / paste)
# ─────────────────────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Strip HTML tags, skipping script/style content."""
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self._parts)


def strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


OOB_EXTRACTION_SYSTEM = """You are a military order-of-battle analyst. Given raw text from a webpage (Wikipedia article, news report, think-tank paper, etc.), extract all named military units and organize them into factions.

Rules:
- Assign each faction to a side: Blue (friendly/Western), Red (adversary), Green (third party), White (neutral)
- Use the faction_hints provided to determine which nation/force maps to which side
- Infer unit type from name/context: Infantry, Armor, Artillery, Aviation, Air Defense, Logistics, SF, Cyber, Naval, EW
- Infer echelon from name: Squad, Platoon, Company, Battalion, Brigade, Division, Corps, Army, Fleet
- If coordinates are unknown, use 0.0 for lat/lng and leave grid_reference empty
- List enablers (air support, ISR, enabler units) separately
- Return ONLY valid JSON, nothing else"""

OOB_EXTRACTION_SCHEMA = """{
  "factions": [
    {
      "faction_id": "BLUE-01",
      "name": "string (e.g., 'NATO Combined Arms Force')",
      "side": "Blue|Red|Green|White",
      "role": "Player|AI-controlled|Neutral",
      "order_of_battle": {
        "units": [
          {
            "unit_id": "string (e.g., BLU-1)",
            "name": "string",
            "type": "Infantry|Armor|Artillery|Aviation|Air Defense|Logistics|SF|Cyber|Naval|EW",
            "echelon": "Squad|Platoon|Company|Battalion|Brigade|Division|Corps|Army",
            "parent_unit": "string or null",
            "strength": "Full",
            "location": {"lat": 0.0, "lng": 0.0, "grid_reference": ""},
            "capabilities": ["string"],
            "limitations": ["string"]
          }
        ],
        "enablers": ["string"],
        "logistics_state": "Adequate"
      },
      "starting_posture": "Offensive|Defensive|Economy of Force|Shaping|Ambiguous",
      "ai_personality": "Opportunistic"
    }
  ],
  "suggested_title": "string (e.g., 'Gulf War - Operation Desert Storm')",
  "suggested_timeframe": "string (e.g., 'January–February 1991')",
  "source_notes": "string (brief description of what the source covered)"
}"""


async def extract_oob_from_text(
    page_text: str,
    faction_hints: dict,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Extract an order of battle from raw text (stripped HTML from Wikipedia etc.).

    faction_hints maps side names to nation/force labels, e.g.
    {"Blue": "Coalition", "Red": "Iraq"} so Claude assigns sides correctly.
    """
    client = get_client()
    hints_text = "\n".join(f"  {side}: {label}" for side, label in faction_hints.items())
    prompt = f"""Extract all military units from the following text and organize them into factions.

FACTION SIDE ASSIGNMENTS (use these to assign Blue/Red/Green/White):
{hints_text or '  (not provided — infer from context)'}

SOURCE TEXT:
{page_text[:12000]}

OUTPUT SCHEMA:
{OOB_EXTRACTION_SCHEMA}

Extract every named unit, formation, or force element mentioned. Return ONLY JSON."""

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=8000,
        system=[{"type": "text", "text": OOB_EXTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}]
    )
    _log_tokens("extract_oob_from_text", response.usage, user_id=user_id, session_id=session_id)
    return extract_json(_response_text(response))
