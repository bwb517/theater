import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sessionsApi, redTeamApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge, SideChip, StrengthBar } from '../components/StatusBadge'
import OperationalMap from '../components/OperationalMap'
import OrdersForm, { blankOrder } from '../components/OrdersForm'
import TurnDiffPanel from '../components/TurnDiffPanel'
import { Map, Send, ScrollText, Eye, Trophy, ChevronDown, AlertCircle, Zap, SkipForward, X, Trash2, RotateCcw, Flag, Navigation, Target } from 'lucide-react'

// Derive current turn workflow phase from session state
function derivePhase(session) {
  if (!session || session.status === 'Complete') return 'complete'
  const curLog = session.turn_logs?.find(t => t.turn_number === session.current_turn)
  if (!curLog || curLog.adjudication) return 'player'
  if (curLog.ai_moves?.length > 0) return 'adjudicate'
  if (curLog.player_moves?.length > 0) return 'red_ai'
  return 'player'
}

const PHASE_META = {
  player:     { label: 'PHASE 1 — BLUE ORDERS', sub: 'Add orders in the Moves tab, then submit.', color: 'border-theater-blue/50 text-theater-blue bg-blue-900/10' },
  red_ai:     { label: 'PHASE 2 — RUN AI ADVERSARY', sub: 'Orders submitted. Run the Red AI to generate adversary moves.', color: 'border-theater-red/50 text-theater-red bg-red-900/10' },
  adjudicate: { label: 'PHASE 3 — ADJUDICATE TURN', sub: 'Red force orders ready. Adjudicate to resolve the turn and advance.', color: 'border-theater-green/50 text-theater-green bg-green-900/10' },
  complete:   { label: 'SESSION COMPLETE', sub: 'The game has ended. Generate an AAR to review the results.', color: 'border-theater-muted text-theater-muted bg-theater-card' },
}

const TABS = [
  { id: 'map', label: 'Map', icon: Map },
  { id: 'moves', label: 'Moves', icon: Send },
  { id: 'log', label: 'Turn Log', icon: ScrollText },
  { id: 'intel', label: 'Intel', icon: Eye },
  { id: 'scores', label: 'Scores', icon: Trophy },
]

function TurnEntry({ turn, onViewDiff }) {
  const [open, setOpen] = useState(false)
  const adj = turn.adjudication || {}
  return (
    <div className="border border-theater-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between p-3 bg-theater-card hover:bg-theater-card transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-theater-accent-light text-sm font-bold">Turn {turn.turn_number}</span>
          {adj.decisive_moment && (
            <span className="text-theater-gray text-xs hidden md:block">· {adj.decisive_moment?.substring(0, 60)}...</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {adj.narrative && onViewDiff && (
            <span
              onClick={e => { e.stopPropagation(); onViewDiff(adj, turn.turn_number) }}
              className="text-xs font-mono text-theater-accent-light border border-theater-accent/30 hover:bg-theater-accent/10 px-2 py-0.5 rounded transition-colors"
            >
              DIFF
            </span>
          )}
          <ChevronDown className={`w-4 h-4 text-theater-muted transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {open && (
        <div className="border-t border-theater-border p-4 bg-theater-bg space-y-4">
          {/* Blue moves */}
          {turn.player_moves?.length > 0 && (
            <div>
              <p className="text-theater-blue font-mono text-xs tracking-wider mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-sm bg-theater-blue" /> Blue Force Actions
              </p>
              {turn.player_moves.map((m, i) => (
                <div key={i} className="text-xs bg-blue-50 border border-blue-200 rounded p-3 mb-2">
                  <p className="font-mono text-theater-blue mb-1">{m.faction_id}</p>
                  {m.moves?.maneuver?.map((mv, j) => (
                    <p key={j} className="text-theater-gray">• [MANEUVER] {mv.action || mv.unit_id}</p>
                  ))}
                  {m.moves?.fires?.map((f, j) => (
                    <p key={j} className="text-theater-gray">• [FIRES] {f.target} — {f.system}</p>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Red moves */}
          {turn.ai_moves?.length > 0 && (
            <div>
              <p className="text-theater-red font-mono text-xs tracking-wider mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-sm bg-theater-red" /> Red Force Actions (AI)
              </p>
              {turn.ai_moves.map((m, i) => {
                const mv = m.moves || {}
                const sel = mv.selected_coa || {}
                return (
                  <div key={i} className="text-xs bg-red-50 border border-red-200 rounded p-3 mb-2">
                    <p className="font-mono text-theater-red mb-2">{mv.intelligence_assessment?.substring(0, 200)}...</p>
                    <p className="font-semibold text-theater-text mb-1">COA: {sel.name}</p>
                    <p className="text-theater-gray">{sel.rationale?.substring(0, 200)}</p>
                  </div>
                )
              })}
            </div>
          )}

          {/* Adjudication */}
          {adj.narrative && (
            <div>
              <p className="text-theater-green font-mono text-xs tracking-wider mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-sm bg-theater-green" /> Adjudication
              </p>
              <div className="bg-theater-card border border-theater-border rounded p-3">
                <p className="text-theater-gray text-xs leading-relaxed">{adj.narrative}</p>
                {adj.decisive_moment && (
                  <div className="mt-3 pt-3 border-t border-theater-border">
                    <p className="text-yellow-700 text-xs font-mono">⚡ DECISIVE MOMENT: {adj.decisive_moment}</p>
                  </div>
                )}
                {adj.key_events?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-theater-border">
                    <p className="text-theater-muted text-xs font-mono mb-2">Key Events:</p>
                    {adj.key_events.map((e, i) => (
                      <p key={i} className="text-theater-gray text-xs">• {e}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {turn.game_master_notes && (
            <div>
              <p className="text-yellow-600 font-mono text-xs tracking-wider mb-1">GM Notes</p>
              <p className="text-theater-gray text-xs italic">{turn.game_master_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function GameSession() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [scenario, setScenario] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('map')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [adjudicating, setAdjudicating] = useState(false)
  const [error, setError] = useState('')

  // Structured orders (shared between map panel and Moves tab)
  const [pendingOrders, setPendingOrders] = useState([])
  const [pendingOrdersHistory, setPendingOrdersHistory] = useState([])
  const pendingOrdersRef = useRef([])
  useEffect(() => { pendingOrdersRef.current = pendingOrders }, [pendingOrders])

  // Turn phase tracking
  const [turnPhase, setTurnPhase] = useState('player')

  // Red AI done notification
  const [redAIDone, setRedAIDone] = useState(false)

  // Capitulate confirmation
  const [showCapitulateConfirm, setShowCapitulateConfirm] = useState(false)

  // Map interactivity
  const [selectedMapUnit, setSelectedMapUnit] = useState(null)
  const [pickingDest, setPickingDest] = useState(false)
  const [pickingOrderId, setPickingOrderId] = useState(null)
  const [pickingFiresTarget, setPickingFiresTarget] = useState(false)
  const [pickingFiresOrderId, setPickingFiresOrderId] = useState(null)
  const [rightClickMenu, setRightClickMenu] = useState(null) // { lat, lng, screenX, screenY }

  // Session overflow menu (kebab)
  const [showSessionMenu, setShowSessionMenu] = useState(false)

  // Previous turn ghost overlay on map
  const [showPreviousPositions, setShowPreviousPositions] = useState(false)

  // Turn diff panel
  const [diffData, setDiffData] = useState(null)
  const [showDiff, setShowDiff] = useState(false)

  // Units highlighted on map after adjudication
  const [highlightedUnits, setHighlightedUnits] = useState([])

  // Wrapped orders setter that tracks history for undo (only when order count changes)
  const setOrdersTracked = useCallback((updater) => {
    const prev = pendingOrdersRef.current
    const next = typeof updater === 'function' ? updater(prev) : updater
    if (next.length !== prev.length) {
      setPendingOrdersHistory(h => [...h.slice(-19), prev])
    }
    setPendingOrders(next)
  }, [])

  const handleUndo = useCallback(() => {
    setPendingOrdersHistory(h => {
      if (h.length === 0) return h
      setPendingOrders(h[h.length - 1])
      return h.slice(0, -1)
    })
  }, [])

  const refresh = () => sessionsApi.get(id).then(r => {
    setSession(r.data)
    setTurnPhase(derivePhase(r.data))
    return r.data
  })

  async function handleDelete() {
    if (!window.confirm(`Delete "${session?.title}"? All turn logs, AAR reports, and Monte Carlo results will be permanently removed.`)) return
    await sessionsApi.delete(id)
    navigate('/')
  }

  // Dismiss session overflow menu on outside click
  useEffect(() => {
    if (!showSessionMenu) return
    const close = () => setShowSessionMenu(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [showSessionMenu])

  // Cancel destination-pick mode with Escape
  useEffect(() => {
    if (!pickingDest) return
    const handler = (e) => { if (e.key === 'Escape') { setPickingDest(false); setPickingOrderId(null) } }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [pickingDest])

  // Dismiss right-click context menu on outside click or Escape.
  // Must use 'click' (not 'mousedown') so the menu button's own onClick fires first;
  // mousedown unmounts the menu before click, preventing the button handler from running.
  useEffect(() => {
    if (!rightClickMenu) return
    const handleKey = (e) => { if (e.key === 'Escape') setRightClickMenu(null) }
    const handleClick = () => setRightClickMenu(null)
    window.addEventListener('keydown', handleKey)
    window.addEventListener('click', handleClick)
    return () => {
      window.removeEventListener('keydown', handleKey)
      window.removeEventListener('click', handleClick)
    }
  }, [rightClickMenu])

  // Ctrl+Z / Cmd+Z to undo pending orders
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !pickingDest) {
        e.preventDefault()
        handleUndo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleUndo, pickingDest])

  useEffect(() => {
    refresh().then(s => {
      if (s.scenario_id) {
        import('../api/client').then(({ scenariosApi }) =>
          scenariosApi.get(s.scenario_id).then(r => setScenario(r.data))
        )
      }
    }).finally(() => setLoading(false))
  }, [id])

  const handleRunAI = async () => {
    setAiGenerating(true)
    setRedAIDone(false)
    setError('')
    try {
      const sc = scenario
      const aiFactions = (sc?.factions || []).filter(f => f.role === 'AI-controlled')
      const curLog = session.turn_logs?.find(t => t.turn_number === session.current_turn)
      const playerMoves = curLog?.player_moves || []

      for (const faction of aiFactions) {
        await redTeamApi.generateMoves(id, {
          faction_id: faction.faction_id,
          player_moves: playerMoves,
          injects: []
        })
      }
      await refresh()
      setRedAIDone(true)
      setTurnPhase('adjudicate')
    } catch (e) {
      setError('AI generation failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setAiGenerating(false)
    }
  }

  const handleAdjudicate = async () => {
    if (!window.confirm(`Adjudicate Turn ${session.current_turn} and advance? This cannot be undone.`)) return
    setAdjudicating(true)
    setError('')
    try {
      const curLog = session.turn_logs?.find(t => t.turn_number === session.current_turn)
      const adjRes = await redTeamApi.adjudicate(id, {
        turn_number: session.current_turn,
        blue_moves: curLog?.player_moves || [],
        red_moves: curLog?.ai_moves || []
      })
      await sessionsApi.advanceTurn(id)
      await refresh()

      // Show diff panel and highlight affected units
      const adj = adjRes.data.adjudication
      if (adj) {
        setDiffData(adj)
        setShowDiff(true)
        setHighlightedUnits((adj.casualties || []).map(c => c.unit_id).filter(Boolean))
        setPendingOrders([])
        setPendingOrdersHistory([])
      }
      setRedAIDone(false)
    } catch (e) {
      setError('Adjudication failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setAdjudicating(false)
    }
  }

  const handleMapClick = useCallback((lat, lng) => {
    if (pickingDest && pickingOrderId) {
      setPendingOrders(prev => prev.map(o =>
        o.id === pickingOrderId
          ? { ...o, to_lat: lat, to_lng: lng, to_location: `${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E` }
          : o
      ))
      setPickingDest(false)
      setPickingOrderId(null)
      setActiveTab('moves')
    } else if (pickingFiresTarget && pickingFiresOrderId) {
      const label = `${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E`
      setPendingOrders(prev => prev.map(o =>
        o.id === pickingFiresOrderId ? { ...o, target: label } : o
      ))
      setPickingFiresTarget(false)
      setPickingFiresOrderId(null)
      setActiveTab('moves')
    }
  }, [pickingDest, pickingOrderId, pickingFiresTarget, pickingFiresOrderId])

  // Fires target picking triggered from OrdersForm
  const handlePickFiresTarget = useCallback((orderId) => {
    setPickingFiresTarget(true)
    setPickingFiresOrderId(orderId)
    setActiveTab('map')
  }, [])

  // Right-click context menu
  const handleMapRightClick = useCallback((lat, lng, screenX, screenY) => {
    setRightClickMenu({ lat, lng, screenX, screenY })
  }, [])

  if (loading) return <LoadingSpinner label="Loading session..." />
  if (!session) return <div className="p-6 text-theater-red">Session not found</div>

  const gameState = session.current_game_state || {}
  const factions = scenario?.factions || []
  const units = gameState.unit_status || []
  const scores = gameState.faction_scores || []
  const turns = session.turn_logs || []
  const previousUnits = session.previous_game_state?.unit_status || []

  // Player faction and unit data for the orders form
  const rawAssignments = session.faction_assignments || []
  const playerFactionIds = rawAssignments.length > 0
    ? new Set(rawAssignments.filter(fa => fa.type === 'Player').map(fa => fa.faction_id))
    : new Set(factions.filter(f => f.role !== 'AI-controlled').map(f => f.faction_id))
  const playerFactions   = factions.filter(f => playerFactionIds.has(f.faction_id))
  const keyTerrain       = scenario?.geography?.key_terrain || []

  // Enrich scenario OOB units with live supply/WTF/C2 state from game_state, exclude destroyed
  const unitStatusMap = Object.fromEntries((gameState.unit_status || []).map(u => [u.unit_id, u]))
  const playerUnits = playerFactions.flatMap(f =>
    (f.order_of_battle?.units || [])
      .map(u => ({ ...u, ...(unitStatusMap[u.unit_id] || {}) }))
      .filter(u => u.strength !== 'Destroyed')
  )

  // FOW: show map from the first player faction's perspective
  const viewingFactionId = [...playerFactionIds][0] || null

  const mapCenter = units.length > 0 && units[0].location?.lat
    ? [units[0].location.lat, units[0].location.lng]
    : [54.1, 22.9]

  // Unit clicked on map — is it a player unit?
  const isPlayerUnit = selectedMapUnit
    ? playerFactionIds.has(selectedMapUnit.faction_id)
    : false

  // Right-click context menu actions
  function applyRightClickManeuver() {
    if (!selectedMapUnit || !rightClickMenu) return
    const order = blankOrder('maneuver', selectedMapUnit)
    order.to_lat = rightClickMenu.lat
    order.to_lng = rightClickMenu.lng
    order.to_location = `${rightClickMenu.lat.toFixed(4)}°N, ${rightClickMenu.lng.toFixed(4)}°E`
    setOrdersTracked(prev => [...prev, order])
    setRightClickMenu(null)
    // Stay on the map — the movement arrow renders immediately
  }
  function applyRightClickFires() {
    if (!selectedMapUnit || !rightClickMenu) return
    const order = blankOrder('fires', selectedMapUnit)
    order.target = `${rightClickMenu.lat.toFixed(4)}°N, ${rightClickMenu.lng.toFixed(4)}°E`
    setOrdersTracked(prev => [...prev, order])
    setRightClickMenu(null)
    setActiveTab('moves')
  }

  return (
    <div className="h-full flex flex-col">
      {/* Session header */}
      <div className="flex-shrink-0 bg-theater-card border-b border-theater-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-theater-text font-semibold font-mono">{session.title}</h2>
              <div className="flex items-center gap-3 mt-0.5">
                <StatusBadge status={session.status} />
                <span className="text-theater-muted text-xs font-mono">
                  Turn {session.current_turn} / {session.max_turns}
                </span>
                <span className="text-theater-muted text-xs font-mono">
                  {session.time_per_turn_hours}hr increments
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {session.status === 'Active' && (
              <button
                onClick={() => setShowCapitulateConfirm(true)}
                className="flex items-center gap-1.5 text-orange-400 text-xs font-mono border border-orange-400/30 hover:bg-orange-400/10 px-3 py-1.5 rounded transition-all"
                title="Declare defeat and end the session"
              >
                <Flag className="w-3.5 h-3.5" />
                CAPITULATE
              </button>
            )}
            <button onClick={() => navigate(`/sessions/${id}/red-team`)} className="text-theater-red text-xs font-mono border border-theater-red/30 hover:bg-theater-red/10 px-3 py-1.5 rounded transition-all">
              Red Team Console
            </button>
            <div className="relative" onClick={e => e.stopPropagation()}>
              <button
                onClick={() => setShowSessionMenu(p => !p)}
                className="text-theater-muted text-xs font-mono border border-theater-border hover:border-theater-accent/30 px-2.5 py-1.5 rounded transition-all"
                title="More options"
              >
                ⋮
              </button>
              {showSessionMenu && (
                <div className="absolute right-0 top-full mt-1 z-[2000] bg-theater-card border border-theater-border rounded-lg shadow-xl overflow-hidden min-w-44">
                  <button
                    onClick={() => { navigate(`/sessions/${id}/monte-carlo`); setShowSessionMenu(false) }}
                    className="w-full text-left px-4 py-2.5 text-theater-gray text-xs font-mono hover:bg-theater-bg transition-colors"
                  >
                    Monte Carlo
                  </button>
                  <button
                    onClick={() => { navigate(`/sessions/${id}/aar`); setShowSessionMenu(false) }}
                    className="w-full text-left px-4 py-2.5 text-theater-accent-light text-xs font-mono hover:bg-theater-bg transition-colors"
                  >
                    Generate AAR
                  </button>
                  <button
                    onClick={() => { handleDelete(); setShowSessionMenu(false) }}
                    className="w-full text-left px-4 py-2.5 text-theater-red text-xs font-mono hover:bg-theater-bg border-t border-theater-border transition-colors flex items-center gap-2"
                  >
                    <Trash2 className="w-3 h-3" /> Delete Session
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Turn progress bar */}
        <div className="mt-3">
          <div className="flex gap-1">
            {Array.from({ length: session.max_turns }).map((_, i) => {
              const turnNum = i + 1
              const done = turnNum < session.current_turn
              const current = turnNum === session.current_turn
              return (
                <div
                  key={i}
                  className={`flex-1 h-1 rounded-full transition-all ${
                    done ? 'bg-theater-accent' : current ? 'bg-theater-accent-light pulse-blue' : 'bg-theater-border'
                  }`}
                />
              )
            })}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-theater-muted text-xs font-mono">H+00:00</span>
            <span className="text-theater-accent-light text-xs font-mono">
              H+{(session.current_turn - 1) * session.time_per_turn_hours}:00 (CURRENT)
            </span>
            <span className="text-theater-muted text-xs font-mono">
              H+{session.max_turns * session.time_per_turn_hours}:00
            </span>
          </div>
        </div>
      </div>

      {/* Turn phase banner */}
      {(() => {
        const phase = PHASE_META[turnPhase] || PHASE_META.player
        return (
          <div className={`flex-shrink-0 border-b px-4 py-2 flex items-center justify-between ${phase.color}`}>
            <div className="flex items-center gap-3">
              <span className="font-mono font-bold text-xs tracking-widest">{phase.label}</span>
              <span className="text-xs opacity-70 hidden md:block">{phase.sub}</span>
            </div>
            <span className="font-mono text-xs opacity-50">Turn {session.current_turn}/{session.max_turns}</span>
          </div>
        )
      })()}

      {/* AI controls */}
      <div className="flex-shrink-0 bg-theater-bg border-b border-theater-border px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {aiGenerating && (
            <div className="flex items-center gap-2 text-theater-red text-xs font-mono">
              <span className="inline-block w-2 h-2 rounded-full bg-theater-red animate-pulse" />
              RED TEAM AI GENERATING ADVERSARY MOVES...
            </div>
          )}
          {adjudicating && (
            <div className="flex items-center gap-2 text-theater-green text-xs font-mono">
              <span className="inline-block w-2 h-2 rounded-full bg-theater-green animate-pulse" />
              ADJUDICATION ENGINE RESOLVING TURN...
            </div>
          )}
          {redAIDone && !adjudicating && !aiGenerating && (
            <div className="flex items-center gap-2 text-theater-green text-xs font-mono">
              <span className="inline-block w-2 h-2 rounded-full bg-theater-green" />
              RED FORCE ORDERS COMPLETE — READY TO ADJUDICATE
              <button onClick={() => setRedAIDone(false)} className="ml-1 text-theater-muted hover:text-theater-text">
                <X className="w-3 h-3" />
              </button>
            </div>
          )}
          {error && !aiGenerating && !adjudicating && (
            <div className="flex items-center gap-2 text-theater-red text-xs">
              <AlertCircle className="w-3.5 h-3.5" />
              {error}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunAI}
            disabled={aiGenerating || adjudicating}
            className="flex items-center gap-2 border border-theater-red/40 hover:bg-theater-red/10 text-theater-red px-4 py-1.5 rounded text-xs font-mono font-semibold transition-all disabled:opacity-40"
          >
            <Zap className="w-3.5 h-3.5" />
            RUN AI ADVERSARY
          </button>
          <button
            onClick={handleAdjudicate}
            disabled={session.status === 'Complete' || aiGenerating || adjudicating}
            className="flex items-center gap-2 border border-theater-green/40 hover:bg-theater-green/10 text-theater-green px-4 py-1.5 rounded text-xs font-mono font-semibold transition-all disabled:opacity-40"
          >
            <SkipForward className="w-3.5 h-3.5" />
            ADJUDICATE & ADVANCE
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex-shrink-0 flex border-b border-theater-border bg-theater-card">
        {TABS.map(({ id: tid, label, icon: Icon }) => (
          <button
            key={tid}
            onClick={() => setActiveTab(tid)}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-semibold border-b-2 transition-all ${
              activeTab === tid
                ? 'border-theater-accent-light text-theater-accent-light'
                : 'border-transparent text-theater-muted hover:text-theater-gray'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {/* Map always stays mounted so Leaflet zoom/pan state is preserved */}
        <div className={`relative h-full ${activeTab !== 'map' ? 'hidden' : ''}`}>
            <OperationalMap
              units={units.map(u => ({ ...u, location: u.location || {} }))}
              factions={factions}
              center={mapCenter}
              zoom={8}
              height="100%"
              onUnitClick={u => { setSelectedMapUnit(prev => prev?.unit_id === u.unit_id ? null : u) }}
              selectedUnit={selectedMapUnit}
              pendingOrders={pendingOrders}
              pickingDestination={pickingDest || pickingFiresTarget}
              onMapClick={handleMapClick}
              onMapRightClick={handleMapRightClick}
              highlightedUnits={highlightedUnits}
              keyTerrain={keyTerrain}
              viewingFactionId={viewingFactionId}
              previousUnits={showPreviousPositions ? previousUnits : []}
            />

            {/* Previous turn positions toggle */}
            {previousUnits.length > 0 && (
              <button
                onClick={() => setShowPreviousPositions(p => !p)}
                className={`absolute top-4 left-14 z-[1001] text-xs font-mono px-3 py-1.5 rounded border transition-all ${
                  showPreviousPositions
                    ? 'bg-gray-700/80 border-gray-400 text-gray-200'
                    : 'bg-theater-card/80 border-theater-border text-theater-muted hover:text-theater-gray'
                }`}
              >
                PREV TURN
              </button>
            )}

            {/* Unit command panel — overlaid top-right of the map */}
            {selectedMapUnit && (
              <div className="absolute top-4 right-4 z-[1001] w-72 bg-theater-card/95 border border-theater-border rounded-lg shadow-xl backdrop-blur-sm overflow-hidden">
                {/* Unit header */}
                <div className="flex items-start justify-between px-3 py-2.5 border-b border-theater-border bg-theater-bg">
                  <div>
                    <p className="font-mono text-xs text-theater-muted">{selectedMapUnit.unit_id}</p>
                    <p className="text-theater-text font-semibold text-sm">{selectedMapUnit.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <SideChip side={factions.find(f => f.faction_id === selectedMapUnit.faction_id)?.side || 'White'} />
                      <span className={`text-xs font-mono ${selectedMapUnit.strength === 'Full' ? 'strength-full' : selectedMapUnit.strength === 'Degraded' ? 'strength-degraded' : 'strength-critical'}`}>
                        {selectedMapUnit.strength}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => setSelectedMapUnit(null)} className="text-theater-muted hover:text-theater-text p-0.5">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Unit details */}
                <div className="px-3 py-2 text-xs border-b border-theater-border space-y-1">
                  {selectedMapUnit.type && <div className="flex justify-between"><span className="text-theater-muted">Type</span><span className="text-theater-gray">{selectedMapUnit.type}</span></div>}
                  {selectedMapUnit.echelon && <div className="flex justify-between"><span className="text-theater-muted">Echelon</span><span className="text-theater-gray">{selectedMapUnit.echelon}</span></div>}
                  {selectedMapUnit.status && <div className="flex justify-between"><span className="text-theater-muted">Status</span><span className="text-theater-gray">{selectedMapUnit.status}</span></div>}
                  {selectedMapUnit.location?.grid_reference && (
                    <div className="flex justify-between"><span className="text-theater-muted">Grid</span><span className="font-mono text-theater-accent-light">{selectedMapUnit.location.grid_reference}</span></div>
                  )}
                </div>

                {!isPlayerUnit && (
                  <div className="px-3 py-2.5">
                    <p className="text-theater-muted text-xs italic">AI-controlled unit — view only</p>
                  </div>
                )}
              </div>
            )}

            {/* Pending orders count badge */}
            {pendingOrders.length > 0 && !selectedMapUnit && !pickingDest && !pickingFiresTarget && (
              <div
                className="absolute top-4 right-4 z-[1001] bg-theater-accent text-white text-xs font-mono px-3 py-1.5 rounded-full shadow-lg cursor-pointer hover:bg-theater-accent-light transition-colors"
                onClick={() => setActiveTab('moves')}
              >
                {pendingOrders.length} pending order{pendingOrders.length !== 1 ? 's' : ''} — REVIEW →
              </div>
            )}

            {/* Instruction banner during destination / target picking */}
            {(pickingDest || pickingFiresTarget) && (
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1001] bg-theater-card/95 border border-theater-accent/50 text-theater-accent-light text-xs font-mono px-4 py-2 rounded-full shadow-xl backdrop-blur-sm pointer-events-none">
                {pickingDest ? '✛ CLICK MAP TO SET MANEUVER DESTINATION' : '✛ CLICK MAP TO SET FIRES TARGET'}
              </div>
            )}

            {/* Right-click context menu */}
            {rightClickMenu && (
              <div
                className="fixed z-[1002] bg-theater-card border border-theater-border rounded-lg shadow-xl overflow-hidden text-xs font-mono"
                style={{ top: rightClickMenu.screenY, left: rightClickMenu.screenX }}
              >
                {selectedMapUnit && isPlayerUnit ? (
                  <>
                    <button
                      onClick={applyRightClickManeuver}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-theater-blue hover:bg-blue-900/20 border-b border-theater-border whitespace-nowrap"
                    >
                      <Navigation className="w-3.5 h-3.5 flex-shrink-0" />
                      Move {selectedMapUnit.name} here
                    </button>
                    <button
                      onClick={applyRightClickFires}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-theater-red hover:bg-red-900/20 border-b border-theater-border whitespace-nowrap"
                    >
                      <Target className="w-3.5 h-3.5 flex-shrink-0" />
                      Fire on this location
                    </button>
                  </>
                ) : (
                  <p className="px-4 py-2.5 text-theater-muted whitespace-nowrap">Select a player unit first</p>
                )}
                <button
                  onClick={() => setRightClickMenu(null)}
                  className="w-full px-4 py-2 text-theater-muted hover:text-theater-text"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

        {activeTab === 'moves' && (
          <div className="h-full overflow-y-auto">
            {pendingOrdersHistory.length > 0 && (
              <div className="flex items-center justify-end px-4 pt-3">
                <button
                  onClick={handleUndo}
                  className="flex items-center gap-1.5 text-theater-muted hover:text-theater-text text-xs font-mono border border-theater-border hover:border-theater-accent/40 px-3 py-1 rounded transition-colors"
                  title="Ctrl+Z / Cmd+Z"
                >
                  <RotateCcw className="w-3 h-3" /> UNDO
                </button>
              </div>
            )}
            <OrdersForm
              session={session}
              orders={pendingOrders}
              setOrders={setOrdersTracked}
              playerUnits={playerUnits}
              playerFactions={playerFactions}
              onPickFiresTarget={handlePickFiresTarget}
              onSubmitted={async () => {
                const data = await refresh()
                if (derivePhase(data) !== 'red_ai') setTurnPhase('red_ai')
                setActiveTab('map')
              }}
            />
          </div>
        )}

        {activeTab === 'log' && (
          <div className="h-full overflow-y-auto p-4 space-y-3">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-theater-text font-mono font-semibold">Turn Log ({turns.length} turns)</h3>
              <button
                onClick={() => {
                  const text = turns.map(t => {
                    const adj = t.adjudication || {}
                    return `TURN ${t.turn_number}\n${adj.narrative || ''}\n\nKey Events:\n${(adj.key_events || []).join('\n')}\n\n---`
                  }).join('\n\n')
                  const blob = new Blob([text], { type: 'text/plain' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `${session.title}_TurnLog.txt`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                className="text-theater-muted text-xs font-mono hover:text-theater-text transition-colors"
              >
                EXPORT LOG ↓
              </button>
            </div>
            {turns.length === 0 ? (
              <p className="text-theater-muted text-sm font-mono text-center py-8">No turns played yet</p>
            ) : (
              [...turns].reverse().map(t => (
                <TurnEntry
                  key={t.turn_number}
                  turn={t}
                  onViewDiff={(adj, turnNum) => { setDiffData({ ...adj, turn_number: turnNum }); setShowDiff(true) }}
                />
              ))
            )}
          </div>
        )}

        {activeTab === 'intel' && (() => {
          // Collect all intelligence_gained items from adjudicated turns, most recent first
          const allIntel = [...turns]
            .sort((a, b) => b.turn_number - a.turn_number)
            .flatMap(t => (t.adjudication?.intelligence_gained || []).map(i => ({ ...i, turn: t.turn_number })))

          // Blue faction intel items
          const blueFactionIds = new Set(factions.filter(f => f.side === 'Blue').map(f => f.faction_id))
          const confirmedIntel = allIntel.filter(i => blueFactionIds.has(i.faction_id))

          // Red units — show as "last known" (grey, not live)
          const redUnits = units.filter(u => factions.find(fa => fa.faction_id === u.faction_id)?.side === 'Red')

          // Triggered scenario injects up to current turn
          const triggeredInjects = (scenario?.injects || []).filter(inj => inj.turn_trigger <= session.current_turn)

          return (
            <div className="h-full overflow-y-auto p-4 space-y-4">
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h3 className="text-theater-blue font-mono font-semibold mb-4 flex items-center gap-2">
                  <Eye className="w-4 h-4" /> Intelligence Picture — Turn {session.current_turn}
                </h3>

                {/* Confirmed intelligence from adjudication */}
                <div className="mb-4">
                  <p className="text-theater-blue font-mono text-xs tracking-wider mb-2">CONFIRMED INTELLIGENCE</p>
                  {confirmedIntel.length === 0 ? (
                    <p className="text-theater-muted text-xs italic">No confirmed intelligence yet. Submit ISR tasks in your intelligence orders to gain visibility on enemy forces.</p>
                  ) : (
                    <div className="space-y-1">
                      {confirmedIntel.map((item, i) => (
                        <div key={i} className="text-xs bg-blue-50 border border-blue-200 rounded p-2 flex gap-2">
                          <span className="font-mono text-theater-blue flex-shrink-0">T{item.turn}</span>
                          <span className="text-theater-gray">{item.intel_item}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Last-known enemy positions (fog of war — stale data, not live) */}
                <div className="mb-4">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">
                    LAST-KNOWN ENEMY POSITIONS <span className="text-theater-muted normal-case font-sans">(may be outdated)</span>
                  </p>
                  {redUnits.length === 0 ? (
                    <p className="text-theater-muted text-xs italic">No enemy positions on record.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {redUnits.map(u => (
                        <div key={u.unit_id} className="text-xs text-theater-gray py-1.5 border-b border-theater-border/30 last:border-0 flex items-center gap-2 opacity-70">
                          <span className="font-mono text-theater-red/70">{u.unit_id}</span>
                          <span>— {u.name}</span>
                          <span className="text-theater-muted">[LAST KNOWN]</span>
                          {u.location?.grid_reference && (
                            <span className="text-theater-muted font-mono">{u.location.grid_reference}</span>
                          )}
                          <button
                            onClick={() => {
                              const order = blankOrder('intelligence')
                              order.task_type = 'Ground Recon'
                              order.details = `Recon target: ${u.unit_id} — ${u.name}. Confirm current position and status.`
                              setOrdersTracked(prev => [...prev, order])
                              setActiveTab('moves')
                            }}
                            className="ml-auto opacity-100 text-theater-blue text-xs font-mono border border-theater-blue/30 hover:bg-theater-blue/10 px-2 py-0.5 rounded transition-colors flex-shrink-0"
                          >
                            + RECON
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Triggered scenario injects */}
                {triggeredInjects.length > 0 && (
                  <div>
                    <p className="text-yellow-600 font-mono text-xs tracking-wider mb-2">Active Injects</p>
                    <div className="space-y-1">
                      {triggeredInjects.map((inj, i) => (
                        <div key={i} className="text-xs bg-yellow-50 border border-yellow-200 rounded p-2">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-mono text-yellow-700">{inj.inject_id}</span>
                            <span className="text-theater-muted">T{inj.turn_trigger}</span>
                            <span className="text-theater-muted">[{inj.type}]</span>
                          </div>
                          <p className="text-theater-gray">{inj.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key terrain reference */}
                {keyTerrain.length > 0 && (
                  <div className="mt-4">
                    <p className="text-yellow-500/80 font-mono text-xs tracking-wider mb-2">KEY TERRAIN</p>
                    <div className="space-y-1">
                      {keyTerrain.map((t, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-theater-gray py-1 border-b border-theater-border/30 last:border-0">
                          <div className="w-2 h-2 rounded-sm bg-yellow-500/60 flex-shrink-0" />
                          <span>{t}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })()}

        {activeTab === 'scores' && (
          <div className="h-full overflow-y-auto p-4 space-y-4">
            <h3 className="text-theater-text font-mono font-semibold">Scores & Objectives — Turn {session.current_turn}</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {scores.map(fs => (
                <div key={fs.faction_id} className={`bg-theater-card border rounded-lg p-4 ${
                  fs.side === 'Blue' ? 'border-theater-blue/30' : fs.side === 'Red' ? 'border-theater-red/30' : 'border-theater-border'
                }`}>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <SideChip side={fs.side} />
                      <p className="text-theater-text text-sm font-semibold mt-1">{fs.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-3xl font-bold font-mono text-theater-text">{fs.score}</p>
                      <p className="text-theater-muted text-xs font-mono">POINTS</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-theater-muted font-mono">OBJECTIVE STATUS</span>
                    <span className={`font-mono ${fs.score > 50 ? 'text-theater-green' : fs.score > 25 ? 'text-yellow-700' : 'text-theater-red'}`}>
                      {fs.objective_status}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Unit status table */}
            <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-theater-border">
                <h4 className="text-theater-text font-mono text-sm font-semibold">UNIT STATUS</h4>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-theater-border">
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">UNIT</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">FACTION</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">STRENGTH</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">SUPPLY</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">MAN</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">WTF</th>
                    <th className="text-left px-4 py-2 text-theater-muted font-mono">C2</th>
                  </tr>
                </thead>
                <tbody>
                  {units.map(u => {
                    const fac = factions.find(f => f.faction_id === u.faction_id)
                    const supply = u.supply || {}
                    const munitions = supply.munitions
                    const wtfColors = { High: 'text-theater-green', Moderate: 'text-yellow-600', Low: 'text-orange-500', Broken: 'text-theater-red' }
                    const c2Colors  = { Nominal: 'text-theater-green', Degraded: 'text-yellow-600', Lost: 'text-theater-red' }
                    return (
                      <tr key={u.unit_id} className={`border-b border-theater-border/40 ${u.strength === 'Destroyed' ? 'opacity-40' : ''}`}>
                        <td className="px-4 py-2">
                          <div className="font-mono text-theater-muted">{u.unit_id}</div>
                          <div className="text-theater-gray">{u.name}</div>
                          {u.strength === 'Destroyed' && <div className="text-theater-red font-mono text-xs">DESTROYED</div>}
                        </td>
                        <td className="px-4 py-2">
                          {fac && <SideChip side={fac.side} />}
                        </td>
                        <td className="px-4 py-2 w-32">
                          <StrengthBar strength={u.strength} />
                        </td>
                        <td className="px-4 py-2">
                          {supply.ammo != null ? (
                            <div className="space-y-0.5 font-mono">
                              {munitions != null ? (
                                <div className={munitions.count === 0 ? 'text-theater-red' : 'text-theater-gray'}>
                                  MUN {munitions.count}/{munitions.max}
                                </div>
                              ) : (
                                <div className={supply.ammo < 20 ? 'text-theater-red' : 'text-theater-gray'}>AMO {supply.ammo}</div>
                              )}
                              <div className={supply.fuel < 20 ? 'text-theater-red' : 'text-theater-gray'}>FUEL {supply.fuel}</div>
                            </div>
                          ) : (
                            <span className="text-theater-muted">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2">
                          {u.manning != null ? (
                            <span className={`font-mono ${u.manning < 30 ? 'text-theater-red' : u.manning < 60 ? 'text-yellow-600' : 'text-theater-green'}`}>
                              {u.manning}%
                            </span>
                          ) : <span className="text-theater-muted">—</span>}
                        </td>
                        <td className="px-4 py-2">
                          {u.will_to_fight ? (
                            <span className={`font-mono font-semibold ${wtfColors[u.will_to_fight] || 'text-theater-gray'}`}>
                              {u.will_to_fight}
                            </span>
                          ) : <span className="text-theater-muted">—</span>}
                        </td>
                        <td className="px-4 py-2">
                          {u.c2_status ? (
                            <span className={`font-mono ${c2Colors[u.c2_status] || 'text-theater-gray'}`}>
                              {u.c2_status}
                            </span>
                          ) : <span className="text-theater-muted">—</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Logistics impacts */}
            {gameState.logistics_impacts?.length > 0 && (
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h4 className="text-theater-text font-mono text-sm font-semibold mb-3">LOGISTICS IMPACTS</h4>
                <div className="space-y-1">
                  {[...gameState.logistics_impacts].reverse().map((imp, i) => (
                    <div key={i} className="text-xs flex gap-2 py-1 border-b border-theater-border/40 last:border-0">
                      <span className="font-mono text-theater-muted flex-shrink-0">T{imp.turn}</span>
                      <span className="font-mono text-theater-accent-light flex-shrink-0">{imp.faction_id}</span>
                      <span className="text-theater-gray">{imp.impact}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Victory conditions */}
            {scenario?.win_conditions && (
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h4 className="text-theater-text font-mono text-sm font-semibold mb-3">VICTORY CONDITIONS</h4>
                {(scenario.win_conditions.scoring_dimensions || []).map((dim, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-theater-border/40 last:border-0">
                    <span className="text-theater-gray text-xs">{dim.dimension}</span>
                    <span className="font-mono text-theater-accent-light text-xs">{dim.weight_pct}%</span>
                  </div>
                ))}
                <p className="text-theater-muted text-xs font-mono mt-3">
                  Method: {scenario.win_conditions.adjudication_method} · {session.max_turns - session.current_turn + 1} turns remaining
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Turn diff panel — shown after adjudication or from turn log */}
      {showDiff && diffData && (
        <TurnDiffPanel
          data={diffData}
          turnNumber={diffData.turn_number ?? session.current_turn - 1}
          onClose={() => setShowDiff(false)}
          onViewMap={() => { setShowDiff(false); setActiveTab('map') }}
        />
      )}

      {/* Capitulate confirmation modal */}
      {showCapitulateConfirm && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60">
          <div className="bg-theater-card border border-theater-red/40 rounded-lg p-6 max-w-sm mx-4 shadow-2xl">
            <div className="flex items-center gap-2 mb-3">
              <Flag className="w-5 h-5 text-theater-red" />
              <h3 className="text-theater-red font-mono font-semibold">Declare Defeat?</h3>
            </div>
            <p className="text-theater-gray text-sm mb-5">This will end the game session immediately. This action cannot be undone.</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowCapitulateConfirm(false)}
                className="text-theater-muted text-xs font-mono border border-theater-border hover:border-theater-accent/40 hover:text-theater-text px-4 py-1.5 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setShowCapitulateConfirm(false)
                  try {
                    await sessionsApi.capitulate(id, [...playerFactionIds][0] || 'BLUE-01')
                    await refresh()
                  } catch (e) {
                    setError('Capitulation failed: ' + (e.response?.data?.detail || e.message))
                  }
                }}
                className="flex items-center gap-1.5 text-theater-red text-xs font-mono border border-theater-red/30 hover:bg-theater-red/10 px-4 py-1.5 rounded transition-colors"
              >
                <Flag className="w-3 h-3" /> Surrender
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
