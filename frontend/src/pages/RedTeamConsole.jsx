import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sessionsApi, scenariosApi, redTeamApi } from '../api/client'
import { LoadingSpinner, AIThinking } from '../components/LoadingSpinner'
import { SideChip, StatusBadge } from '../components/StatusBadge'
import { Zap, ArrowLeft, Shield, AlertCircle, ChevronDown, Settings } from 'lucide-react'

const PERSONALITIES = ['Aggressive', 'Cautious', 'Opportunistic', 'Deceptive', 'Attrition-focused']

function COACard({ coa, selected, onSelect }) {
  const [open, setOpen] = useState(selected)
  const riskColor = { Low: 'text-theater-green', Medium: 'text-yellow-700', High: 'text-theater-red' }
  return (
    <div
      className={`border rounded-lg overflow-hidden cursor-pointer transition-all ${
        selected ? 'border-theater-accent bg-theater-accent/5' : 'border-theater-border hover:border-theater-accent/30'
      }`}
      onClick={() => { setOpen(p => !p); onSelect?.() }}
    >
      <div className="flex items-center justify-between p-3 bg-theater-card">
        <div className="flex items-center gap-3">
          {selected && <span className="w-2 h-2 rounded-full bg-theater-accent-light flex-shrink-0" />}
          <span className="text-theater-text font-mono font-semibold text-sm">{coa.coa_name || coa.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`font-mono text-xs ${riskColor[coa.risk] || 'text-theater-gray'}`}>
            Risk: {coa.risk}
          </span>
          <ChevronDown className={`w-4 h-4 text-theater-muted transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </div>
      {open && (
        <div className="border-t border-theater-border p-3 text-xs text-theater-gray leading-relaxed space-y-2">
          <p>{coa.description || coa.rationale}</p>
          {coa.pros?.length > 0 && (
            <div>
              <p className="text-theater-green font-mono mb-1">Pros:</p>
              {coa.pros.map((p, i) => <p key={i}>+ {p}</p>)}
            </div>
          )}
          {coa.cons?.length > 0 && (
            <div>
              <p className="text-theater-red font-mono mb-1">Cons:</p>
              {coa.cons.map((c, i) => <p key={i}>- {c}</p>)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ActionTable({ label, items, color }) {
  if (!items?.length) return null
  return (
    <div>
      <p className={`font-mono text-xs tracking-wider mb-2 ${color}`}>{label}</p>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="text-xs text-theater-gray bg-theater-bg border border-theater-border/50 rounded p-2 leading-relaxed">
            {item.unit_id && <span className="font-mono text-theater-muted mr-2">[{item.unit_id}]</span>}
            {item.action || item.collection_task || item.target || item.action}
            {item.rationale && <span className="text-theater-muted ml-2">— {item.rationale}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RedTeamConsole() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [scenario, setScenario] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [selectedFaction, setSelectedFaction] = useState(null)
  const [injectText, setInjectText] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    sessionsApi.get(id).then(r => {
      setSession(r.data)
      return r.data
    }).then(s => {
      if (s.scenario_id) {
        scenariosApi.get(s.scenario_id).then(r => {
          setScenario(r.data)
          const aiFactions = (r.data.factions || []).filter(f => f.role === 'AI-controlled')
          if (aiFactions.length > 0) setSelectedFaction(aiFactions[0])
        })
      }
    }).finally(() => setLoading(false))
  }, [id])

  const aiFactions = (scenario?.factions || []).filter(f => f.role === 'AI-controlled')

  const [aiDone, setAiDone] = useState(false)

  const handleGenerate = async () => {
    if (!selectedFaction) return
    setGenerating(true)
    setAiDone(false)
    setError('')
    setAiResult(null)
    try {
      const curLog = session.turn_logs?.find(t => t.turn_number === session.current_turn)
      const res = await redTeamApi.generateMoves(id, {
        faction_id: selectedFaction.faction_id,
        player_moves: curLog?.player_moves || [],
        injects: injectText ? [{ description: injectText, type: 'Event' }] : []
      })
      setAiResult(res.data.moves)
      setAiDone(true)
      await sessionsApi.get(id).then(r => setSession(r.data))
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setGenerating(false)
    }
  }

  const handlePersonalityChange = async (personality) => {
    if (!selectedFaction) return
    try {
      await redTeamApi.updatePersonality(id, { faction_id: selectedFaction.faction_id, personality })
      setSelectedFaction(f => ({ ...f, ai_personality: personality }))
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <LoadingSpinner />
  if (generating) return <AIThinking label={`${selectedFaction?.name || 'Red'} commander is planning...`} />

  return (
    <div className="p-6 fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(`/sessions/${id}`)} className="text-theater-muted hover:text-theater-text transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <Shield className="w-6 h-6 text-theater-red" />
            Red Team Console
          </h1>
          <p className="text-theater-muted text-sm">{session?.title} — Turn {session?.current_turn}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls */}
        <div className="space-y-4">
          {/* Faction selector */}
          <div className="bg-theater-card border border-theater-border rounded-lg p-4">
            <h3 className="text-theater-text font-mono font-semibold text-sm mb-3 flex items-center gap-2">
              <Settings className="w-4 h-4 text-theater-muted" /> AI Faction
            </h3>
            <div className="space-y-2">
              {aiFactions.map(f => (
                <button
                  key={f.faction_id}
                  onClick={() => setSelectedFaction(f)}
                  className={`w-full flex items-center gap-2 p-2 rounded border transition-all ${
                    selectedFaction?.faction_id === f.faction_id
                      ? 'border-theater-red/40 bg-theater-red/10'
                      : 'border-theater-border hover:border-theater-red/20'
                  }`}
                >
                  <SideChip side={f.side} />
                  <span className="text-theater-text text-xs font-mono">{f.name?.substring(0, 30)}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Personality */}
          {selectedFaction && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-3">AI Personality</h3>
              <div className="space-y-1.5">
                {PERSONALITIES.map(p => (
                  <button
                    key={p}
                    onClick={() => handlePersonalityChange(p)}
                    className={`w-full text-left px-3 py-2 rounded text-xs font-mono transition-all ${
                      selectedFaction.ai_personality === p
                        ? 'bg-theater-red/20 text-theater-red border border-theater-red/30'
                        : 'text-theater-gray border border-theater-border hover:border-theater-red/20 hover:text-theater-text'
                    }`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Manual inject */}
          <div className="bg-theater-card border border-theater-border rounded-lg p-4">
            <h3 className="text-theater-text font-mono font-semibold text-sm mb-3">MANUAL INJECT</h3>
            <textarea
              value={injectText}
              onChange={e => setInjectText(e.target.value)}
              rows={3}
              placeholder="Inject an event, intelligence report, or friction event that the AI commander should account for..."
              className="w-full bg-theater-bg border border-theater-border rounded p-2 text-theater-text text-xs font-mono resize-none focus:outline-none focus:border-theater-accent transition-colors"
            />
          </div>

          <button
            onClick={handleGenerate}
            disabled={!selectedFaction}
            className="w-full flex items-center justify-center gap-2 bg-theater-red/80 hover:bg-theater-red disabled:opacity-40 text-theater-text py-3 rounded font-mono font-semibold tracking-wider transition-colors"
          >
            <Zap className="w-4 h-4" />
            GENERATE AI MOVES
          </button>

          {aiDone && !error && (
            <div className="flex items-center gap-2 text-theater-green text-xs bg-green-900/20 border border-theater-green/30 rounded p-3 font-mono">
              <span className="inline-block w-2 h-2 rounded-full bg-theater-green flex-shrink-0" />
              AI moves generated. Return to the game session to adjudicate.
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 text-theater-red text-xs bg-red-50 border border-red-200 rounded p-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {error}
            </div>
          )}
        </div>

        {/* AI output */}
        <div className="lg:col-span-2 space-y-4">
          {!aiResult && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-8 text-center">
              <Shield className="w-10 h-10 text-theater-muted mx-auto mb-3" />
              <p className="text-theater-gray font-mono">Select a faction and generate AI moves to see the Red commander's plan</p>
            </div>
          )}

          {aiResult && (
            <>
              {/* Intel assessment */}
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h3 className="text-theater-red font-mono font-semibold text-sm mb-3">INTELLIGENCE ASSESSMENT</h3>
                <p className="text-theater-gray text-xs leading-relaxed">{aiResult.intelligence_assessment}</p>
              </div>

              {/* COAs */}
              {aiResult.coa_development?.length > 0 && (
                <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                  <h3 className="text-theater-text font-mono font-semibold text-sm mb-3">
                    COURSES OF ACTION ({aiResult.coa_development.length})
                  </h3>
                  <div className="space-y-2">
                    {aiResult.coa_development.map((coa, i) => (
                      <COACard key={i} coa={coa} selected={aiResult.selected_coa?.name === (coa.coa_name || coa.name)} />
                    ))}
                  </div>
                </div>
              )}

              {/* Selected COA actions */}
              {aiResult.selected_coa && (
                <div className="bg-red-50 border border-theater-red/30 rounded-lg p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-theater-red font-mono font-semibold text-sm">
                      Selected COA: {aiResult.selected_coa.name}
                    </h3>
                    <StatusBadge status={aiResult.selected_coa.risk === 'High' ? 'Red' : 'Degraded'} />
                  </div>
                  <p className="text-theater-gray text-xs leading-relaxed">{aiResult.selected_coa.rationale}</p>

                  {aiResult.selected_coa.actions && (
                    <div className="space-y-3">
                      <ActionTable label="Maneuver" items={aiResult.selected_coa.actions.maneuver} color="text-theater-blue" />
                      <ActionTable label="Fires" items={aiResult.selected_coa.actions.fires} color="text-theater-red" />
                      <ActionTable label="Intelligence" items={aiResult.selected_coa.actions.intelligence} color="text-yellow-700" />
                      <ActionTable label="Logistics" items={aiResult.selected_coa.actions.logistics} color="text-theater-green" />
                      <ActionTable label="Information Ops" items={aiResult.selected_coa.actions.information_ops} color="text-purple-400" />
                      <ActionTable label="C2" items={aiResult.selected_coa.actions.c2} color="text-theater-gray" />
                    </div>
                  )}
                </div>
              )}

              {/* Commander's intent and deception */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                  <h3 className="text-theater-text font-mono font-semibold text-xs mb-2">COMMANDER'S INTENT</h3>
                  <p className="text-theater-gray text-xs leading-relaxed">{aiResult.commanders_intent}</p>
                </div>
                <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                  <h3 className="text-theater-muted font-mono font-semibold text-xs mb-2">DECEPTION PLAN</h3>
                  <p className="text-theater-gray text-xs leading-relaxed italic">{aiResult.deception_plan}</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
