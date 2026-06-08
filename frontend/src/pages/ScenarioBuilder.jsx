import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { scenariosApi, sessionsApi } from '../api/client'
import { AIThinking } from '../components/LoadingSpinner'
import { StatusBadge, SideChip } from '../components/StatusBadge'
import OperationalMap from '../components/OperationalMap'
import {
  Wand2, Save, Play, ChevronDown, ChevronRight, Zap, AlertCircle, Info,
  Shield, Clock, CloudRain, Truck, TrendingUp,
  Users, AlertTriangle, CheckCircle, XCircle,
} from 'lucide-react'

const EXAMPLE_PROMPTS = [
  "NATO brigade defends the Suwalki Gap against Russian mechanized assault, 72-hour scenario, 2026",
  "Iranian IRGC asymmetric response to US strike on nuclear facility, 30-day strategic scenario",
  "Israeli airstrikes against Syria, 14-day air campaign with ground component",
  "North Korea conventional attack across DMZ, 72-hour tactical scenario"
]

const ASSUMPTION_BADGES = {
  'Permissive': 'badge badge-blue',
  'Standard': 'badge badge-active',
  'Restrictive': 'badge badge-paused',
  'Escalation-Limited': 'badge badge-red',
  'Excellent': 'badge badge-active',
  'Good': 'badge badge-active',
  'Adequate': 'badge badge-paused',
  'Poor': 'badge badge-red',
  'Denied': 'badge badge-red',
  'Clear': 'badge badge-active',
  'Degraded': 'badge badge-paused',
  'Severe': 'badge badge-red',
  'Robust': 'badge badge-active',
  'Strained': 'badge badge-paused',
  'Critical': 'badge badge-red',
  'None': 'badge badge-active',
  'Moderate': 'badge badge-paused',
  'Extreme': 'badge badge-red',
  'Conventional-only': 'badge badge-active',
  'Theater-nuclear-threshold': 'badge badge-paused',
  'Full-spectrum': 'badge badge-red',
  'Full': 'badge badge-active',
  'Partial': 'badge badge-paused',
  'Symbolic': 'badge badge-red',
}

function AssumptionBadge({ value }) {
  if (!value) return null
  const cls = ASSUMPTION_BADGES[value] || 'badge badge-paused'
  return <span className={cls}>{value}</span>
}

function PlanningAssumptionsCard({ assumptions }) {
  const [open, setOpen] = useState(false)
  if (!assumptions || Object.keys(assumptions).length === 0) return null

  const allied = assumptions.allied_involvement || {}
  const allies = allied.allies || []

  return (
    <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-3 hover:bg-theater-bg/50 transition-colors"
      >
        <h3 className="text-theater-text font-semibold text-sm font-mono flex items-center gap-2">
          <Shield className="w-4 h-4 text-theater-accent-light" />
          PLANNING ASSUMPTIONS
        </h3>
        {open ? <ChevronDown className="w-4 h-4 text-theater-muted" /> : <ChevronRight className="w-4 h-4 text-theater-muted" />}
      </button>

      {open && (
        <div className="border-t border-theater-border p-4 space-y-3 text-xs">
          {/* Allied Involvement */}
          <div>
            <p className="text-theater-muted font-mono tracking-wider mb-2 flex items-center gap-2">
              <Users className="w-3.5 h-3.5" /> Allied Involvement
              {allied.enabled
                ? <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                : <XCircle className="w-3.5 h-3.5 text-theater-muted" />}
            </p>
            {allied.enabled && allies.length > 0 ? (
              <div className="space-y-2">
                {allies.map((ally, i) => (
                  <div key={i} className="border border-theater-border/50 rounded p-2 bg-theater-bg/50">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-theater-text font-semibold">{ally.nation}</span>
                      <div className="flex items-center gap-1">
                        <AssumptionBadge value={ally.commitment_level} />
                        {ally.arrival_turn > 0 && (
                          <span className="font-mono text-theater-accent-light">Turn {ally.arrival_turn}</span>
                        )}
                      </div>
                    </div>
                    {ally.forces_description && (
                      <p className="text-theater-gray">{ally.forces_description}</p>
                    )}
                    {ally.conditions_for_entry && (
                      <p className="text-theater-muted mt-1 italic">Entry: {ally.conditions_for_entry}</p>
                    )}
                    {ally.arrival_description && (
                      <p className="text-theater-gray mt-1">{ally.arrival_description}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-theater-muted">No allied involvement</p>
            )}
          </div>

          {/* Constraint grid */}
          <div className="grid grid-cols-2 gap-3">
            {assumptions.rules_of_engagement && (
              <div>
                <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                  <Shield className="w-3 h-3" /> Rules of Engagement
                </p>
                <AssumptionBadge value={assumptions.rules_of_engagement} />
              </div>
            )}
            {assumptions.intelligence_quality && (
              <div>
                <p className="text-theater-muted font-mono mb-1">Intelligence Quality</p>
                <AssumptionBadge value={assumptions.intelligence_quality} />
              </div>
            )}
            {assumptions.weather_conditions && (
              <div>
                <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                  <CloudRain className="w-3 h-3" /> Weather
                </p>
                <AssumptionBadge value={assumptions.weather_conditions} />
              </div>
            )}
            {assumptions.logistics_posture && (
              <div>
                <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                  <Truck className="w-3 h-3" /> Logistics Posture
                </p>
                <AssumptionBadge value={assumptions.logistics_posture} />
              </div>
            )}
            {assumptions.time_pressure && (
              <div>
                <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Time Pressure
                </p>
                <AssumptionBadge value={assumptions.time_pressure} />
              </div>
            )}
            {assumptions.escalation_ceiling && (
              <div>
                <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" /> Escalation Ceiling
                </p>
                <AssumptionBadge value={assumptions.escalation_ceiling} />
              </div>
            )}
            {assumptions.reinforcement_policy && (
              <div>
                <p className="text-theater-muted font-mono mb-1">Reinforcement Policy</p>
                <span className="text-theater-gray">{assumptions.reinforcement_policy}</span>
              </div>
            )}
          </div>

          {/* Political Constraints */}
          {assumptions.political_constraints && (
            <div>
              <p className="text-theater-muted font-mono mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Political Constraints
              </p>
              <p className="text-theater-gray leading-relaxed">{assumptions.political_constraints}</p>
            </div>
          )}

          {/* Designer Notes */}
          {assumptions.designer_notes && (
            <div>
              <p className="text-theater-muted font-mono mb-1">Designer Notes</p>
              <p className="text-theater-gray leading-relaxed italic">{assumptions.designer_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FactionCard({ faction, expanded, onToggle }) {
  const units = faction.order_of_battle?.units || []
  return (
    <div className="border border-theater-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 bg-theater-card hover:bg-theater-card transition-colors"
      >
        <div className="flex items-center gap-3">
          <SideChip side={faction.side} />
          <span className="text-theater-text font-medium text-sm">{faction.name}</span>
          <StatusBadge status={faction.role} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-theater-muted text-xs font-mono">{units.length} units</span>
          {expanded ? <ChevronDown className="w-4 h-4 text-theater-muted" /> : <ChevronRight className="w-4 h-4 text-theater-muted" />}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-theater-border p-3 bg-theater-bg space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-theater-muted text-xs font-mono mb-1">Primary Objective</p>
              <p className="text-theater-gray text-xs">{faction.objective_primary}</p>
            </div>
            <div>
              <p className="text-theater-muted text-xs font-mono mb-1">Posture</p>
              <p className="text-theater-gray text-xs">{faction.starting_posture}</p>
            </div>
          </div>
          {faction.ai_personality && (
            <div>
              <p className="text-theater-muted text-xs font-mono mb-1">AI Personality</p>
              <span className="badge badge-red">{faction.ai_personality}</span>
            </div>
          )}
          {units.length > 0 && (
            <div>
              <p className="text-theater-muted text-xs font-mono mb-2">Order of Battle ({units.length} units)</p>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {units.map(u => (
                  <div key={u.unit_id} className="flex items-center justify-between text-xs py-1 border-b border-theater-border/50">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-theater-muted">{u.unit_id}</span>
                      <span className="text-theater-gray">{u.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-theater-muted">{u.echelon}</span>
                      <span className={u.strength === 'Full' ? 'strength-full' : u.strength === 'Degraded' ? 'strength-degraded' : 'strength-critical'}>
                        {u.strength}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {faction.victory_conditions?.length > 0 && (
            <div>
              <p className="text-theater-muted text-xs font-mono mb-2">Victory Conditions</p>
              {faction.victory_conditions.map((vc, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1">
                  <span className="text-theater-gray flex-1 pr-4">{vc.condition}</span>
                  <span className="font-mono text-theater-accent-light">{vc.weight_pct}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ScenarioBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()

  // Main flow
  const [step, setStep] = useState(id ? 'edit' : 'input')

  // Scenario state
  const [prompt, setPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [scenario, setScenario] = useState(null)
  const [error, setError] = useState('')
  const [expandedFactions, setExpandedFactions] = useState({})
  const [mapUnits, setMapUnits] = useState([])

  useEffect(() => {
    if (id) {
      scenariosApi.get(id).then(r => {
        setScenario(r.data)
        setStep('edit')
        buildMapUnits(r.data)
      })
    }
  }, [id])

  const buildMapUnits = (sc) => {
    if (!sc?.factions) return
    const units = []
    sc.factions.forEach(faction => {
      (faction.order_of_battle?.units || []).forEach(u => {
        if (u.location?.lat) units.push({ ...u, faction_id: faction.faction_id })
      })
    })
    setMapUnits(units)
  }

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setGenerating(true)
    setError('')
    try {
      const res = await scenariosApi.generate(prompt)
      const sc = res.data.scenario
      setScenario(sc)
      setStep('edit')
      buildMapUnits(sc)
    } catch (e) {
      setError(e.response?.data?.detail || 'Generation failed. Check your API key and try again.')
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        title: scenario.title,
        scenario_type: scenario.scenario_type,
        timeframe: scenario.timeframe,
        geography: scenario.geography || {},
        situation: scenario.situation || {},
        factions: scenario.factions || [],
        injects: scenario.injects || [],
        win_conditions: scenario.win_conditions || {},
        ai_notes: scenario.ai_notes || '',
        is_template: false
      }
      let res
      if (id) {
        res = await scenariosApi.update(id, payload)
      } else {
        res = await scenariosApi.create(payload)
      }
      navigate(`/scenarios/${res.data.id}/edit`)
    } catch (e) {
      setError(e.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleLaunch = async () => {
    if (!id && !scenario) return
    const scenarioId = id || (await scenariosApi.create({
      title: scenario.title, scenario_type: scenario.scenario_type,
      timeframe: scenario.timeframe, geography: scenario.geography || {},
      situation: scenario.situation || {}, factions: scenario.factions || [],
      injects: scenario.injects || [], win_conditions: scenario.win_conditions || {},
      ai_notes: scenario.ai_notes || '', is_template: false
    })).data.id

    const res = await sessionsApi.create({
      scenario_id: scenarioId,
      title: scenario?.title || 'New Session',
      max_turns: scenario?.win_conditions?.duration_turns || 6,
      time_per_turn_hours: 0,  // backend auto-derives from scenario timeframe
      faction_assignments: []
    })
    navigate(`/sessions/${res.data.id}`)
  }

  const toggleFaction = (fid) => setExpandedFactions(p => ({ ...p, [fid]: !p[fid] }))

  // ── Loading states ─────────────────────────────────────────────────────────
  if (generating) return <AIThinking label="Theater is building your scenario..." />

  // ── Step 1: Input ──────────────────────────────────────────────────────────
  if (step === 'input') return (
    <div className="p-6 max-w-3xl mx-auto fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
          <Wand2 className="w-6 h-6 text-theater-accent-light" />
          Scenario Builder
        </h1>
        <p className="text-theater-muted text-sm mt-1">Generate your scenario using AI</p>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-theater-red text-sm bg-red-50 border border-red-200 rounded p-3 mb-4">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold">Error</p>
            <p className="text-xs mt-0.5 text-red-300">{error}</p>
          </div>
        </div>
      )}

      {/* ── Theater Generate ── */}
      <div className="space-y-4">
        <div className="bg-theater-card border border-theater-border rounded-lg p-6 space-y-4">
          <div>
            <label className="block text-xs font-mono text-theater-gray tracking-wider mb-2">
              Scenario Description
            </label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              rows={5}
              placeholder="Describe your wargaming scenario in plain English. Include: the forces involved, geographic location, timeframe, and the core conflict or decision point you want to explore..."
              className="w-full bg-theater-bg border border-theater-border rounded p-3 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors resize-none font-mono leading-relaxed"
            />
          </div>
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim()}
            className="w-full flex items-center justify-center gap-2 bg-theater-accent hover:bg-theater-accent-light disabled:opacity-40 disabled:cursor-not-allowed text-white py-3 rounded font-mono font-semibold tracking-wider transition-colors"
          >
            <Zap className="w-4 h-4" />
            Generate Scenario with Theater
          </button>
        </div>

        <div>
          <p className="text-theater-muted text-xs font-mono tracking-wider mb-3 flex items-center gap-2">
            <Info className="w-3.5 h-3.5" /> Example prompts
          </p>
          <div className="space-y-2">
            {EXAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setPrompt(p)}
                className="w-full text-left text-theater-gray text-xs p-3 bg-theater-card border border-theater-border rounded hover:border-theater-accent/30 hover:text-theater-text transition-all font-mono leading-relaxed"
              >
                "{p}"
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )

  // ── Step 2: Edit ───────────────────────────────────────────────────────────
  if (!scenario) return null
  const factions = scenario.factions || []
  const planningAssumptions = scenario.situation?.planning_assumptions
  const mapCenter = mapUnits.length > 0
    ? [mapUnits[0].location.lat, mapUnits[0].location.lng]
    : [54.1, 22.9]

  return (
    <div className="h-full flex flex-col fade-in">
      {/* Toolbar */}
      <div className="flex-shrink-0 bg-theater-card border-b border-theater-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-theater-text font-semibold font-mono tracking-wider">{scenario.title}</h2>
          <StatusBadge status={scenario.scenario_type} />
          <span className="text-theater-muted text-xs font-mono">{scenario.timeframe}</span>
        </div>
        <div className="flex items-center gap-2">
          {!id && (
            <button onClick={() => setStep('input')} className="text-theater-gray text-xs font-mono hover:text-theater-text transition-colors px-3 py-1.5">
              ← Back
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text px-4 py-1.5 rounded text-xs font-mono transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            onClick={handleLaunch}
            className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-4 py-1.5 rounded text-xs font-mono font-semibold transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            Launch Session
          </button>
        </div>
      </div>

      {error && (
        <div className="flex-shrink-0 flex items-center gap-2 text-theater-red text-xs bg-red-950/40 border-b border-red-900/40 px-6 py-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="flex-1 overflow-hidden flex">
        {/* Left panel: scenario details */}
        <div className="w-1/2 overflow-y-auto p-4 space-y-4 border-r border-theater-border">
          {/* Situation */}
          <div className="bg-theater-card border border-theater-border rounded-lg p-4">
            <h3 className="text-theater-text font-semibold text-sm font-mono mb-3">SITUATION</h3>
            {scenario.situation?.background && (
              <p className="text-theater-gray text-xs leading-relaxed mb-3">{scenario.situation.background}</p>
            )}
            {scenario.situation?.precipitating_event && (
              <>
                <p className="text-theater-muted text-xs font-mono tracking-wider mb-1">Precipitating Event</p>
                <p className="text-theater-gray text-xs leading-relaxed mb-3">{scenario.situation.precipitating_event}</p>
              </>
            )}
            {scenario.situation?.current_situation && (
              <>
                <p className="text-theater-muted text-xs font-mono tracking-wider mb-1">Current Situation</p>
                <p className="text-theater-gray text-xs leading-relaxed">{scenario.situation.current_situation}</p>
              </>
            )}
          </div>

          {/* Geography */}
          {scenario.geography && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-semibold text-sm font-mono mb-3">Geography</h3>
              <p className="text-theater-gray text-xs mb-3">{scenario.geography.region}</p>
              {scenario.geography.key_terrain?.length > 0 && (
                <div className="space-y-1">
                  {scenario.geography.key_terrain.map((t, i) => (
                    <div key={i} className="text-xs text-theater-muted font-mono">• {t}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Planning Assumptions */}
          <PlanningAssumptionsCard assumptions={planningAssumptions} />

          {/* Factions & OOB */}
          <div className="space-y-2">
            <h3 className="text-theater-text font-semibold text-sm font-mono">Order of Battle ({factions.length} factions)</h3>
            {factions.map(f => (
              <FactionCard
                key={f.faction_id}
                faction={f}
                expanded={!!expandedFactions[f.faction_id]}
                onToggle={() => toggleFaction(f.faction_id)}
              />
            ))}
          </div>

          {/* Injects */}
          {scenario.injects?.length > 0 && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-semibold text-sm font-mono mb-3">
                INJECTS ({scenario.injects.length})
              </h3>
              <div className="space-y-3">
                {scenario.injects.map(inj => (
                  <div key={inj.inject_id} className="border border-theater-border/50 rounded p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-theater-muted text-xs">{inj.inject_id}</span>
                      <div className="flex items-center gap-2">
                        <span className="badge badge-paused">{inj.type}</span>
                        <span className="text-theater-muted text-xs font-mono">Turn {inj.turn_trigger}</span>
                      </div>
                    </div>
                    <p className="text-theater-gray text-xs leading-relaxed">{inj.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Notes */}
          {scenario.ai_notes && (
            <div className="bg-theater-accent/5 border border-theater-accent/20 rounded-lg p-4">
              <h3 className="text-theater-accent-light font-semibold text-sm font-mono mb-2 flex items-center gap-2">
                <Zap className="w-4 h-4" /> Designer Notes
              </h3>
              <p className="text-theater-gray text-xs leading-relaxed">{scenario.ai_notes}</p>
            </div>
          )}
        </div>

        {/* Right panel: map */}
        <div className="w-1/2 relative">
          <div className="absolute top-3 left-3 right-3 z-10">
            <div className="bg-theater-card/80 backdrop-blur border border-theater-border rounded p-2 flex items-center justify-between">
              <span className="text-theater-muted text-xs font-mono">Operational Map — Unit Starting Positions</span>
              <span className="text-theater-accent-light text-xs font-mono">{mapUnits.length} units plotted</span>
            </div>
          </div>
          <OperationalMap
            units={mapUnits}
            factions={factions}
            center={mapCenter}
            zoom={7}
            height="100%"
          />
        </div>
      </div>

    </div>
  )
}
