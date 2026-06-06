"""
THEATER Platform — Database Seeder
Run: python seed_data.py
Creates admin user, unit library, 5 scenario templates, demo IRON WOLF session.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
import models
from auth import hash_password
from datetime import datetime


Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        # ── Demo users (opt-in only) ────────────────────────────────────────
        # Default-off: these are well-known credentials documented in the repo.
        # Never seed them on a public/prod deploy. Set SEED_DEMO_USERS=true to enable.
        if os.getenv("SEED_DEMO_USERS", "").lower() in ("1", "true", "yes"):
            if not db.query(models.User).filter_by(username="admin").first():
                db.add(models.User(
                    username="admin", email="admin@theater.local",
                    hashed_password=hash_password("theater123"), role="admin"
                ))
                db.add(models.User(
                    username="gamemaster", email="gm@theater.local",
                    hashed_password=hash_password("theater123"), role="game_master"
                ))
                db.add(models.User(
                    username="player1", email="player1@theater.local",
                    hashed_password=hash_password("theater123"), role="player"
                ))
                db.commit()
                print("✓ Demo users created (SEED_DEMO_USERS enabled)")
        else:
            print("• Skipping demo users (set SEED_DEMO_USERS=true to create them)")

        # ── Unit Library ────────────────────────────────────────────────────
        if db.query(models.UnitTemplate).count() == 0:
            units = [
                # NATO Ground Forces
                {"name":"Armored Brigade Combat Team","type":"Armor","echelon":"Brigade","nation_group":"NATO","capabilities":["Combined arms","Tank-heavy","Organic artillery","Engineer support"],"limitations":["High logistics demand","Limited in urban terrain","Air defense dependent on higher"],"typical_strength":4500},
                {"name":"Infantry Brigade Combat Team","type":"Infantry","echelon":"Brigade","nation_group":"NATO","capabilities":["Dismounted assault","Urban warfare","Air-assault capable","Organic fires"],"limitations":["Limited armor protection","Attrition-sensitive","Logistics-intensive"],"typical_strength":4200},
                {"name":"Stryker Brigade Combat Team","type":"Infantry","echelon":"Brigade","nation_group":"NATO","capabilities":["High mobility","Rapid deployment","Network-enabled","Anti-armor capable"],"limitations":["Limited vs. heavy armor","Wheeled-terrain dependent","Moderate protection"],"typical_strength":4000},
                {"name":"M1A2 Abrams Battalion","type":"Armor","echelon":"Battalion","nation_group":"NATO","capabilities":["Heavy direct fire","Thermal optics","Active protection system","TUSK urban kit"],"limitations":["High fuel consumption","Limited reverse speed","Logistics tail"],"typical_strength":58},
                {"name":"M2 Bradley Battalion","type":"Mechanized Infantry","echelon":"Battalion","nation_group":"NATO","capabilities":["Dismount infantry","25mm autocannon","TOW missiles","Night vision"],"limitations":["Overcrowded crew compartment","Maintenance intensive"],"typical_strength":44},
                {"name":"M109A7 Paladin Battalion","type":"Artillery","echelon":"Battalion","nation_group":"NATO","capabilities":["155mm precision fires","AFATDS integration","Shoot-and-scoot","Excalibur capable"],"limitations":["Resupply intensive","Air defense dependent"],"typical_strength":18},
                {"name":"HIMARS Battery","type":"Artillery","echelon":"Battery","nation_group":"NATO","capabilities":["GMLRS 70km range","ATACMS 300km","Rapid repositioning","Precision strike"],"limitations":["Limited magazine depth","High-value target","Reload time"],"typical_strength":6},
                {"name":"AH-64E Apache Battalion","type":"Aviation","echelon":"Battalion","nation_group":"NATO","capabilities":["Anti-armor","Air-to-air","TADS/PNVS","Hellfire missiles"],"limitations":["Weather dependent","Maintenance intensive","IR signature"],"typical_strength":24},
                {"name":"Patriot Battery","type":"Air Defense","echelon":"Battery","nation_group":"NATO","capabilities":["TBM intercept","Anti-cruise missile","Long range","Multi-target"],"limitations":["Fixed site","Limited vs. saturation","Logistics"],"typical_strength":8},
                {"name":"Combat Engineer Battalion","type":"Engineers","echelon":"Battalion","nation_group":"NATO","capabilities":["Obstacle breaching","Bridge laying","Demolition","Counter-mobility"],"limitations":["Slow in contact","Heavy equipment dependent"],"typical_strength":500},
                {"name":"Special Forces ODA","type":"SF","echelon":"Team","nation_group":"NATO","capabilities":["UW","Direct action","JTAC","HUMINT","Partner force training"],"limitations":["Small numbers","Limited sustainment","Non-standard equipment"],"typical_strength":12},
                {"name":"F-35A Squadron","type":"Air","echelon":"Squadron","nation_group":"NATO","capabilities":["Stealth","Multi-role","Sensor fusion","EW","SEAD"],"limitations":["High maintenance","Limited payload vs. F-15","Sortie rate"],"typical_strength":24},
                {"name":"E-3 Sentry AWACS","type":"Air","echelon":"Aircraft","nation_group":"NATO","capabilities":["360° radar","Battle management","Datalink","Long endurance"],"limitations":["High-value target","Limited self-defense"],"typical_strength":1},
                {"name":"Logistics Brigade","type":"Logistics","echelon":"Brigade","nation_group":"NATO","capabilities":["Class I-IX","Field maintenance","Medical","Transportation"],"limitations":["Vulnerable to interdiction","Slow movement"],"typical_strength":2000},
                # Russian Ground Forces
                {"name":"Combined Arms Army","type":"Combined Arms","echelon":"Army","nation_group":"Russia","capabilities":["Multi-domain operations","Organic air defense","EW integration","Long-range fires"],"limitations":["C2 centralized","Logistics fragile","NCO corps weak"],"typical_strength":45000},
                {"name":"Tank Regiment","type":"Armor","echelon":"Regiment","nation_group":"Russia","capabilities":["T-80BVM tanks","ERA protection","Reactive armor","Thermal sights"],"limitations":["Limited night ops","Maintenance-intensive","Crew quality variable"],"typical_strength":93},
                {"name":"Motor Rifle Battalion (BTG)","type":"Mechanized Infantry","echelon":"Battalion","nation_group":"Russia","capabilities":["BMP-3 IFVs","Organic artillery","AD assets","EW support"],"limitations":["Junior leader quality","C2 fragile","Logistics poor"],"typical_strength":800},
                {"name":"9M727 Iskander-M Battery","type":"Artillery","echelon":"Battery","nation_group":"Russia","capabilities":["500km range","Maneuvering warhead","Nuclear-capable","Precision strike"],"limitations":["Limited magazine","High-value target","Reload time long"],"typical_strength":6},
                {"name":"BM-21 Grad Battalion","type":"Artillery","echelon":"Battalion","nation_group":"Russia","capabilities":["Area saturation","Rapid fire","Mobility","Multiple warhead types"],"limitations":["Inaccurate","Large signature","Reload time"],"typical_strength":18},
                {"name":"S-400 Battalion","type":"Air Defense","echelon":"Battalion","nation_group":"Russia","capabilities":["400km range","Anti-stealth","Multi-target","ABM capable"],"limitations":["Fixed deployment slow","Logistics","EW vulnerable"],"typical_strength":8},
                {"name":"Electronic Warfare Battalion","type":"EW","echelon":"Battalion","nation_group":"Russia","capabilities":["GPS jamming","Comms jamming","Radar spoofing","Drone defeat"],"limitations":["Signature heavy","Fixed site preferred","Affects own forces"],"typical_strength":400},
                {"name":"Spetsnaz Company","type":"SF","echelon":"Company","nation_group":"Russia","capabilities":["Sabotage","Assassination","Recon","Partisan support","CBRN"],"limitations":["Small numbers","Limited logistics","Deniability constraints"],"typical_strength":90},
                {"name":"Su-57 Squadron","type":"Air","echelon":"Squadron","nation_group":"Russia","capabilities":["Stealth capable","BVR missiles","Supercruise","EW systems"],"limitations":["Limited numbers","Maintenance issues","Avionics immature"],"typical_strength":12},
                {"name":"Ka-52 Attack Helicopter Squadron","type":"Aviation","echelon":"Squadron","nation_group":"Russia","capabilities":["Anti-armor","Night capable","Cannon/missile","Recon"],"limitations":["Maintenance","Crew quality","Weather dependent"],"typical_strength":12},
                # Chinese Forces
                {"name":"PLA Group Army","type":"Combined Arms","echelon":"Army","nation_group":"China","capabilities":["Multi-domain","Long-range fires","EW integration","Anti-access"],"limitations":["Limited combat experience","Logistics challenged","C2 learning"],"typical_strength":40000},
                {"name":"Type 99A Tank Battalion","type":"Armor","echelon":"Battalion","nation_group":"China","capabilities":["APS system","ERA","Thermal sights","NBC protection"],"limitations":["Limited exports","Training quality","Maintenance"],"typical_strength":40},
                {"name":"DF-26 IRBM Brigade","type":"Missile","echelon":"Brigade","nation_group":"China","capabilities":["4000km range","Anti-ship variant","Nuclear-capable","Precision"],"limitations":["High-value target","Fixed silos","Limited reload"],"typical_strength":16},
                {"name":"J-20 Stealth Squadron","type":"Air","echelon":"Squadron","nation_group":"China","capabilities":["Stealth","Long-range intercept","Advanced avionics","IRST"],"limitations":["Engine reliability","Limited exports","Training"],"typical_strength":16},
                {"name":"PLAN Surface Action Group","type":"Naval","echelon":"Group","nation_group":"China","capabilities":["Type 055 destroyer","YJ-18 ASMs","Long-range SAM","ASW"],"limitations":["Limited deep-water experience","Logistics at range","Blue-water ASW"],"typical_strength":4},
                # IRGC/Iran
                {"name":"IRGC Quds Force Brigade","type":"SF","echelon":"Brigade","nation_group":"Iran","capabilities":["Proxy warfare","Sabotage","HUMINT","Unconventional"],"limitations":["No air support","Light weapons only","C2 dispersed"],"typical_strength":1500},
                {"name":"Fateh-110 Missile Battery","type":"Missile","echelon":"Battery","nation_group":"Iran","capabilities":["300km range","Mobile","Precision capable","Rapid launch"],"limitations":["Limited guidance","Reload slow","Vulnerable to EW"],"typical_strength":6},
                # Generic / Hybrid
                {"name":"Proxy Militia Brigade","type":"Infantry","echelon":"Brigade","nation_group":"Generic","capabilities":["Guerrilla tactics","IED employment","Area denial","HUMINT network"],"limitations":["No air defense","Light weapons","Logistics primitive","C2 poor"],"typical_strength":2000},
                {"name":"Cyber Operations Team","type":"Cyber","echelon":"Team","nation_group":"Generic","capabilities":["Network intrusion","SCADA attacks","Information ops","Attribution masking"],"limitations":["Requires access","Detectable","Reversible effects"],"typical_strength":20},
                {"name":"UAS Squadron (Medium)","type":"Aviation","echelon":"Squadron","nation_group":"Generic","capabilities":["ISR","Strike","EW","Persistent surveillance"],"limitations":["Weather sensitive","Jammable","Limited payload"],"typical_strength":12},
                {"name":"NBC Defense Company","type":"Protection","echelon":"Company","nation_group":"Generic","capabilities":["CBRN detection","Decontamination","Hazmat response","Reporting"],"limitations":["Slow operations","Equipment heavy","Limited combat"],"typical_strength":120},
                {"name":"Information Operations Cell","type":"IO","echelon":"Cell","nation_group":"Generic","capabilities":["PSYOP","Social media influence","Disinformation","MISO"],"limitations":["Slow effects","Attribution risk","Legal constraints"],"typical_strength":30},
            ]
            for u in units:
                db.add(models.UnitTemplate(
                    name=u["name"], type=u["type"], echelon=u["echelon"],
                    nation_group=u["nation_group"],
                    capabilities=json.dumps(u["capabilities"]),
                    limitations=json.dumps(u["limitations"]),
                    typical_strength=u["typical_strength"]
                ))
            db.commit()
            print(f"✓ Unit library: {len(units)} units")

        # ── Scenario Templates ──────────────────────────────────────────────
        if db.query(models.Scenario).filter_by(is_template=True).count() == 0:
            scenarios = _build_scenarios()
            for s in scenarios:
                db.add(models.Scenario(
                    title=s["title"],
                    classification="UNCLASSIFIED",
                    scenario_type=s["scenario_type"],
                    timeframe=s["timeframe"],
                    geography=json.dumps(s["geography"]),
                    situation=json.dumps(s["situation"]),
                    factions=json.dumps(s["factions"]),
                    injects=json.dumps(s["injects"]),
                    win_conditions=json.dumps(s["win_conditions"]),
                    ai_notes=s["ai_notes"],
                    is_template=True,
                    template_name=s["template_name"],
                ))
            db.commit()
            print(f"✓ {len(scenarios)} scenario templates created")

        # ── Demo IRON WOLF Session ──────────────────────────────────────────
        if db.query(models.GameSession).filter_by(title="IRON WOLF — DEMO SESSION").count() == 0:
            iron_wolf = db.query(models.Scenario).filter_by(template_name="IRON_WOLF").first()
            if iron_wolf:
                _create_demo_session(db, iron_wolf)
                print("✓ Demo IRON WOLF session created")

        print("\n✅ Database seeded successfully!")
        print("   Login: admin / theater123")
        print("   Start backend: uvicorn main:app --reload --port 8000")

    finally:
        db.close()


def _build_scenarios():
    return [
        # ── 1: IRON WOLF ─────────────────────────────────────────────────
        {
            "template_name": "IRON_WOLF",
            "title": "IRON WOLF: Defense of the Suwalki Gap",
            "scenario_type": "Tactical",
            "timeframe": "72 hours, March 2026",
            "geography": {
                "region": "Suwalki Gap, northeastern Poland / Lithuania border",
                "key_terrain": ["Suwalki town (administrative center)", "Augustow Forest (concealment)", "Raczki Ridge (observation)", "Sejny Corridor (axis of advance)", "Mazury Lakes (obstacle)"],
                "chokepoints": ["Suwalki urban area (Route 8 junction)", "Augustow Canal crossings", "Szypliszki border crossing", "Lazdijai-Kalvarija road"],
                "strategic_locations": ["Suwalki Airport (LOC)", "Margrabowa logistics hub", "Sejny border post", "Augustow rail junction"]
            },
            "situation": {
                "background": "The Suwalki Gap — a 100km land corridor between the Kaliningrad Oblast and Belarus — is NATO's most vulnerable chokepoint. Russian and Belarusian forces have conducted a series of escalatory provocations along the border throughout February 2026, including live-fire exercises within 10km of Polish territory. The NATO Enhanced Forward Presence battlegroup in Lithuania has been reinforced, but remains below BCT strength. Poland has activated its territorial defense forces and placed the 15th Mechanized Brigade on REDCON-2.\n\nIntelligence assessments indicate the Russian 11th Army Corps in Kaliningrad has surged ammunition and fuel reserves to a 30-day sustainment posture. Electronic warfare activity has increased 340% in the past 72 hours, degrading Polish border monitoring systems. The Belarusian 6th Mechanized Brigade has moved to assembly areas within 40km of the border. A diplomatic incident involving Polish fishing vessels seized in Kaliningrad waters has provided a pretext for escalation.\n\nNATO Article 4 consultations are ongoing. SACEUR has authorized force protection measures but has not yet ordered full defensive deployment. Political constraints require NATO forces to avoid firing first except in self-defense. Time is critical: intelligence suggests a 72-hour window before Russian forces can achieve a fait accompli seizure of the Gap.",
                "precipitating_event": "At 0200 local on Day 1, Russian Spetsnaz elements conducted sabotage attacks on three Polish border monitoring stations and the Augustow Canal bridge control systems. Simultaneously, electronic warfare assets jammed Polish military communications across the Gap region. The Polish 15th Mechanized Brigade reported contact with advance elements of what appears to be the Russian 79th Motor Rifle Brigade. NATO declared Article 5 crisis conditions at 0400.",
                "current_situation": "NATO BCT is moving to prepared defensive positions across the Gap. Russian forward detachments are probing NATO positions, supported by heavy electronic warfare and indirect fires. Air space is contested — Polish F-16s have engaged Russian Su-27s in two beyond-visual-range engagements. The Lithuanian 3rd Mechanized Battalion is moving south to link with Polish forces at Sejny. Time is the critical variable: if Russia can sever the Gap in 72 hours, Baltic states may be isolated before NATO Article 5 consensus triggers reinforcement."
            },
            "factions": [
                {
                    "faction_id": "BLUE-01",
                    "name": "NATO Combined Arms Force (4/3 ABCT + Polish 15th Mech)",
                    "side": "Blue",
                    "role": "Player",
                    "objective_primary": "Maintain physical control of the Suwalki Gap corridor — Route 8 must remain open to NATO reinforcements for the full 72 hours",
                    "objective_secondary": "Preserve brigade combat power above 70% strength; avoid civilian casualties in Suwalki urban area",
                    "constraints": "Rules of engagement require positive ID before engagement; no fires within 500m of civilian structures without GM approval; cannot cross into Kaliningrad or Belarus territory; airspace coordination required for all CAS requests (20-minute delay)",
                    "victory_conditions": [
                        {"condition": "Route 8 corridor remains open at game end", "weight_pct": 40},
                        {"condition": "Russian forces do not reach Suwalki town", "weight_pct": 30},
                        {"condition": "NATO force strength above 60% at game end", "weight_pct": 20},
                        {"condition": "No civilian mass casualty events in Suwalki", "weight_pct": 10}
                    ],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"BLU-1","name":"1-68 Armor (M1A2 SEPv3)","type":"Armor","echelon":"Battalion","parent_unit":None,"strength":"Full","location":{"lat":54.10,"lng":22.93,"grid_reference":"UP 721 384"},"capabilities":["Heavy direct fire","Thermal optics","APS"],"limitations":["Fuel-intensive","Urban restrictions"]},
                            {"unit_id":"BLU-2","name":"3-15 Infantry (Mech/Bradley)","type":"Mechanized Infantry","echelon":"Battalion","parent_unit":None,"strength":"Full","location":{"lat":54.07,"lng":22.88,"grid_reference":"UP 698 352"},"capabilities":["Dismount capability","TOW missiles","Night ops"],"limitations":["Urban vulnerability","Maintenance"]},
                            {"unit_id":"BLU-3","name":"1-9 Field Artillery (M109A7)","type":"Artillery","echelon":"Battalion","parent_unit":None,"strength":"Full","location":{"lat":54.05,"lng":22.95,"grid_reference":"UP 740 333"},"capabilities":["155mm precision","Excalibur","Shoot-scoot"],"limitations":["Ammo consumption","Air defense gap"]},
                            {"unit_id":"BLU-4","name":"3/15 Mech Brigade (Polish)","type":"Mechanized Infantry","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":54.15,"lng":23.10,"grid_reference":"UP 820 430"},"capabilities":["Leopard 2A5 tanks","Rosomak APCs","Border knowledge"],"limitations":["Different C2 system","Language barrier"]},
                            {"unit_id":"BLU-5","name":"HIMARS Battery A","type":"Artillery","echelon":"Battery","parent_unit":None,"strength":"Full","location":{"lat":53.95,"lng":22.80,"grid_reference":"UP 642 231"},"capabilities":["GMLRS 70km","Rapid displacement","Precision"],"limitations":["Magazine limited","High-value target"]},
                            {"unit_id":"BLU-6","name":"1-4 Air Defense (Patriot)","type":"Air Defense","echelon":"Battery","parent_unit":None,"strength":"Full","location":{"lat":54.00,"lng":22.90,"grid_reference":"UP 710 280"},"capabilities":["TBM intercept","Anti-cruise missile"],"limitations":["Fixed site","Reload time"]}
                        ],
                        "enablers": ["Polish Air Force F-16s (4 available per turn)", "AWACS coverage from NATO airspace", "SIGINT collection from NSA forward element", "Corps engineer bridge company"],
                        "logistics_state": "Adequate"
                    },
                    "starting_posture": "Defensive",
                    "ai_personality": "Cautious"
                },
                {
                    "faction_id": "RED-01",
                    "name": "Russian 11th Army Corps (Kaliningrad)",
                    "side": "Red",
                    "role": "AI-controlled",
                    "objective_primary": "Seize and hold the Suwalki Gap corridor within 72 hours, physically severing land connection between Poland and the Baltic states",
                    "objective_secondary": "Destroy or render combat-ineffective at least one NATO maneuver battalion; demonstrate Western inability to defend Baltic allies",
                    "constraints": "Political constraints: avoid strikes on Suwalki civilian population center until ordered; Kaliningrad-based assets are protected — do not risk S-400 systems to direct NATO counterfire; Belarusian forces are enablers only, not main effort",
                    "victory_conditions": [
                        {"condition": "Russian forces control Route 8 junction at Suwalki by game end", "weight_pct": 45},
                        {"condition": "NATO force strength reduced below 50% in at least one sector", "weight_pct": 30},
                        {"condition": "Russian main effort forces suffer less than 40% casualties", "weight_pct": 25}
                    ],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"RED-1","name":"79th Motor Rifle Brigade","type":"Mechanized Infantry","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":54.72,"lng":21.95,"grid_reference":"KG 234 817"},"capabilities":["T-72B3 tanks","BMP-2 IFVs","Organic artillery","EW assets"],"limitations":["Limited NCO quality","Logistics fragile"]},
                            {"unit_id":"RED-2","name":"7th Motor Rifle Regiment","type":"Mechanized Infantry","echelon":"Regiment","parent_unit":None,"strength":"Full","location":{"lat":54.68,"lng":22.10,"grid_reference":"KG 312 789"},"capabilities":["BMP-3 IFVs","Thermobaric weapons","Urban warfare"],"limitations":["Coordination with 79th MRB"]},
                            {"unit_id":"RED-3","name":"244th Artillery Brigade (Iskander)","type":"Artillery","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":54.85,"lng":21.80,"grid_reference":"KG 158 921"},"capabilities":["Iskander-M 500km","Precision strike","Quick reaction"],"limitations":["High-value target","Limited rounds"]},
                            {"unit_id":"RED-4","name":"RB-109A Bylina EW Complex","type":"EW","echelon":"Battalion","parent_unit":None,"strength":"Full","location":{"lat":54.75,"lng":21.90,"grid_reference":"KG 221 838"},"capabilities":["GPS jamming","Comms disruption","Drone defeat"],"limitations":["Signature","Affects own comms"]},
                            {"unit_id":"RED-5","name":"6th Mechanized Brigade (Belarus)","type":"Mechanized Infantry","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":53.90,"lng":23.80,"grid_reference":"YB 187 204"},"capabilities":["Flanking threat","BMP-2","Militia support"],"limitations":["Coordination fragile","Logistics poor"]}
                        ],
                        "enablers": ["Su-27 air cover from Kaliningrad (contested)", "Spetsnaz reconnaissance teams (3 active)", "S-400 system providing area denial (not to be expended)", "Belarusian border pressure force"],
                        "logistics_state": "Robust"
                    },
                    "starting_posture": "Offensive",
                    "ai_personality": "Aggressive"
                }
            ],
            "injects": [
                {"inject_id":"INJ-01","turn_trigger":2,"condition_trigger":None,"description":"NATO SIGINT intercepts communications indicating Russian 79th MRB is planning a night assault through the Augustow Forest. Intel is 72-hour old and may not reflect current dispositions. Blue force receives this 30 minutes before turn resolution.","type":"Intel","affected_factions":["BLUE-01"]},
                {"inject_id":"INJ-02","turn_trigger":3,"condition_trigger":None,"description":"A civilian convoy of 400 Polish refugees is moving south on Route 8, directly through the anticipated Russian axis of advance. GM must decide: halt convoy (delaying NATO logistics), reroute through forest (3-hour delay), or allow movement and accept civilian risk.","type":"Decision","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-03","turn_trigger":4,"condition_trigger":None,"description":"Weather front: heavy fog and rain reduces visibility to 500m and grounds all fixed-wing aircraft for 12 hours. All air support unavailable; artillery spotting degraded. Affects both sides equally.","type":"Friction","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-04","turn_trigger":5,"condition_trigger":None,"description":"Lithuania triggers Article 5 emergency provisions. US 82nd Airborne Division lead elements (1 battalion) will arrive at Vilnius in 18 hours (2 turns). Morale boost for NATO, changes Russian timeline calculus.","type":"Event","affected_factions":["BLUE-01"]},
                {"inject_id":"INJ-05","turn_trigger":6,"condition_trigger":"If Russian forces control any terrain adjacent to Suwalki town","description":"Russian information operations campaign goes viral: social media flooded with images (some doctored) of NATO forces firing on civilians. Lithuanian parliament begins emergency session on NATO commitment. Blue force political constraints tighten: all artillery in 2km of Suwalki requires GM approval.","type":"Event","affected_factions":["BLUE-01","RED-01"]}
            ],
            "win_conditions": {
                "duration_turns": 8,
                "adjudication_method": "Points",
                "scoring_dimensions": [
                    {"dimension": "Terrain control (Route 8 corridor)", "weight_pct": 40},
                    {"dimension": "Force preservation", "weight_pct": 25},
                    {"dimension": "Objective achievement", "weight_pct": 25},
                    {"dimension": "Civilian protection", "weight_pct": 10}
                ]
            },
            "ai_notes": "DESIGNER NOTES: This scenario models the Suwalki Gap problem, NATO's most studied vulnerability (cf. RAND 2016 study 'Reinforcing Deterrence on NATO's Eastern Flank'). The historical analogue is the Fulda Gap problem during Cold War, but compressed to brigade level with modern fires and EW. KEY DYNAMICS: (1) Time is the critical variable — Russia needs speed, NATO needs to delay until reinforcement; (2) EW will degrade Blue comms significantly — plan for degraded C2; (3) The Augustow Forest creates a concealment corridor that complicates NATO ISR; (4) Logistics will stress both sides by Turn 4; (5) The Belarusian flanking threat forces NATO to divide attention. FRICTION POINTS: NATO ROE restrictions will create command frustration; civilian traffic on Route 8 will complicate fires; weather inject (Turn 4) fundamentally changes the fight. HISTORICAL: Compare to Operation Bagration's tempo and Soviet deep battle doctrine applied at brigade scale."
        },
        # ── 2: STRAIT GAME ───────────────────────────────────────────────
        {
            "template_name": "STRAIT_GAME",
            "title": "STRAIT GAME: PRC Gray-Zone Coercion, Taiwan Strait",
            "scenario_type": "Gray-Zone",
            "timeframe": "90 days, Q2 2026",
            "geography": {
                "region": "Taiwan Strait and surrounding maritime/air space",
                "key_terrain": ["Penghu Islands (midpoint strategic position)", "Kinmen/Matsu (ROC-held offshore islands)", "East China Sea air space", "Bashi Channel (southern access)", "Miyako Strait (US naval access)"],
                "chokepoints": ["Taiwan Strait center line (historical median line)", "Penghu Channel", "Bashi Channel", "Luzon Strait"],
                "strategic_locations": ["Taipei (political center)", "Kaohsiung Port (economic hub)", "Taichung Air Base", "Zuoying Naval Base", "Hualien Air Base (dispersal)"]
            },
            "situation": {
                "background": "Taiwan's January 2026 elections returned the Democratic Progressive Party to power with an increased mandate and a presidential platform explicitly supporting formal defense agreements with the United States. Beijing characterized the election as a 'separatist provocation' and announced the suspension of all cross-strait economic exchanges. The PRC State Council authorized the PLA to conduct 'necessary military activities' in defense of sovereignty. Simultaneously, Beijing launched a comprehensive economic pressure campaign: halting rare earth exports to Taiwan and pressuring third-country semiconductor firms to cease Taiwan contracts.\n\nThe PLA Eastern Theater Command has surged forces to a high-readiness posture, conducting what Beijing calls 'Joint Sword 2026' exercises involving all service branches. PLA naval vessels have begun transiting what Taipei considers Taiwan's territorial waters around Kinmen and Matsu. ADIZ incursions have increased from 4/week to 34/week in the past month. The US has repositioned a carrier strike group to the Philippine Sea but has not yet transited the Taiwan Strait.\n\nThe scenario explores the 180-day gray zone between coercive intimidation and outright kinetic conflict. Blue (US/Taiwan) must deter escalation and preserve Taiwan's political independence without triggering a shooting war. Red (PRC) must achieve maximum coercive effect — economic, political, and military pressure — to extract concessions without crossing Article 5 or triggering US intervention.",
                "precipitating_event": "The PRC Coast Guard announced a new 'Maritime Safety Inspection Zone' encompassing Kinmen and Matsu islands, effective immediately, requiring all vessels to receive PRC Coast Guard authorization before entering. Taiwan rejected the announcement as illegal. Two ROCN patrol vessels were surrounded but not fired upon by PRC Coast Guard cutters. The US State Department issued a statement of 'deep concern.'",
                "current_situation": "Day 1 of the 90-day campaign. PRC is applying multi-domain coercive pressure below the threshold of armed conflict. Taiwan faces simultaneous economic, cyber, information, and military pressure. The US is calibrating its response: strong enough to deter escalation, measured enough not to provide pretext for PRC kinetic action. Japan and Australia are watching closely; their responses will be shaped by US leadership signals."
            },
            "factions": [
                {
                    "faction_id": "BLUE-01", "name": "US Indo-Pacific Command / Taiwan (ROC)",
                    "side": "Blue", "role": "Player",
                    "objective_primary": "Deter PRC from escalating to kinetic conflict while preserving Taiwan's de facto political independence and economic viability",
                    "objective_secondary": "Maintain coalition solidarity (Japan, Australia, Philippines); avoid actions that provide PRC pretext for kinetic escalation",
                    "constraints": "US cannot commit forces to combat without POTUS authorization; Taiwan cannot formally declare independence; all military actions must be coordinated through joint US-ROC C2; economic countermeasures require Congressional authorization",
                    "victory_conditions": [{"condition":"No kinetic conflict by Day 90","weight_pct":40},{"condition":"Taiwan's economy does not contract more than 15% GDP","weight_pct":25},{"condition":"PRC does not achieve control of Penghu, Kinmen, or Matsu","weight_pct":25},{"condition":"US-Japan-Australia coalition holds","weight_pct":10}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"BLU-1","name":"USS Ronald Reagan CSG","type":"Naval","echelon":"Group","parent_unit":None,"strength":"Full","location":{"lat":21.0,"lng":124.5,"grid_reference":"Philippine Sea"},"capabilities":["F/A-18 strike","Aegis BMD","Presence signaling","Anti-ship"],"limitations":["Political constraints on transit","High-value target"]},
                            {"unit_id":"BLU-2","name":"ROCAF F-16V Wing (4th TFW)","type":"Air","echelon":"Wing","parent_unit":None,"strength":"Full","location":{"lat":24.26,"lng":120.62,"grid_reference":"Taichung AB"},"capabilities":["Air superiority","Strike","SEAD","AESA radar"],"limitations":["Numerical inferiority vs PLAAF","Base vulnerability"]},
                            {"unit_id":"BLU-3","name":"ROCN Submarine Flotilla","type":"Naval","echelon":"Flotilla","parent_unit":None,"strength":"Full","location":{"lat":23.0,"lng":120.0,"grid_reference":"Classified"},"capabilities":["Anti-ship","ISR","Deterrence","Mine warfare"],"limitations":["Aging boats","Maintenance","Limited numbers"]},
                            {"unit_id":"BLU-4","name":"US Cyber Command Task Force","type":"Cyber","echelon":"Team","parent_unit":None,"strength":"Full","location":{"lat":38.9,"lng":-77.0,"grid_reference":"Fort Meade MD"},"capabilities":["Offensive cyber","Network defense","PRC infrastructure targeting"],"limitations":["Escalation risk","Attribution","Legal constraints"]}
                        ],
                        "enablers": ["State Department diplomatic channel","US Treasury economic sanctions authority","Japan GSDF/MSDF cooperation","JASSM-ER long-range strike capability"],
                        "logistics_state": "Robust"
                    },
                    "starting_posture": "Economy of Force",
                    "ai_personality": "Cautious"
                },
                {
                    "faction_id": "RED-01", "name": "PRC / PLA Eastern Theater Command",
                    "side": "Red", "role": "AI-controlled",
                    "objective_primary": "Compel Taiwan to accept political negotiations on PRC terms — specifically, agreement to '1992 Consensus' framing and suspension of formal US defense agreements",
                    "objective_secondary": "Demonstrate to regional neighbors that US security guarantees are unreliable; fracture US-Japan-Australia coalition",
                    "constraints": "Avoid kinetic action that triggers US military response; protect CCP legitimacy — domestic audiences expect strength but not catastrophic losses; Politburo Standing Committee approval required for any lethal action",
                    "victory_conditions": [{"condition":"Taiwan agrees to political negotiations on PRC terms","weight_pct":50},{"condition":"US-Taiwan defense agreement suspended or delayed","weight_pct":30},{"condition":"US-Japan alliance publicly strained","weight_pct":20}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"RED-1","name":"PLA 71st Group Army","type":"Combined Arms","echelon":"Army","parent_unit":None,"strength":"Full","location":{"lat":26.0,"lng":119.3,"grid_reference":"Fujian Province"},"capabilities":["Amphibious assault ready","Coastal fires","EW integration"],"limitations":["Blue-water logistics","Amphibious complexity"]},
                            {"unit_id":"RED-2","name":"PLAN South Sea Fleet","type":"Naval","echelon":"Fleet","parent_unit":None,"strength":"Full","location":{"lat":22.3,"lng":114.2,"grid_reference":"Zhanjiang Naval Base"},"capabilities":["Type 055 destroyers","Carrier Shandong","Submarine force","Anti-ship missiles"],"limitations":["ASW gaps","Carrier experience"]},
                            {"unit_id":"RED-3","name":"PLA Rocket Force (DF-21D/DF-26)","type":"Missile","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":29.0,"lng":116.0,"grid_reference":"Classified"},"capabilities":["Anti-ship ballistic missiles","4000km range","Saturation capability"],"limitations":["Targeting dependent on ISR","High-value target"]},
                            {"unit_id":"RED-4","name":"PRC State Cyber Force (MSS/PLA Unit 61398)","type":"Cyber","echelon":"Team","parent_unit":None,"strength":"Full","location":{"lat":31.2,"lng":121.5,"grid_reference":"Shanghai"},"capabilities":["Critical infrastructure targeting","Financial system attacks","Disinformation"],"limitations":["Attribution risk","Escalation"]}
                        ],
                        "enablers": ["Global Times information operations","Economic sanctions (rare earths)","Coast Guard gray-zone harassment","Diplomatic pressure on third countries"],
                        "logistics_state": "Robust"
                    },
                    "starting_posture": "Shaping",
                    "ai_personality": "Deceptive"
                }
            ],
            "injects": [
                {"inject_id":"INJ-01","turn_trigger":2,"condition_trigger":None,"description":"PRC cyber attack takes down Taiwan Stock Exchange for 4 hours, causing 8% market drop. Attribution is clear to intelligence community but not publicly provable. Blue must decide: public attribution (escalatory) or quiet response (signals weakness).","type":"Decision","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-02","turn_trigger":4,"condition_trigger":None,"description":"Japan announces it will 'review' the US-Japan alliance framework in light of Taiwan tensions, signaling potential neutrality. This is a Red information operations success. Blue must respond within 48 hours or Japan's posture solidifies.","type":"Event","affected_factions":["BLUE-01"]},
                {"inject_id":"INJ-03","turn_trigger":6,"condition_trigger":None,"description":"PRC Coast Guard vessel 'accidentally' fires water cannons on ROC Coast Guard cutter, injuring 3 sailors. ROC President demands response. This is the escalation threshold moment.","type":"Decision","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-04","turn_trigger":8,"condition_trigger":None,"description":"Semiconductor shortage reaches critical level: TSMC reports inability to fulfill US DoD contracts due to supply chain disruption. US Congress demands action. Blue political constraints loosen: military options now available without prior approval.","type":"Event","affected_factions":["BLUE-01"]}
            ],
            "win_conditions": {"duration_turns":9,"adjudication_method":"Objective-based","scoring_dimensions":[{"dimension":"Political stability","weight_pct":40},{"dimension":"Economic resilience","weight_pct":30},{"dimension":"Military deterrence","weight_pct":20},{"dimension":"Alliance cohesion","weight_pct":10}]},
            "ai_notes": "DESIGNER NOTES: This models the 'gray zone' problem — coercion below the threshold of armed conflict. Historical analogues: Crimea 2014 (fait accompli), Hong Kong 2019-2020 (economic/political pressure), and PRC pressure on Philippines in South China Sea. KEY INSIGHT: Red wins if Blue over-responds (provocation) or under-responds (emboldenment). The optimal Blue strategy is calibrated, multimodal response across economics, cyber, and military signaling simultaneously. FRICTION: Domestic political pressures on both sides create suboptimal decisions; coalition solidarity is the key Blue center of gravity; the cyber domain provides Red with deniable escalation options. NOTE for game masters: inject timing can be adjusted to compress or extend the escalation ladder."
        },
        # ── 3: DESERT THUNDER ────────────────────────────────────────────
        {
            "template_name": "DESERT_THUNDER",
            "title": "DESERT THUNDER: US-Iran Conventional Strike Response",
            "scenario_type": "Operational",
            "timeframe": "30 days, 2026",
            "geography": {
                "region": "Arabian Gulf, Gulf of Oman, and Iranian territory",
                "key_terrain": ["Strait of Hormuz (global energy chokepoint)", "Kharg Island (Iran oil terminal)", "Bandar Abbas (IRGCN base)", "Al Udeid Air Base (CENTCOM HQ)", "USS Abraham Lincoln CSG operating area"],
                "chokepoints": ["Strait of Hormuz (33km wide)", "Gulf of Oman transit lanes", "Persian Gulf shipping lanes"],
                "strategic_locations": ["Natanz enrichment facility (target)", "Fordow facility (target)", "Kharg Island oil terminal", "Tehran political center", "Bushehr nuclear plant"]
            },
            "situation": {
                "background": "US and Israeli intelligence jointly assessed that Iran achieved sufficient fissile material for a nuclear device in January 2026. International Atomic Energy Agency inspectors were expelled from Iran in February. US President authorized CENTCOM to conduct limited strikes on Iranian nuclear facilities on Day 0 of the scenario. Israeli Air Force participated in strike planning but did not execute (plausible deniability maintained). Strikes achieved 60-70% destruction of Natanz and Fordow facilities, with 3 US aircraft lost.",
                "precipitating_event": "Iranian Supreme Leader announced within 6 hours of strikes that Iran will 'respond at the time and place of our choosing' and declared the Strait of Hormuz 'under Iranian sovereign protection.' IRGCN deployed fast boat swarms and Houthi proxies fired ballistic missiles at Saudi Arabia.",
                "current_situation": "Day 2 post-strike. Iran is mobilizing conventional and proxy forces. Two US tankers have been attacked in the Gulf of Oman. Oil markets have spiked 40%. GCC partners are requesting US protection but balking at being named as basing nations. The US has a 30-day window before Iranian nuclear reconstitution begins at dispersed sites — political pressure demands the window be exploited or surrendered."
            },
            "factions": [
                {
                    "faction_id": "BLUE-01", "name": "US CENTCOM / GCC Coalition",
                    "side": "Blue", "role": "Player",
                    "objective_primary": "Prevent Iranian reconstitution of nuclear program; protect Strait of Hormuz freedom of navigation for 30 days",
                    "objective_secondary": "Minimize Iranian escalation to proxy attacks on Gulf partners; preserve international coalition support",
                    "constraints": "No US ground forces in Iran; Israeli participation must remain non-public; GCC partner base access requires daily political approval; Congressional War Powers notification limits kinetic action to 60 days",
                    "victory_conditions": [{"condition":"Strait of Hormuz remains open throughout","weight_pct":40},{"condition":"Iranian reconstitution delayed 12+ months","weight_pct":35},{"condition":"GCC coalition intact at Day 30","weight_pct":25}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"BLU-1","name":"USS Abraham Lincoln CSG","type":"Naval","echelon":"Group","parent_unit":None,"strength":"Full","location":{"lat":24.5,"lng":58.5,"grid_reference":"Gulf of Oman"},"capabilities":["F/A-18E/F strike","Aegis","Tomahawk","ASW"],"limitations":["Strait of Hormuz access risk","High-value target"]},
                            {"unit_id":"BLU-2","name":"USAF 494th FS (F-15E)","type":"Air","echelon":"Squadron","parent_unit":None,"strength":"Full","location":{"lat":25.1,"lng":51.5,"grid_reference":"Al Udeid AB"},"capabilities":["Long-range strike","JDAM/JASSM","SEAD","Night operations"],"limitations":["Basing politics","Air defense threat"]},
                            {"unit_id":"BLU-3","name":"B-2 Spirit Detachment","type":"Air","echelon":"Flight","parent_unit":None,"strength":"Full","location":{"lat":13.5,"lng":144.8,"grid_reference":"Andersen AFB"},"capabilities":["Stealth","MOP bunker buster","Strategic strike","Standoff"],"limitations":["Limited sorties","Very long transit"]},
                            {"unit_id":"BLU-4","name":"USS Georgia SSGN","type":"Naval","echelon":"Submarine","parent_unit":None,"strength":"Full","location":{"lat":23.0,"lng":58.0,"grid_reference":"Gulf of Oman (submerged)"},"capabilities":["154 Tomahawks","SOF insertion","Covert presence"],"limitations":["Detection risk in shallow Gulf"]}
                        ],
                        "enablers": ["E-3 AWACS (Qatar)","RQ-4 Global Hawk ISR","Saudi RSAF F-15SA support","UAE basing for tankers"],
                        "logistics_state": "Adequate"
                    },
                    "starting_posture": "Shaping",
                    "ai_personality": "Cautious"
                },
                {
                    "faction_id": "RED-01", "name": "IRGC / Iranian Armed Forces",
                    "side": "Red", "role": "AI-controlled",
                    "objective_primary": "Impose maximum economic and military cost on US and Gulf partners to deter further strikes; demonstrate that Iran cannot be attacked without consequence",
                    "objective_secondary": "Preserve Iranian conventional military capability; protect remaining nuclear infrastructure; avoid strikes on Tehran proper",
                    "constraints": "Avoid actions that trigger direct US homeland retaliation; conventional military must not be expended in losing battles; Supreme Leader approval required for any action affecting Russian or Chinese interests",
                    "victory_conditions": [{"condition":"Strait of Hormuz closed for 72+ hours (oil spike)","weight_pct":40},{"condition":"US or GCC partner suffers significant military casualties","weight_pct":35},{"condition":"International condemnation of US strikes achieved","weight_pct":25}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"RED-1","name":"IRGCN Fast Boat Flotilla","type":"Naval","echelon":"Flotilla","parent_unit":None,"strength":"Full","location":{"lat":27.2,"lng":56.4,"grid_reference":"Bandar Abbas"},"capabilities":["Swarm tactics","Mines","Anti-ship missiles","Suicide boats"],"limitations":["Vulnerable to US fires","No air defense","Day ops only"]},
                            {"unit_id":"RED-2","name":"IRGC Aerospace Force (Ballistic Missiles)","type":"Missile","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":32.0,"lng":53.0,"grid_reference":"Central Iran (dispersed)"},"capabilities":["Shahab-3 MRBM","Emad precision variant","500-2000km range","Dispersed launch"],"limitations":["Accuracy limited","Reload slow","US intercept capable"]},
                            {"unit_id":"RED-3","name":"Houthi Proxy Force (Yemen)","type":"Proxy","echelon":"Brigade","parent_unit":None,"strength":"Full","location":{"lat":15.4,"lng":44.2,"grid_reference":"Sanaa area"},"capabilities":["Drone swarms","Anti-ship missiles","Deniability","Area denial"],"limitations":["No sophisticated C2","Air defense vulnerable","Supply lines tenuous"]},
                            {"unit_id":"RED-4","name":"Quds Force Proxy Network","type":"SF","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":33.3,"lng":44.4,"grid_reference":"Iraq/Syria (dispersed)"},"capabilities":["IED attacks on US bases","HUMINT","Sabotage","Rocket attacks"],"limitations":["Deniability required","Limited heavy weapons"]}
                        ],
                        "enablers": ["Lebanese Hezbollah threat-in-being","Iraqi PMF harassment","Global information operations (RT/Press TV)","MOIS intelligence network in Gulf"],
                        "logistics_state": "Adequate"
                    },
                    "starting_posture": "Defensive",
                    "ai_personality": "Attrition-focused"
                }
            ],
            "injects": [
                {"inject_id":"INJ-01","turn_trigger":2,"condition_trigger":None,"description":"Houthi drone swarm (22 drones) attacks Saudi Aramco Abqaiq facility. 3 storage tanks destroyed. Oil production drops 5 million bbl/day. International pressure on US intensifies.","type":"Event","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-02","turn_trigger":4,"condition_trigger":None,"description":"US merchant vessel MV Pacific Voyager struck by IRGCN torpedo in Strait of Hormuz. 4 US civilians killed. Lloyd's of London suspends Gulf shipping insurance. Congress demands military response.","type":"Event","affected_factions":["BLUE-01"]},
                {"inject_id":"INJ-03","turn_trigger":7,"condition_trigger":None,"description":"Intelligence indicates Iran has moved reconstitution equipment to 3 dispersed sites not on original target list, including one beneath a hospital in Isfahan. Blue strike authority requires specific Presidential Finding for each site.","type":"Intel","affected_factions":["BLUE-01"]}
            ],
            "win_conditions": {"duration_turns":10,"adjudication_method":"Points","scoring_dimensions":[{"dimension":"Strait of Hormuz openness","weight_pct":35},{"dimension":"Nuclear reconstitution delay","weight_pct":30},{"dimension":"Coalition solidarity","weight_pct":20},{"dimension":"Iranian military degradation","weight_pct":15}]},
            "ai_notes": "DESIGNER NOTES: Models the post-strike escalation problem — how does Iran respond to a US/Israeli nuclear strike, and how does the US manage escalation while protecting Gulf partners? Historical analogues: Israeli strike on Iraqi Osirak (1981), Operation Praying Mantis (1988), and the 2020 Soleimani strike aftermath. KEY DYNAMICS: Iran's asymmetric strategy (proxies, mining, swarms) is designed to impose costs without giving the US a clean kinetic target. Blue must balance escalation management with deterrence credibility. FRICTION: GCC partner politics are critical — Saudi/UAE may withdraw basing rights if casualties mount; international coalition is fragile; Congressional timeline pressure is real."
        },
        # ── 4: SHADOW CAMPAIGN ───────────────────────────────────────────
        {
            "template_name": "SHADOW_CAMPAIGN",
            "title": "SHADOW CAMPAIGN: Russian Hybrid Warfare, Eastern Europe",
            "scenario_type": "Strategic",
            "timeframe": "6 months, 2026",
            "geography": {
                "region": "Eastern Europe: Poland, Baltic states, Moldova, and Romania",
                "key_terrain": ["Warsaw (NATO political hub)", "Vilnius (junction point)", "Chisinau (vulnerable state)", "Riga (vulnerable Baltic capital)", "Bucharest (southern flank)"],
                "chokepoints": ["Suwalki Gap (physical)", "NATO information environment", "European energy grid", "EU financial system"],
                "strategic_locations": ["US embassies (17 in region)", "NATO Multinational Corps NE (Szczecin)", "European critical infrastructure (pipelines, grids)", "Transatlantic fiber optic cables"]
            },
            "situation": {
                "background": "Russia has determined that direct military confrontation with NATO is too costly following the lessons of the Ukraine war. Instead, GRU and FSB have been directed to conduct a coordinated 6-month 'Strategic Influence Operation' designed to fracture NATO cohesion, destabilize vulnerable eastern flank members, and create conditions for a political realignment of Moldova and the Baltic states without direct military action.\n\nThe campaign uses a sophisticated blend of cyber attacks, disinformation, energy coercion, financial warfare, and support to extremist political movements. Multiple GRU contractor groups ('Sandworm,' 'Fancy Bear,' and a new unit designated 'Operation Polar Vortex') have been activated. The operation is designed to appear as organic political instability rather than external interference.",
                "precipitating_event": "A coordinated cyber attack on Estonian and Lithuanian power grids caused 48-hour blackouts affecting 2 million people. Simultaneously, a major German newspaper (since revealed to be a GRU front) published leaked NATO military planning documents. Three pro-Russian political parties in Latvia, Moldova, and Romania held synchronized press conferences calling for NATO withdrawal.",
                "current_situation": "Week 1 of the 6-month campaign. NATO intelligence has assessed the attacks as GRU-coordinated but lacks definitive attribution to present publicly. Blue force (EU/NATO) must identify, attribute, and counter a sophisticated hybrid campaign while maintaining democratic norms and avoiding actions that hand Russia a propaganda victory."
            },
            "factions": [
                {
                    "faction_id": "BLUE-01", "name": "EU/NATO Political-Military Response",
                    "side": "Blue", "role": "Player",
                    "objective_primary": "Maintain NATO cohesion and expose/counter Russian hybrid campaign without escalating to kinetic conflict",
                    "objective_secondary": "Stabilize vulnerable member states; protect critical infrastructure; maintain democratic legitimacy of partner governments",
                    "constraints": "All offensive cyber operations require POTUS and allied consensus; public attribution requires 'high confidence' standard (effectively 90%+); military options require Article 5 consensus — difficult to achieve for gray-zone attacks",
                    "victory_conditions": [{"condition":"All NATO members remain in alliance at 6-month mark","weight_pct":40},{"condition":"Russian operation publicly attributed and condemned by EU/UN","weight_pct":30},{"condition":"Vulnerable states (Moldova, Baltic) politically stable","weight_pct":30}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"BLU-1","name":"NATO Strategic Communications Centre (Riga)","type":"IO","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":56.9,"lng":24.1,"grid_reference":"Riga"},"capabilities":["Counter-disinformation","Attribution","Media coordination","Narrative shaping"],"limitations":["Slow response cycle","Bureaucratic","Language barriers"]},
                            {"unit_id":"BLU-2","name":"EU Hybrid Threats Team (Helsinki Centre)","type":"IO","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":60.2,"lng":25.0,"grid_reference":"Helsinki"},"capabilities":["Election integrity","Financial forensics","Civil society engagement"],"limitations":["No kinetic authority","Member state politics"]},
                            {"unit_id":"BLU-3","name":"US Cyber Command Forward Element","type":"Cyber","echelon":"Team","parent_unit":None,"strength":"Full","location":{"lat":52.2,"lng":21.0,"grid_reference":"Warsaw"},"capabilities":["Offensive cyber","Critical infrastructure defense","Hunt forward operations"],"limitations":["Political constraints","Escalation risk"]},
                            {"unit_id":"BLU-4","name":"NATO CJOC Intelligence Fusion Cell","type":"Intelligence","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":50.8,"lng":4.4,"grid_reference":"Mons, Belgium"},"capabilities":["SIGINT fusion","Pattern of life analysis","Early warning"],"limitations":["Classification barriers","Attribution standards"]}
                        ],
                        "enablers": ["European sanctions authority (EU Council)","State Department public diplomacy","NSA collection assets","MI6/DGSE intelligence sharing"],
                        "logistics_state": "Robust"
                    },
                    "starting_posture": "Defensive",
                    "ai_personality": "Cautious"
                },
                {
                    "faction_id": "RED-01", "name": "Russian GRU / FSB Strategic Operations",
                    "side": "Red", "role": "AI-controlled",
                    "objective_primary": "Fracture NATO political cohesion and create conditions for political realignment of at least 2 eastern European states toward Russian-favorable neutrality within 6 months",
                    "objective_secondary": "Demonstrate that NATO membership does not protect against Russian political-economic pressure; discredit US leadership in European security",
                    "constraints": "Maintain plausible deniability at all costs — any confirmed attribution triggers Western sanctions that undermine the operation; avoid kinetic action that triggers Article 5 consensus (which is currently impossible); Kremlin must approve any action that risks direct confrontation",
                    "victory_conditions": [{"condition":"NATO publicly divided on response (two+ members publicly resist action)","weight_pct":40},{"condition":"Pro-Russian political party wins election in one member state","weight_pct":35},{"condition":"Operation remains officially unattributed for 4+ months","weight_pct":25}],
                    "order_of_battle": {
                        "units": [
                            {"unit_id":"RED-1","name":"GRU Unit 26165 (Fancy Bear)","type":"Cyber","echelon":"Team","parent_unit":None,"strength":"Full","location":{"lat":55.7,"lng":37.6,"grid_reference":"Moscow (remote)"},"capabilities":["Spearphishing","APT operations","Election interference","Document theft and leak"],"limitations":["Attribution risk if sloppy","US countermeasures improving"]},
                            {"unit_id":"RED-2","name":"GRU Unit 74455 (Sandworm)","type":"Cyber","echelon":"Team","parent_unit":None,"strength":"Full","location":{"lat":55.7,"lng":37.6,"grid_reference":"Moscow (remote)"},"capabilities":["Critical infrastructure attacks","Industrial control systems","NotPetya-class disruption"],"limitations":["High attribution risk","Irreversible effects can escalate"]},
                            {"unit_id":"RED-3","name":"Internet Research Agency (Troll Farm)","type":"IO","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":59.9,"lng":30.3,"grid_reference":"St. Petersburg"},"capabilities":["Social media manipulation","Deepfakes","Disinformation","Amplification networks"],"limitations":["Platform takedowns","Exposure risk","Diminishing effectiveness"]},
                            {"unit_id":"RED-4","name":"FSB Active Measures Network","type":"SF","echelon":"Cell","parent_unit":None,"strength":"Full","location":{"lat":50.4,"lng":30.5,"grid_reference":"Distributed Eastern Europe"},"capabilities":["Asset recruitment","Sabotage","Poison attacks","Money flows to proxies"],"limitations":["Exposed network (some blown)","Requires local infrastructure"]}
                        ],
                        "enablers": ["Gazprom energy leverage","RT/Sputnik amplification","Political donations to European parties (via cutouts)","Russian Orthodox Church network"],
                        "logistics_state": "Adequate"
                    },
                    "starting_posture": "Ambiguous",
                    "ai_personality": "Deceptive"
                }
            ],
            "injects": [
                {"inject_id":"INJ-01","turn_trigger":2,"condition_trigger":None,"description":"Moldovan President is photographed with a Russian intelligence handler in Bucharest. Photo leaked to press by unknown source. Moldovan government denies and accuses photo of being AI-generated. Blue must determine authenticity and decide on public response.","type":"Intel","affected_factions":["BLUE-01"]},
                {"inject_id":"INJ-02","turn_trigger":3,"condition_trigger":None,"description":"Russian gas supply to Hungary cut 40%, citing 'maintenance.' Hungary threatens to veto NATO sanctions response. This splits the alliance publicly.","type":"Event","affected_factions":["BLUE-01","RED-01"]},
                {"inject_id":"INJ-03","turn_trigger":5,"condition_trigger":None,"description":"NSA provides Blue with definitive attribution evidence — a GRU officer's personal device was captured in SIGINT linking Sandworm to the power grid attacks. Evidence is from classified source and cannot be publicly disclosed without compromise.","type":"Intel","affected_factions":["BLUE-01"]}
            ],
            "win_conditions": {"duration_turns":6,"adjudication_method":"Narrative","scoring_dimensions":[{"dimension":"Alliance cohesion","weight_pct":40},{"dimension":"Attribution and exposure","weight_pct":30},{"dimension":"Partner state stability","weight_pct":30}]},
            "ai_notes": "DESIGNER NOTES: This models the 'hybrid warfare' problem that NATO has struggled to define doctrine for. Historical analogues: Russian operations in Estonia 2007, Georgia 2008, Ukraine 2014-2022. The key insight: hybrid warfare succeeds when democracies cannot agree on what constitutes an act of war, cannot attribute confidently, and cannot achieve consensus on response. Blue must 'get inside' Red's decision cycle while managing alliance politics. FRICTION: The democratic legitimacy constraint is both Blue's strength (moral authority) and weakness (slow decision-making). Red exploits the gap between 'confident attribution' and 'publicly demonstrable attribution' relentlessly."
        }
        
    ]


def _create_demo_session(db, iron_wolf: models.Scenario):
    factions = json.loads(iron_wolf.factions)
    blue = next(f for f in factions if f["side"] == "Blue")
    red = next(f for f in factions if f["side"] == "Red")

    game_state = {
        "faction_scores": [
            {"faction_id": "BLUE-01", "name": "NATO Combined Arms Force", "side": "Blue", "score": 55, "objective_status": "Holding"},
            {"faction_id": "RED-01", "name": "Russian 11th Army Corps", "side": "Red", "score": 38, "objective_status": "Partial advance"}
        ],
        "unit_status": [
            {"unit_id":"BLU-1","name":"1-68 Armor","faction_id":"BLUE-01","type":"Armor","strength":"Degraded","location":{"lat":54.10,"lng":22.93},"status":"Engaged","supply":{"ammo":65,"fuel":80,"maintenance":70,"munitions":None},"will_to_fight":"Moderate","c2_status":"Nominal","detected_by":["BLUE-01"]},
            {"unit_id":"BLU-2","name":"3-15 Infantry","faction_id":"BLUE-01","type":"Infantry","strength":"Full","location":{"lat":54.07,"lng":22.88},"status":"Active","supply":{"ammo":90,"fuel":85,"maintenance":95,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["BLUE-01"]},
            {"unit_id":"BLU-3","name":"1-9 Field Artillery","faction_id":"BLUE-01","type":"Artillery","strength":"Full","location":{"lat":54.05,"lng":22.95},"status":"Active","supply":{"ammo":70,"fuel":90,"maintenance":85,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["BLUE-01"]},
            {"unit_id":"BLU-4","name":"Polish 15th Mech","faction_id":"BLUE-01","type":"Mechanized Infantry","strength":"Full","location":{"lat":54.15,"lng":23.10},"status":"Active","supply":{"ammo":95,"fuel":95,"maintenance":100,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["BLUE-01"]},
            {"unit_id":"BLU-5","name":"HIMARS Battery A","faction_id":"BLUE-01","type":"Artillery","strength":"Full","location":{"lat":53.95,"lng":22.80},"status":"Active","supply":{"ammo":100,"fuel":90,"maintenance":100,"munitions":{"count":4,"max":6,"type":"GMLRS rockets"}},"will_to_fight":"High","c2_status":"Nominal","detected_by":["BLUE-01"]},
            {"unit_id":"RED-1","name":"79th Motor Rifle Brigade","faction_id":"RED-01","type":"Mechanized Infantry","strength":"Degraded","location":{"lat":54.40,"lng":22.50},"status":"Advancing","supply":{"ammo":55,"fuel":60,"maintenance":65,"munitions":None},"will_to_fight":"Moderate","c2_status":"Nominal","detected_by":["RED-01","BLUE-01"]},
            {"unit_id":"RED-2","name":"7th Motor Rifle Regiment","faction_id":"RED-01","type":"Mechanized Infantry","strength":"Full","location":{"lat":54.50,"lng":22.30},"status":"Advancing","supply":{"ammo":80,"fuel":75,"maintenance":80,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["RED-01"]},
            {"unit_id":"RED-3","name":"244th Artillery Brigade","faction_id":"RED-01","type":"Artillery","strength":"Full","location":{"lat":54.72,"lng":21.95},"status":"Active","supply":{"ammo":75,"fuel":85,"maintenance":85,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["RED-01"]},
            {"unit_id":"RED-4","name":"EW Battalion","faction_id":"RED-01","type":"EW","strength":"Full","location":{"lat":54.68,"lng":22.10},"status":"Active","supply":{"ammo":100,"fuel":90,"maintenance":95,"munitions":None},"will_to_fight":"High","c2_status":"Nominal","detected_by":["RED-01"]}
        ],
        "controlled_terrain": [
            {"location_id":"Szypliszki Junction","controlling_faction":"RED-01"},
            {"location_id":"Route 8 km 0-15","controlling_faction":"RED-01"},
            {"location_id":"Route 8 km 15-40","controlling_faction":"BLUE-01"},
            {"location_id":"Suwalki town","controlling_faction":"BLUE-01"},
            {"location_id":"Augustow Forest (north)","controlling_faction":"Contested"}
        ]
    }
    session = models.GameSession(
        scenario_id=iron_wolf.id,
        title="IRON WOLF — DEMO SESSION",
        status="Active",
        current_turn=5,
        max_turns=8,
        time_per_turn_hours=9,
        faction_assignments=json.dumps([
            {"faction_id":"BLUE-01","user_id":None,"type":"Player"},
            {"faction_id":"RED-01","user_id":None,"type":"AI"}
        ]),
        current_game_state=json.dumps(game_state)
    )
    db.add(session)
    db.flush()

    turns = [
        {
            "turn_number": 1,
            "player_moves": [{"faction_id":"BLUE-01","moves":{"maneuver":[{"unit_id":"BLU-1","action":"Establish battle positions at Raczki Ridge, tie-in with BLU-2 on left flank"},{"unit_id":"BLU-2","action":"Occupy prepared defensive positions in Augustow Forest eastern edge"},{"unit_id":"BLU-4","action":"Screen forward, establish OP at Szypliszki junction"}],"fires":[{"target":"Known Russian assembly areas north of Goldap","system":"BLU-3 M109A7","effect":"Harassment and interdiction"}],"intelligence":[{"task":"Drone ISR along northern axis","asset":"RQ-7 Shadow"}],"logistics":[{"action":"Forward ammunition stockpile to Suwalki depot"}]},"submitted_at":"2026-03-15T04:00:00Z"}],
            "ai_moves": [{"faction_id":"RED-01","moves":{"intelligence_assessment":"NATO BCT appears to be in hasty defense with main effort at Raczki Ridge. Polish forces slower to deploy than expected. Northern Augustow axis appears lightly screened — possible gap between US and Polish units.","selected_coa":{"name":"WOLF FANG: Northern Envelopment","rationale":"Exploit gap between US and Polish forces in northern sector. Main effort through Augustow Forest will surprise NATO forces expecting frontal assault on Route 8.","risk":"Medium","actions":{"maneuver":[{"unit_id":"RED-1","action":"Probe along Route 8 with 1 BTG to fix NATO attention on southern axis","from_location":"Goldap assembly area","to_location":"South of Szypliszki junction"},{"unit_id":"RED-2","action":"Main effort: penetrate through Augustow Forest northern track toward Sejny","from_location":"Suvalkai border region","to_location":"Augustow Forest northern track"}],"fires":[{"target":"Raczki Ridge observation posts","system":"BM-21 Grad","effect":"Suppression and C2 disruption"},{"target":"Polish 15th Mech assembly area","system":"Iskander-M","effect":"Disruption and delay"}],"information_ops":[{"action":"Jam Polish military communications on 30-90MHz band"}]}},"commanders_intent":"Fix NATO on southern axis while main effort develops through northern Augustow track. Goal: reach Sejny by Turn 3, threatening to encircle Suwalki from north.","deception_plan":"Conspicuous movement of RED-1 on Route 8 to draw NATO attention and fires south while RED-2 moves quietly north"}}],
            "adjudication": {"narrative":"Turn 1 — H+00 to H+09 (0200-1100 local). NATO BCT executed a disciplined movement into prepared positions despite Russian electronic warfare degrading communications by 60%. The 1-68 Armor established excellent battle positions on Raczki Ridge with good observation northward. The 3-15 Infantry occupied forest positions with TOW teams covering likely vehicle approaches. CONTACT: Russian 79th MRB probe along Route 8 made contact with Polish 15th Mech screening elements at the Szypliszki junction at 0715. Polish forces executed a successful delay, inflicting 3 BTR kills before withdrawing to prepared positions. KEY EVENT: NATO HIMARS battery executed two GMLRS strikes on suspected Russian logistics nodes north of Goldap, destroying one ammunition truck and two fuel tankers. Russian electronic warfare successfully degraded NATO UAS operations — RQ-7 Shadow lost communications and returned to base without completing ISR task. NOTABLE: Russian main effort through Augustow Forest was not detected. Russian 7th Motor Rifle Regiment is moving quietly through forest tracks. First contact expected Turn 2-3.","decisive_moment":"Polish 15th Mech's disciplined delay at Szypliszki bought NATO 6 hours to complete defensive preparation","casualties":[{"faction_id":"RED-01","unit_id":"RED-1","strength_change":"Full→Degraded","cause":"HIMARS GMLRS strikes on logistics nodes, Blue defensive fires at Szypliszki"}],"terrain_changes":[{"location":"Szypliszki Junction","from_faction":"BLUE-01","to_faction":"RED-01"}],"score_changes":[{"faction_id":"BLUE-01","dimension":"Terrain control","change":5,"rationale":"Established strong defensive positions"},{"faction_id":"RED-01","dimension":"Terrain control","change":8,"rationale":"Seized Szypliszki junction; northern approach undetected"}],"key_events":["Russian 79th MRB probe along Route 8","Polish delay at Szypliszki successful","HIMARS strikes on Russian logistics","NATO UAS degraded by EW","Russian northern envelopment undetected"],"next_turn_conditions":"NATO in prepared positions along Raczki-Augustow line. Russian 7th MRR approaching Augustow Forest from north, undetected. Russian 79th MRB consolidating at Szypliszki. Weather: clear, -2°C."}
        },
        {
            "turn_number": 2,
            "player_moves": [{"faction_id":"BLUE-01","moves":{"maneuver":[{"unit_id":"BLU-1","action":"Hold Raczki Ridge positions; prepare alternate battle positions to rear"},{"unit_id":"BLU-2","action":"Extend right flank patrol to Augustow Forest northern track — intelligence suggests possible gap"},{"unit_id":"BLU-4","action":"Counter-attack to retake Szypliszki junction with 2 companies"}],"fires":[{"target":"Russian 79th MRB consolidation area at Szypliszki","system":"BLU-3 and BLU-5","effect":"Destroy in place; prevent reinforcement from Kaliningrad"}],"intelligence":[{"task":"Immediate ISR on Augustow Forest northern track — possible enemy movement"}],"c2":[{"action":"Request Polish Air Force F-16 CAS mission for Turn 3; request AWACS priority for northern sector"}]},"submitted_at":"2026-03-15T13:00:00Z"}],
            "ai_moves": [{"faction_id":"RED-01","moves":{"intelligence_assessment":"NATO fires were effectively targeted — Russian logistics at Goldap took significant damage. NATO is aware of Szypliszki junction loss and appears to be planning counter-attack. NATO ISR now looking at northern Augustow axis — main effort may be detected. Accelerate tempo.","selected_coa":{"name":"WOLF FANG ACCELERATE: Force NATO Decision","rationale":"Main effort through Augustow Forest must reach Phase Line KAUNAS before NATO can establish blocking position. Simultaneously, fix NATO reserves with escalated pressure on Raczki Ridge to prevent reorientation.","risk":"High","actions":{"maneuver":[{"unit_id":"RED-2","action":"Maximum speed advance: push 2 BTGs through Augustow Forest — accept road congestion for speed","from_location":"Augustow Forest entry"},{"unit_id":"RED-1","action":"Escalate to full regimental assault on Raczki Ridge — fix NATO armor, prevent reorientation north"},{"unit_id":"RED-5","action":"Belarusian 6th Mech: cross border at Lazdijai, threaten Sejny from east"}],"fires":[{"target":"Polish 15th Mech counter-attack force","system":"Iskander-M precision strike","effect":"Destroy counter-attack before it begins"},{"target":"HIMARS battery suspected location","system":"BM-21 Grad saturation","effect":"Suppress/destroy Blue precision fires"}]}},"commanders_intent":"Reach Sejny by end of Turn 3. This will create a 3-sided encirclement of Suwalki. Once Sejny is taken, Blue must either counterattack from a disadvantaged position or concede the Gap.","deception_plan":"Feed NATO with interceptable comms suggesting main effort is still Route 8; RED-2 maintains radio silence"}}],
            "adjudication": {"narrative":"Turn 2 — H+09 to H+18 (1100-2000 local). This was the critical turn. NATO's ISR mission to the northern Augustow axis arrived 3 hours too late — Russian 7th Motor Rifle Regiment had already cleared the forest track. At 1640, Russian BTG lead elements emerged from the Augustow Forest at Krasnopol, only 18km from Sejny, threatening to outflank the entire NATO defensive line. NATO 3-15 Infantry, executing its right flank extension, made unexpected contact with Russian forward security element at the forest exit. The engagement was intense: 3-15 Infantry stopped the Russian advance but took 22% casualties (Degraded). On the southern axis, the Polish 15th Mech counter-attack toward Szypliszki was struck by an Iskander-M precision missile, destroying 4 Leopard 2A5 tanks and killing 31 soldiers. The counter-attack was abandoned. Russian escalation on Raczki Ridge was costly: 1-68 Armor's thermal optics and battle position geometry gave NATO a 4:1 kill ratio in direct fire. Russian 79th MRB is now at Critical strength. KEY DECISION POINT: NATO commander now faces a choice — reinforce the northern axis at risk of thinning Raczki Ridge, or hold the southern line and accept Russian advance toward Sejny.","decisive_moment":"Russian 7th MRR emergence from Augustow Forest at Krasnopol — the scenario turning point","casualties":[{"faction_id":"BLUE-01","unit_id":"BLU-2","strength_change":"Full→Degraded","cause":"Forest contact with Russian 7th MRR forward security element"},{"faction_id":"RED-01","unit_id":"RED-1","strength_change":"Degraded→Critical","cause":"NATO 1-68 Armor battle position geometry, 4:1 kill ratio at Raczki Ridge"}],"terrain_changes":[{"location":"Augustow Forest northern exit","from_faction":"BLUE-01","to_faction":"Contested"},{"location":"Route 8 km 0-15","from_faction":"RED-01","to_faction":"RED-01"}],"score_changes":[{"faction_id":"BLUE-01","dimension":"Force preservation","change":-8,"rationale":"3-15 Infantry degraded; Polish counter-attack destroyed"},{"faction_id":"RED-01","dimension":"Terrain control","change":12,"rationale":"Achieved northern envelopment position; main effort in place"}],"key_events":["Russian 7th MRR emerges from Augustow Forest undetected","3-15 Infantry stops Russian advance but takes 22% casualties","Polish counter-attack destroyed by Iskander precision strike","Russian 79th MRB at Critical strength after Raczki Ridge combat"],"next_turn_conditions":"Critical juncture. Russian main effort is positioned to threaten Sejny. NATO must choose: reinforce north or hold south. Russian 79th MRB is combat-ineffective. Belarusian 6th Mech approaching Lazdijai border crossing. Darkness falling."}
        },
        {
            "turn_number": 3,
            "player_moves": [{"faction_id":"BLUE-01","moves":{"maneuver":[{"unit_id":"BLU-1","action":"Detach one company to reinforce 3-15 Infantry at Krasnopol; remainder holds Raczki Ridge"},{"unit_id":"BLU-4","action":"Polish 15th Mech pivots north — establish blocking position at Sejny before Russian arrival; abandon Route 8 counter-attack"}],"fires":[{"target":"Russian 7th MRR at Krasnopol before they can consolidate","system":"BLU-3 and BLU-5 simultaneous strike"},{"target":"Belarusian 6th Mech at Lazdijai crossing","system":"BLU-5 GMLRS — cannot allow third axis"}],"c2":[{"action":"Declare FRAGORD WOLFSBANE: northern axis is main effort — all CAS priority shifts north"}],"intelligence":[{"task":"Priority ISR on Belarusian 6th Mech — must confirm intentions"}]},"submitted_at":"2026-03-16T04:00:00Z"}],
            "ai_moves": [{"faction_id":"RED-01","moves":{"intelligence_assessment":"NATO has recognized the northern threat and is reorienting. Polish 15th Mech is moving toward Sejny. NATO fires capability remains high — HIMARS must be neutralized. Belarusian 6th Mech crossing at Lazdijai will fix Polish forces on third axis. Critical timing: must reach Sejny before Polish forces establish blocking position.","selected_coa":{"name":"RACE TO SEJNY","rationale":"Red force has a 4-6 hour window to seize Sejny before Polish blocking position is established. Maximum effort, accept losses. Simultaneously use Belarusian 6th Mech to force NATO to split attention.","risk":"High","actions":{"maneuver":[{"unit_id":"RED-2","action":"All-out advance to Sejny — 3 BTGs abreast, bypass Krasnopol contact, move through forest to avoid Blue fires"},{"unit_id":"RED-5","action":"Belarusian 6th Mech: cross at Lazdijai, advance toward Sejny from east — must be in position before Polish blocking force arrives"}],"fires":[{"target":"HIMARS battery suspected location (northeast of Suwalki)","system":"Iskander-M targeting based on SIGINT"},{"target":"Polish 15th Mech column on Route 8 northbound","system":"Ka-52 helicopter attack"}],"information_ops":[{"action":"Information operations: broadcast to Lithuanian media that Sejny has fallen (disinformation) to create panic and degrade NATO decision-making"}]}},"commanders_intent":"Seize Sejny in Turn 3. Hold in Turn 4-5 against NATO counter-attack. At this point, political pressure on NATO governments will be irresistible — the Gap will be de facto closed.","deception_plan":"Broadcast false Sejny seizure to accelerate panic and NATO political crisis"}}],
            "adjudication": {"narrative":"Turn 3 — H+18 to H+27 (2000-0500+1). The night battle for Sejny. Russian 7th MRR raced toward Sejny through darkness using thermal advantage and forest tracks. Polish 15th Mech was executing its northern pivot simultaneously. The two forces arrived at Sejny within 90 minutes of each other. HIMARS Battery A, responding to FRAGORD WOLFSBANE, executed a 6-round GMLRS strike on Russian 7th MRR lead elements 8km south of Sejny, destroying 14 vehicles and halting the advance for 2 hours. This bought Polish 15th Mech time to establish a hasty blocking position on Sejny's northern edge. Russian Ka-52 helicopters, launched to strike the Polish column, were engaged by Polish SHORAD — 2 Ka-52s shot down, 1 damaged. Ka-52 attack mission aborted. The Iskander-M strike targeting HIMARS: 1 of 6 HIMARS vehicles destroyed (HIMARS battery now Degraded). Belarusian 6th Mech crossed at Lazdijai and is 25km from Sejny — major new threat. STALEMATE AT SEJNY: Both sides hold portions of Sejny — brutal urban fighting through night. Red does not control the town. Blue narrowly prevented Russian breakthrough.","decisive_moment":"HIMARS 6-round GMLRS strike south of Sejny — bought 2 hours that allowed Polish 15th Mech to establish blocking position","casualties":[{"faction_id":"RED-01","unit_id":"RED-2","strength_change":"Full→Degraded","cause":"HIMARS precision strike, Polish SHORAD vs Ka-52s"},{"faction_id":"BLUE-01","unit_id":"BLU-5","strength_change":"Full→Degraded","cause":"Iskander-M strike — 1 of 6 HIMARS vehicles destroyed"}],"terrain_changes":[{"location":"Sejny town","from_faction":"BLUE-01","to_faction":"Contested"}],"score_changes":[{"faction_id":"BLUE-01","dimension":"Objective achievement","change":15,"rationale":"Narrowly prevented Sejny seizure — turning point held"},{"faction_id":"RED-01","dimension":"Objective achievement","change":-5,"rationale":"Failed to seize Sejny — timeline now untenable for 72-hour objective"}],"key_events":["HIMARS precision strike halts Russian advance 8km from Sejny","Polish 15th Mech establishes blocking position — narrow margin","Ka-52 attack aborted after 2 aircraft shot down","Belarusian 6th Mech crosses at Lazdijai — new threat axis","Both sides hold portions of Sejny — contested town"],"next_turn_conditions":"Sejny contested. Russian main effort stalled but not broken. Belarusian 6th Mech is 3 turns from Sejny. NATO HIMARS degraded but operational. Russian window is closing. 33 hours remain in scenario."}
        },
        {
            "turn_number": 4,
            "player_moves": [{"faction_id":"BLUE-01","moves":{"maneuver":[{"unit_id":"BLU-1","action":"Full tank battalion + BLU-2 remnant: limited counterattack to clear Russian forces from Sejny urban area"},{"unit_id":"BLU-4","action":"Hold northern Sejny blocking position; prepare for Belarusian 6th Mech approach from east"}],"fires":[{"target":"Belarusian 6th Mech column on approach to Sejny","system":"BLU-5 GMLRS (remaining 4 launchers)"},{"target":"Russian logistics node at Augustow Forest exit — cut off 7th MRR resupply","system":"BLU-3 M109A7 Excalibur"}],"c2":[{"action":"Request 82nd Airborne early arrival — political channels activated (inject INJ-04 triggered)"}],"intelligence":[{"task":"All ISR on Belarusian 6th Mech — confirm combat power and ETA to Sejny"}]},"submitted_at":"2026-03-16T13:00:00Z"}],
            "ai_moves": [{"faction_id":"RED-01","moves":{"intelligence_assessment":"The 72-hour objective window is closing. Russian 7th MRR is degraded and stalled in Sejny. Blue counterattack is underway. Belarusian 6th Mech is 3 hours from Sejny but approaching into an HIMARS threat environment. Risk calculation: continuation is high cost with reducing probability of success. Recommend consolidate and hold — force NATO into costly counterattack while protecting Red main effort force.","selected_coa":{"name":"IRON WALL: Defensive Consolidation","rationale":"Offensive culminated at Sejny. Shift to defensive consolidation: hold gains (Szypliszki junction, northern Route 8 corridor, Sejny portions), wait for Belarusian reinforcement, and grind NATO counterattack to a halt with fires and EW.","risk":"Medium","actions":{"maneuver":[{"unit_id":"RED-2","action":"Consolidate in southern Sejny; establish strong anti-armor positions; prepare for NATO counterattack"},{"unit_id":"RED-5","action":"Belarusian 6th Mech: advance to within 10km of Sejny, but do NOT enter city until Russian fires can suppress HIMARS"}],"fires":[{"target":"NATO counterattack force (1-68 Armor approaching Sejny)","system":"All available artillery — saturation fire to halt counterattack"}],"logistics":[{"action":"Emergency fuel and ammunition resupply to RED-2 at Sejny — current logistics state 30% only"}]}},"commanders_intent":"Hold Sejny partial control for 2 more turns. Even partial Sejny control creates a political crisis for NATO — Polish, Lithuanian governments demanding immediate NATO Article 5 response, creating paralysis. The political effect is achieved even if military position is imperfect.","deception_plan":"Publicly claim Sejny is fully under Russian control — force NATO leadership to respond to information rather than ground truth; delay their counterattack decision"}}],
            "adjudication": {"narrative":"Turn 4 — H+27 to H+36 (0500-1400). The counterattack. NATO 1-68 Armor, reinforced by 3-15 Infantry survivors, launched a coordinated counterattack into southern Sejny at first light. The attack made good initial progress — Abrams thermal sights gave a decisive advantage in the urban dawn. Three Russian T-72 tanks were destroyed in the first 45 minutes, and NATO forces cleared 60% of the urban area. RUSSIAN FIRE RESPONSE: Russian artillery, massed by RED-3 in Kaliningrad, executed a 2,000-round barrage on the NATO counterattack avenue of approach. Heavy casualties: 1-68 Armor took 18% casualties (remaining Full strength by narrow margin). Three M2 Bradley vehicles were destroyed. The barrage did not stop the counterattack but significantly slowed it. BELARUSIAN HALT: HIMARS GMLRS strikes on Belarusian 6th Mech approach routes destroyed 11 vehicles and temporarily halted the column 12km east of Sejny. Belarusian forces reversed and sought concealment — they have not crossed the kill zone. ENDSTATE: NATO controls 75% of Sejny, Russian forces control southern 25% and a neighborhood around the rail station. Route 8 north of Suwalki is contested. Russian 7th MRR is at Critical strength. 36 hours remain.","decisive_moment":"NATO 1-68 Armor uses thermal advantage to clear 60% of Sejny despite Russian artillery barrage — offensive momentum shifts","casualties":[{"faction_id":"BLUE-01","unit_id":"BLU-1","strength_change":"Full→Degraded","cause":"Russian massed artillery barrage during counterattack — 18% casualties, 3 Bradleys destroyed"},{"faction_id":"RED-01","unit_id":"RED-2","strength_change":"Degraded→Critical","cause":"NATO urban counterattack with thermal advantage, HIMARS logistics interdiction"}],"terrain_changes":[{"location":"Sejny town","from_faction":"Contested","to_faction":"Contested"},{"location":"Route 8 km 15-40","from_faction":"BLUE-01","to_faction":"Contested"}],"score_changes":[{"faction_id":"BLUE-01","dimension":"Objective achievement","change":10,"rationale":"75% Sejny cleared; Route 8 mostly open"},{"faction_id":"RED-01","dimension":"Force preservation","change":-8,"rationale":"7th MRR at Critical strength; Belarusian 6th Mech halted by HIMARS"}],"key_events":["NATO urban counterattack clears 75% of Sejny","Russian 2,000-round artillery barrage inflicts NATO casualties but fails to stop attack","HIMARS halts Belarusian 6th Mech 12km east of Sejny","Russian 7th MRR at Critical strength — offensive combat power exhausted","36 hours remain in scenario — Turn 5 begins"],"next_turn_conditions":"NATO holds initiative. Sejny 75% clear. Russian offensive stalled. Belarusian threat remains. NATO 1-68 Armor Degraded but operational. HIMARS at 2 effective launchers. 82nd Airborne lead element arriving Vilnius in 12 hours. Russian 7th MRR cannot sustain further offensive action."},
            "game_master_notes": "Excellent player decision-making in Turn 3 — FRAGORD WOLFSBANE and HIMARS prioritization was the key call. The narrow Sejny hold (2-hour window) demonstrates the value of precision fires in shaping the operational environment. For Turn 5, recommend introducing INJ-04 (82nd Airborne) and consider whether Russia will attempt political negotiations given deteriorating military position. Red AI should shift from Aggressive to Attrition-focused personality."
        }
    ]

    for t in turns:
        db.add(models.TurnLog(
            session_id=session.id,
            turn_number=t["turn_number"],
            player_moves=json.dumps(t["player_moves"]),
            ai_moves=json.dumps(t["ai_moves"]),
            adjudication=json.dumps(t["adjudication"]),
            injects_triggered=json.dumps([]),
            game_master_notes=t.get("game_master_notes")
        ))

    # Monte Carlo results
    mc_results = {
        "simulation_runs": [
            {"run_id":1,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Standard","friction_level":"Moderate"},"narrative":"NATO BCT successfully delays Russian advance through combined arms defense. Russian northern envelopment is detected in Turn 2 due to better ISR. HIMARS strikes degrade Russian logistics sustainably. By Turn 6, Russian offensive has culminated and 82nd Airborne arrival tips the balance definitively. NATO holds the Gap.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":True,"red_achieves_primary":False,"dominant_factor":"Early detection of Russian northern envelopment"}},
            {"run_id":2,"assumptions":{"weather":"Fog","intelligence_quality":"Poor","logistics":"Smooth","political_constraints":"Standard","friction_level":"High"},"narrative":"Fog and EW combine to blind NATO ISR. Russian 7th MRR reaches Sejny undetected by Turn 2. With Sejny fallen, Route 8 is severed by Turn 4. Political crisis: Lithuania requests ceasefire. NATO fails primary objective.","outcome":{"blue_achieves_primary":False,"blue_achieves_secondary":False,"red_achieves_primary":True,"dominant_factor":"Intelligence failure in fog conditions"}},
            {"run_id":3,"assumptions":{"weather":"Clear","intelligence_quality":"Excellent","logistics":"Smooth","political_constraints":"Tight"},"narrative":"Excellent NATO ISR detects Russian northern envelopment in Turn 1. Blue redirects Polish 15th Mech immediately. However, tight political constraints prevent pre-emptive HIMARS strikes. Russian advance slows but eventually reaches Sejny contested by Turn 4. NATO holds — barely.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":False,"red_achieves_primary":False,"dominant_factor":"Early detection offset by ROE restrictions"}},
            {"run_id":4,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Critical failure","political_constraints":"Standard","friction_level":"Moderate"},"narrative":"HIMARS resupply convoy is struck by Iskander in Turn 2. Blue precision fires unavailable from Turn 3. Without HIMARS, Russia reaches Sejny unconstrained. Route 8 falls by Turn 5. Logistics failure was decisive.","outcome":{"blue_achieves_primary":False,"blue_achieves_secondary":False,"red_achieves_primary":True,"dominant_factor":"HIMARS logistics failure"}},
            {"run_id":5,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Standard","friction_level":"Low"},"narrative":"Low friction scenario. NATO defensive scheme works as planned. Russian probe at Szypliszki repulsed. Northern envelopment detected by enhanced ISR. Sejny never threatened. NATO wins decisively by Turn 6 with 82nd Airborne arrival.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":True,"red_achieves_primary":False,"dominant_factor":"Low friction allowed NATO plan to execute as designed"}},
            {"run_id":6,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Standard","friction_level":"Moderate"},"narrative":"Scenario similar to demo session. Narrow NATO hold at Sejny. HIMARS proves decisive. Russian offensive culminates at Turn 4. Partial Russian success in capturing Route 8 junction but Gap not closed.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":False,"red_achieves_primary":False,"dominant_factor":"HIMARS precision fires and Polish 15th Mech reorientation"}},
            {"run_id":7,"assumptions":{"weather":"Severe","intelligence_quality":"Poor","logistics":"Strained","political_constraints":"Tight","friction_level":"Very High"},"narrative":"Perfect storm: severe weather grounds all air, EW degrades comms, logistics strained from Turn 2. Russian advance exploits chaos. Belarusian 6th Mech completes encirclement. Suwalki isolated by Turn 6. Catastrophic Blue failure.","outcome":{"blue_achieves_primary":False,"blue_achieves_secondary":False,"red_achieves_primary":True,"dominant_factor":"Compound friction overwhelmed NATO C2 and logistics"}},
            {"run_id":8,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Loosened","friction_level":"Moderate"},"narrative":"Political constraints loosened — NATO authorized pre-emptive HIMARS strikes on Russian assembly areas in Kaliningrad border region (within legal interpretation). Russian logistics crippled before Turn 2. Northern envelopment stalls. NATO decisive victory.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":True,"red_achieves_primary":False,"dominant_factor":"Pre-emptive deep fires on Russian logistics"}},
            {"run_id":9,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Standard","friction_level":"Moderate"},"narrative":"Russia prioritizes Belarusian 6th Mech over Augustow envelopment. Three-axis attack overwhelms NATO defenders. Polish 15th Mech cannot cover two axes. Gap taken by Turn 5.","outcome":{"blue_achieves_primary":False,"blue_achieves_secondary":True,"red_achieves_primary":True,"dominant_factor":"Russian three-axis attack exceeds NATO covering force capacity"}},
            {"run_id":10,"assumptions":{"weather":"Clear","intelligence_quality":"Adequate","logistics":"Smooth","political_constraints":"Standard","friction_level":"Moderate"},"narrative":"Blue concentrates fires on Russian artillery brigade in Turn 2, eliminating massed indirect fire capability. Russian maneuver forces advance without fire support and take 40%+ casualties at Raczki Ridge. Russian offensive collapses by Turn 4.","outcome":{"blue_achieves_primary":True,"blue_achieves_secondary":True,"red_achieves_primary":False,"dominant_factor":"Counter-battery fires eliminating Russian indirect fire capability"}}
        ],
        "aggregate": {
            "outcome_probabilities": [
                {"scenario_outcome":"NATO holds Gap — Blue primary objective achieved","probability_pct":50,"description":"Blue successfully defends Route 8 corridor for full 72 hours"},
                {"scenario_outcome":"Russian partial success — Sejny contested, Route 8 threatened","probability_pct":25,"description":"Russian advance reaches Sejny but does not close the Gap"},
                {"scenario_outcome":"Russian breakthrough — Gap closed","probability_pct":25,"description":"Russia achieves primary objective: Gap physically severed"}
            ],
            "key_decision_points": [
                {"turn":1,"decision":"ISR prioritization: southern Route 8 vs. northern Augustow axis","impact_rating":"Critical","appears_in_runs":9,"rationale":"Appears in 9 of 10 simulations as the decisive early decision. Detection of northern envelopment in Turn 1 vs Turn 2 changes outcome in 4 simulations."},
                {"turn":2,"decision":"FRAGORD commitment: reinforce north (abandon Route 8 counter) vs. continue Route 8 plan","impact_rating":"Critical","appears_in_runs":8,"rationale":"The moment NATO recognizes the main effort has shifted. Players who adapted early held Sejny; those who continued Route 8 focus lost it."},
                {"turn":3,"decision":"HIMARS target prioritization: Russian 7th MRR at Sejny vs. Belarusian 6th Mech approach","impact_rating":"High","appears_in_runs":7,"rationale":"HIMARS fires are the decisive enabling capability. Target prioritization in Turn 3 determines whether Russia can achieve Sejny or whether Belarusian axis is neutralized."},
                {"turn":4,"decision":"Whether to launch counterattack to clear Sejny vs. consolidate and wait for 82nd Airborne","impact_rating":"High","appears_in_runs":6,"rationale":"Aggressive counterattack risks casualties but reestablishes control; waiting for reinforcement is lower risk but cedes time."}
            ],
            "risk_factors": [
                {"factor":"NATO ISR degraded by Russian EW — northern envelopment undetected","impact":"High","frequency":"Common","mitigation":"Dedicate UAS to northern Augustow axis from Turn 1; assume EW will degrade comms and plan for degraded ops"},
                {"factor":"HIMARS logistics vulnerability to Iskander precision strike","impact":"High","frequency":"Occasional","mitigation":"Disperse HIMARS after each mission; use satellite-based logistics tracking to harden resupply routes; pre-position ammunition forward"},
                {"factor":"Belarusian 6th Mech third-axis attack overwhelming NATO covering force capacity","impact":"High","frequency":"Occasional","mitigation":"Designate HIMARS priority to Belarusian approach routes; use Polish territorial forces to screen eastern axis"},
                {"factor":"Compound friction (weather + EW + logistics) overwhelming NATO C2","impact":"High","frequency":"Rare","mitigation":"Practice degraded comms procedures; pre-plan Phase Lines that work without real-time C2"},
                {"factor":"Political constraints preventing pre-emptive fires on Russian assembly areas","impact":"Medium","frequency":"Common","mitigation":"Pre-coordinate fires authorities with higher HQ before scenario begins; establish decision thresholds in OPORD"}
            ],
            "sensitivity_findings": "The scenario outcome is most sensitive to two factors: (1) NATO ISR quality and the speed of detecting the Russian northern envelopment, and (2) HIMARS availability — in all 5 Blue-win simulations, HIMARS executed at least 2 effective precision strike missions. The scenario is relatively insensitive to weather and political constraints individually, but highly sensitive to their combination. The Belarusian 6th Mech axis, while threatening, appears in only 2 decisive outcomes — it is a shaping force, not the main effort.",
            "most_likely_narrative": "The most likely outcome (50% probability) is a narrow NATO defensive success. Russia detects a gap between US and Polish forces and attempts a northern envelopment through the Augustow Forest. NATO detects this in Turn 2 (not Turn 1 — EW prevents earlier detection) and executes a hasty reorientation with Polish 15th Mech. HIMARS provides decisive precision fires that slow the Russian advance. A tense fight for Sejny results in NATO controlling 70%+ of the town by Turn 4. Russian offensive culminates by Turn 5 as logistics fail. 82nd Airborne arrival stabilizes the situation. Route 8 remains open — barely. Blue takes 25-35% casualties; Red takes 45-55%. The political aftermath is severe: Baltic states demand permanent reinforcement; Russia claims partial success in demonstrating NATO's inability to rapidly defend the Gap.",
            "best_case_narrative": "In the optimistic scenario (20% probability): NATO ISR detects the Russian northern envelopment in Turn 1. Polish 15th Mech pivots immediately. HIMARS executes a devastating Turn 1 strike on Russian logistics in the Goldap assembly area, crippling Red's sustainment from the start. The Russian 7th MRR reaches Sejny but is immediately defeated by the combination of Polish blocking position and HIMARS fires. Russian offensive culminates by Turn 3. NATO counterattacks to restore Szypliszki junction by Turn 5. Blue takes less than 15% casualties; Red is at 60% casualties. The scenario ends with a clear NATO tactical victory and a demonstration that the Gap can be defended.",
            "worst_case_narrative": "In the pessimistic scenario (15% probability): A perfect storm of fog, Russian EW success, and logistics friction blinds NATO and degrades C2 from Turn 1. Russian northern envelopment reaches Sejny by Turn 2 before detection. Blue FRAGORD WOLFSBANE comes too late. Belarusian 6th Mech completes eastern encirclement of Suwalki by Turn 5. Route 8 is physically severed. Lithuanian land connection to NATO is cut. Political shock triggers an emergency NATO summit but military reality cannot be reversed in the remaining turns. Russian objective achieved at Turn 6. Baltic states isolated. This outcome, while 15% probability, has the highest strategic consequence of any scenario result.",
            "analytical_bottom_line": "IRON WOLF is a 'knife's edge' scenario: the outcome hinges on two narrow decisions (ISR prioritization in Turn 1 and HIMARS targeting in Turn 3) and one random variable (weather/friction). The 50/25/25 outcome distribution reflects real military uncertainty. NATO's defensive position is strong IF intelligence functions and precision fires are preserved. The scenario's key lesson: NATO's defensive advantage is enabled by technology (HIMARS, thermal optics, ISR) and degraded by Russian electronic warfare. The human element — the speed and quality of Blue decision-making — is the single most impactful variable."
        }
    }

    mc = models.MonteCarloResult(
        session_id=session.id,
        scenario_id=iron_wolf.id,
        results=json.dumps(mc_results)
    )
    db.add(mc)

    # Partial AAR (sections 1-3)
    partial_aar = {
        "metadata": {"exercise_title":"IRON WOLF: Defense of the Suwalki Gap","classification":"UNCLASSIFIED","date_generated":"2026-03-17","scenario_type":"Tactical","duration_turns":4,"participants":["Blue: NATO Combined Arms Force (Player-controlled)","Red: Russian 11th Army Corps (AI-controlled, Aggressive personality)","White: Game Master"]},
        "section_1_executive_summary": {
            "scenario_overview": "A 72-hour tactical scenario modeling NATO brigade-level defense of the Suwalki Gap against a Russian mechanized assault from Kaliningrad. The Blue player controlled NATO 4/3 ABCT augmented with Polish 15th Mechanized Brigade. Red was AI-controlled with Aggressive personality. Four turns (36 hours) have been played.",
            "outcome": "ONGOING — Turn 4 of 8 complete. NATO currently holds Suwalki and 75% of Sejny. Route 8 contested in northern sector. Russian offensive has culminated but not collapsed. Score: Blue 77 / Red 43. Blue leads but outcome is not decided.",
            "key_findings": [
                {"finding_number":1,"finding":"The Russian northern envelopment through Augustow Forest was the decisive operational maneuver, not the expected frontal assault on Route 8. NATO detection lag of 9 hours (Turn 1 vs Turn 2) nearly allowed Route 8 to be severed.","confidence":"High","significance":"Critical"},
                {"finding_number":2,"finding":"HIMARS precision fires were the single most decisive Blue capability, enabling 3 turning-point events: halting Russian logistics in Turn 1, stopping the Russian 7th MRR advance in Turn 3, and halting Belarusian 6th Mech in Turn 4.","confidence":"High","significance":"Critical"},
                {"finding_number":3,"finding":"Russian electronic warfare degraded NATO ISR and communications by 60% from Turn 1, preventing detection of the northern envelopment until direct contact was made. Blue was fighting blind in a critical window.","confidence":"High","significance":"Important"},
                {"finding_number":4,"finding":"The Polish 15th Mech Brigade's rapid reorientation from Route 8 to Sejny (FRAGORD WOLFSBANE, Turn 3) was the single best Blue decision of the game, executed 2 hours before Russian forces arrived at Sejny.","confidence":"High","significance":"Critical"},
                {"finding_number":5,"finding":"Russian Iskander-M precision strikes are a game-changing capability: destroying 4 Polish Leopard 2A5 tanks in a single strike (Turn 2) and neutralizing 1 HIMARS launcher (Turn 3). Blue had no effective counter to Iskander during the exercise.","confidence":"High","significance":"Important"}
            ],
            "bottom_line_up_front": "IRON WOLF demonstrates that the Suwalki Gap can be defended at brigade level IF NATO achieves early detection of Russian axis of advance and preserves precision fires capability. The margin is narrow: 2 hours between Russian 7th MRR and Polish 15th Mech at Sejny. The scenario validates three key insights: (1) EW degradation of ISR is a critical vulnerability; (2) HIMARS/precision fires are an asymmetric enabler that Russia must neutralize first; (3) the Suwalki-Sejny axis is the decisive terrain, not Route 8."
        },
        "section_2_chronological_narrative": {
            "phase_narratives": [
                {"phase":"Phase 1: Opening Moves and Deception (Turn 1, H+00 to H+09)","narrative":"NATO BCT executed a disciplined movement to prepared defensive positions despite Russian electronic warfare degrading communications across the Gap region. The Russian opening move was a classic deception operation: a conspicuous probe along Route 8 (the expected axis) masked the main effort — the 7th Motor Rifle Regiment moving silently through the Augustow Forest. NATO's RQ-7 Shadow ISR mission to the northern axis was degraded by Russian EW and returned without actionable intelligence. HIMARS executed two precision strikes on Russian logistics north of Goldap, setting the conditions for Russian sustainment problems in later turns.","decisive_moments":["Polish 15th Mech successful delay at Szypliszki junction","HIMARS logistics strikes north of Goldap","Russian 7th MRR enters Augustow Forest undetected"],"turning_point":None},
                {"phase":"Phase 2: Main Effort Revelation and Crisis (Turn 2, H+09 to H+18)","narrative":"The scenario's turning point. Russian 7th MRR emerged from the Augustow Forest at Krasnopol, completely surprising NATO. The 3-15 Infantry, conducting its right-flank extension patrol, made unexpected contact and stopped the Russian advance — but took 22% casualties (Degraded status) and was combat-limited for subsequent turns. Simultaneously, a Russian Iskander-M precision strike destroyed 4 Polish Leopard 2A5 tanks and 31 soldiers, eliminating the Polish counter-attack that would have retaken Szypliszki. On the southern axis, Russian 79th MRB was effectively destroyed by 1-68 Armor's battle position geometry — 4:1 kill ratio in direct fire. The scenario bifurcated: Red's northern envelopment was succeeding; Red's Route 8 assault was failing. The game's decisive decision point arrived: NATO commander must reorient north or continue south.","decisive_moments":["Russian 7th MRR emerges from forest at Krasnopol","3-15 Infantry stops Russian advance but takes 22% casualties","Polish counter-attack destroyed by Iskander precision strike","1-68 Armor achieves 4:1 kill ratio on Raczki Ridge"],"turning_point":"Russian 7th MRR emergence from Augustow Forest — the scenario's operational surprise"},
                {"phase":"Phase 3: The Race to Sejny (Turn 3, H+18 to H+27)","narrative":"The night battle. NATO issued FRAGORD WOLFSBANE, identifying the northern axis as the new main effort and shifting all fire support priority. Russian 7th MRR raced toward Sejny through darkness; Polish 15th Mech pivoted north simultaneously. HIMARS executed a 6-round GMLRS strike 8km south of Sejny, halting the Russian advance for exactly 2 hours — the time Polish 15th Mech needed to establish a blocking position on Sejny's northern edge. The margin was as narrow as any operation in modern wargaming: 2 hours. Russian Ka-52 helicopters attempted to strike the Polish column but were engaged by SHORAD — 2 Ka-52s shot down. The Belarusian 6th Mech crossed the border at Lazdijai, opening a third axis. Sejny became contested.","decisive_moments":["FRAGORD WOLFSBANE — Blue recognizes main effort shift","HIMARS 6-round GMLRS strike halts Russian advance 8km from Sejny","Polish 15th Mech arrives at Sejny 2 hours before Russian advance resumes","Belarusian 6th Mech crosses at Lazdijai — new axis opens"],"turning_point":"HIMARS precision strike buying 2 hours for Polish blocking position establishment"},
                {"phase":"Phase 4: Counterattack and Consolidation (Turn 4, H+27 to H+36)","narrative":"NATO seized the initiative. 1-68 Armor, reinforced by 3-15 Infantry survivors, launched a dawn counterattack into Sejny. Thermal optics provided decisive advantage in urban fighting — 3 Russian T-72 tanks destroyed in first 45 minutes, 60% of Sejny cleared. Russian massed artillery (2,000 rounds) slowed but did not stop the counterattack. HIMARS strikes halted Belarusian 6th Mech 12km east of Sejny. The Russian offensive had culminated: 7th MRR at Critical strength, 79th MRB combat-ineffective. 36 hours remain in the scenario.","decisive_moments":["NATO dawn counterattack clears 60% of Sejny using thermal advantage","Russian 2,000-round barrage slows but cannot stop NATO counterattack","HIMARS halts Belarusian 6th Mech 12km from Sejny","Russian offensive culmination — Red switches to Defensive posture"],"turning_point":"NATO counterattack clearing Sejny — Blue regains initiative after Turn 3 crisis"}
            ],
            "overall_flow": "The game has followed a classic 'deeper than expected' Russian deep-battle penetration attempt, defeated by precise NATO fires and rapid decision-making. The scenario has moved through 3 distinct phases: (1) initial contact and deception; (2) crisis and near-breakthrough; (3) stabilization and counterattack. With 4 turns remaining, Blue holds the advantage but has consumed significant combat power. The 82nd Airborne arrival in 2 turns may prove decisive — if Russia cannot achieve its political objective before that reinforcement arrives."
        },
        "section_3_blue_force_analysis": {
            "coa_assessment": "Blue's initial COA (layered defense on Route 8 with economy of force in north) was doctrinally sound but insufficiently flexible to account for Russian deception. The decision to allocate only a screening force to the northern axis reflected conventional threat assessment and was the root cause of the Turn 2 crisis. The COA was adequate for a frontal assault but inadequate for the sophisticated envelopment executed by Red.",
            "execution_quality": "Despite the initial intelligence failure, Blue execution quality was generally high once the main effort was identified. FRAGORD WOLFSBANE was issued rapidly; Polish 15th Mech executed the reorientation under contact; HIMARS fires were well-timed and precisely targeted. The counterattack in Turn 4 demonstrated excellent combined arms integration. Blue's execution recovered effectively from the Turn 2 crisis.",
            "key_decisions": [
                {"turn":1,"decision":"ISR prioritization — allocated RQ-7 Shadow to general surveillance rather than northern Augustow axis specifically","assessment":"Poor","rationale":"The northern axis was the most dangerous avenue of approach and should have received priority ISR from Turn 1.","alternative":"Dedicate RQ-7 to Augustow Forest northern track; use ground OPs to observe Route 8"},
                {"turn":2,"decision":"FRAGORD WOLFSBANE — abandoning Route 8 counter-attack to reorient north","assessment":"Excellent","rationale":"Rapid recognition of the changed main effort threat; decisive reorientation under pressure; accepted risk on southern axis to address decisive threat.","alternative":"None better — this was the correct decision at the correct time"},
                {"turn":3,"decision":"HIMARS target priority — Russian 7th MRR vs. Belarusian 6th Mech","assessment":"Good","rationale":"Correctly identified that 7th MRR was the immediate threat to Sejny; Belarusian 6th Mech could be engaged later. GMLRS strike timing was excellent.","alternative":"Counter-battery fire on Russian artillery brigade could have reduced the massed fires threat that would materialize in Turn 4"},
                {"turn":4,"decision":"Immediate counterattack to clear Sejny vs. consolidate and wait for 82nd Airborne","assessment":"Acceptable","rationale":"Aggressive decision that recovered initiative and cleared most of Sejny. Risk was accepted appropriately.","alternative":"Waiting 1 turn for 82nd Airborne reinforcement before counterattacking would have reduced casualties and potentially achieved more decisive Sejny clearance"}
            ],
            "logistics_sustainment": "Blue logistics performance was adequate but under stress. HIMARS resupply convoy was threatened by Iskander strike in Turn 3 — one launcher destroyed. M109A7 ammunition consumption was high in Turns 2-4; without Turn 5 resupply, fires capability will be severely degraded. The decision to pre-position ammunition at Suwalki depot (Turn 1) proved essential. Recommend: establish a second ammunition cache at Sejny now that it is being cleared.",
            "information_operations": "Blue information operations were essentially absent. Red's disinformation campaign (false claim that Sejny had fallen) created 4 hours of decision paralysis in Blue's Turn 3. Recommendation: establish a dedicated IO response cell with the authority to rapidly counter Red disinformation; pre-coordinate with Lithuanian and Polish media channels.",
            "overall_grade": "Above Average"
        }
    }

    aar = models.AARReport(
        session_id=session.id,
        content=json.dumps(partial_aar),
        share_token="demo-iron-wolf-aar-2026"
    )
    db.add(aar)
    db.commit()

if __name__ == "__main__":
    seed()
