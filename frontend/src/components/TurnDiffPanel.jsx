import { X, Zap, TrendingUp, TrendingDown, Shield, MapPin, ArrowRight, Package, Brain, Wifi } from 'lucide-react'

function ScoreRow({ change }) {
  const positive = change.change > 0
  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <div className={`flex-shrink-0 mt-0.5 ${positive ? 'text-theater-green' : 'text-theater-red'}`}>
        {positive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-theater-muted">{change.faction_id}</span>
          <span className={`font-mono font-bold text-sm ${positive ? 'text-theater-green' : 'text-theater-red'}`}>
            {positive ? '+' : ''}{change.change}
          </span>
          <span className="text-theater-muted text-xs">{change.dimension}</span>
        </div>
        {change.rationale && (
          <p className="text-theater-gray text-xs mt-0.5 leading-relaxed">{change.rationale}</p>
        )}
      </div>
    </div>
  )
}

const STRENGTH_ORDER = { Full: 3, Degraded: 2, Critical: 1, Destroyed: 0 }

function CasualtyRow({ cas }) {
  const parts = cas.strength_change?.split(/[→>]/) || []
  const from = parts[0]?.trim()
  const to = parts[parts.length - 1]?.trim()
  const degraded = STRENGTH_ORDER[to] < STRENGTH_ORDER[from]
  const strColor = { Full: 'text-theater-green', Degraded: 'text-yellow-700', Critical: 'text-theater-red', Destroyed: 'text-theater-red' }

  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <Shield className="w-3.5 h-3.5 text-theater-muted flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-theater-muted">{cas.unit_id}</span>
          {from && to && (
            <div className="flex items-center gap-1 text-xs font-mono">
              <span className={strColor[from] || 'text-theater-gray'}>{from}</span>
              <ArrowRight className="w-3 h-3 text-theater-muted" />
              <span className={`font-bold ${strColor[to] || 'text-theater-gray'}`}>{to}</span>
            </div>
          )}
          <span className="text-theater-muted text-xs font-mono">[{cas.faction_id}]</span>
        </div>
        {cas.cause && (
          <p className="text-theater-gray text-xs mt-0.5 leading-relaxed">{cas.cause}</p>
        )}
      </div>
    </div>
  )
}

function TerrainRow({ change }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <MapPin className="w-3.5 h-3.5 text-theater-muted flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-theater-text text-xs font-semibold">{change.location}</p>
        <div className="flex items-center gap-1 text-xs font-mono mt-0.5">
          <span className="text-theater-red">{change.from_faction || 'Contested'}</span>
          <ArrowRight className="w-3 h-3 text-theater-muted" />
          <span className="text-theater-blue">{change.to_faction}</span>
        </div>
      </div>
    </div>
  )
}

const WTF_COLORS = { High: '#22c55e', Moderate: '#fbbf24', Low: '#f97316', Broken: '#ef4444' }
const C2_COLORS  = { Nominal: '#22c55e', Degraded: '#fbbf24', Lost: '#ef4444' }

function SupplyRow({ sc, unitMap }) {
  const name = unitMap?.[sc.unit_id] || sc.unit_id
  const deltas = [
    sc.ammo_delta        && { label: 'AMO', val: sc.ammo_delta },
    sc.fuel_delta        && { label: 'FUEL', val: sc.fuel_delta },
    sc.maintenance_delta && { label: 'MNT', val: sc.maintenance_delta },
    sc.munitions_delta   && { label: 'MUN', val: sc.munitions_delta },
  ].filter(Boolean)
  if (deltas.length === 0) return null
  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <Package className="w-3.5 h-3.5 text-theater-muted flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-theater-muted">{name}</span>
          {deltas.map(({ label, val }) => (
            <span key={label} className={`font-mono text-xs font-bold ${val > 0 ? 'text-theater-green' : 'text-theater-red'}`}>
              {label} {val > 0 ? '+' : ''}{val}
            </span>
          ))}
        </div>
        {sc.reason && <p className="text-theater-gray text-xs mt-0.5">{sc.reason}</p>}
      </div>
    </div>
  )
}

function WTFRow({ change, unitMap }) {
  const name = unitMap?.[change.unit_id] || change.unit_id
  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <Brain className="w-3.5 h-3.5 text-theater-muted flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-theater-muted">{name}</span>
          <span className="text-xs font-mono" style={{ color: WTF_COLORS[change.from] || '#9ca3af' }}>{change.from}</span>
          <ArrowRight className="w-3 h-3 text-theater-muted" />
          <span className="text-xs font-mono font-bold" style={{ color: WTF_COLORS[change.to] || '#9ca3af' }}>{change.to}</span>
        </div>
        {change.reason && <p className="text-theater-gray text-xs mt-0.5">{change.reason}</p>}
      </div>
    </div>
  )
}

function C2Row({ change, unitMap }) {
  const name = unitMap?.[change.unit_id] || change.unit_id
  return (
    <div className="flex items-start gap-3 py-2 border-b border-theater-border/40 last:border-0">
      <Wifi className="w-3.5 h-3.5 text-theater-muted flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-theater-muted">{name}</span>
          <span className="text-xs font-mono" style={{ color: C2_COLORS[change.from] || '#9ca3af' }}>{change.from}</span>
          <ArrowRight className="w-3 h-3 text-theater-muted" />
          <span className="text-xs font-mono font-bold" style={{ color: C2_COLORS[change.to] || '#9ca3af' }}>{change.to}</span>
        </div>
        {change.cause && <p className="text-theater-gray text-xs mt-0.5">{change.cause}</p>}
      </div>
    </div>
  )
}

export default function TurnDiffPanel({ data, turnNumber, onClose, onViewMap }) {
  if (!data) return null

  const {
    narrative,
    decisive_moment,
    casualties = [],
    terrain_changes = [],
    score_changes = [],
    key_events = [],
    next_turn_conditions,
    logistics_impacts = [],
    supply_changes = [],
    will_to_fight_changes = [],
    c2_changes = [],
  } = data

  const totalScoreDelta = score_changes.reduce((s, c) => s + Math.abs(c.change), 0)
  // Build a quick name lookup from casualties/supply data (unit_id → readable name isn't in adjudication directly)
  const unitMap = {}
  casualties.forEach(c => { if (c.unit_id) unitMap[c.unit_id] = c.unit_id })
  supply_changes.forEach(s => { if (s.unit_id) unitMap[s.unit_id] = s.unit_id })
  will_to_fight_changes.forEach(w => { if (w.unit_id) unitMap[w.unit_id] = w.unit_id })
  c2_changes.forEach(c => { if (c.unit_id) unitMap[c.unit_id] = c.unit_id })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-theater-bg/95 p-4">
      <div className="bg-theater-card border border-theater-border rounded-xl w-full max-w-4xl max-h-[94vh] overflow-hidden shadow-2xl flex flex-col">

        {/* Header */}
        <div className="flex-shrink-0 px-5 py-4 border-b border-theater-border bg-theater-bg flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-700" />
              <h2 className="text-theater-text font-mono font-bold tracking-wider">Turn {turnNumber} Results</h2>
            </div>
            <p className="text-theater-muted text-xs mt-0.5 font-mono">
              {casualties.length} casualt{casualties.length !== 1 ? 'ies' : 'y'} ·{' '}
              {terrain_changes.length} terrain change{terrain_changes.length !== 1 ? 's' : ''} ·{' '}
              {supply_changes.length > 0 ? `${supply_changes.length} supply event${supply_changes.length !== 1 ? 's' : ''} · ` : ''}
              {totalScoreDelta > 0 ? `${totalScoreDelta} pts scored` : 'no scoring'}
            </p>
          </div>
          <button onClick={onClose} className="text-theater-muted hover:text-theater-text transition-colors p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Decisive moment */}
          {decisive_moment && (
            <div className="px-5 py-3 bg-yellow-50 border-b border-yellow-200">
              <p className="text-yellow-700 font-mono text-xs tracking-wider mb-1">⚡ DECISIVE MOMENT</p>
              <p className="text-theater-text text-sm font-semibold leading-relaxed">{decisive_moment}</p>
            </div>
          )}

          {/* Narrative */}
          {narrative && (
            <div className="px-5 py-4 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">OPERATIONS NARRATIVE</p>
              <p className="text-theater-gray text-xs leading-relaxed">{narrative}</p>
            </div>
          )}

          {/* Score changes */}
          {score_changes.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">SCORE CHANGES</p>
              {score_changes.map((sc, i) => <ScoreRow key={i} change={sc} />)}
            </div>
          )}

          {/* Casualties */}
          {casualties.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">
                CASUALTIES & ATTRITION
              </p>
              {casualties.map((c, i) => <CasualtyRow key={i} cas={c} />)}
            </div>
          )}

          {/* Terrain changes */}
          {terrain_changes.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">TERRAIN CONTROL CHANGES</p>
              {terrain_changes.map((tc, i) => <TerrainRow key={i} change={tc} />)}
            </div>
          )}

          {/* Logistics impacts */}
          {logistics_impacts.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">LOGISTICS IMPACTS</p>
              {logistics_impacts.map((li, i) => (
                <div key={i} className="flex gap-2 py-1.5 border-b border-theater-border/40 last:border-0 text-xs">
                  <span className="font-mono text-theater-accent-light flex-shrink-0">{li.faction_id}</span>
                  <span className="text-theater-gray">{li.impact}</span>
                </div>
              ))}
            </div>
          )}

          {/* Supply changes */}
          {supply_changes.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">SUPPLY CHANGES</p>
              {supply_changes.map((sc, i) => <SupplyRow key={i} sc={sc} unitMap={unitMap} />)}
            </div>
          )}

          {/* Will-to-Fight changes */}
          {will_to_fight_changes.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">WILL-TO-FIGHT</p>
              {will_to_fight_changes.map((w, i) => <WTFRow key={i} change={w} unitMap={unitMap} />)}
            </div>
          )}

          {/* C2 changes */}
          {c2_changes.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">C2 STATUS</p>
              {c2_changes.map((c, i) => <C2Row key={i} change={c} unitMap={unitMap} />)}
            </div>
          )}

          {/* Key events */}
          {key_events.length > 0 && (
            <div className="px-5 py-3 border-b border-theater-border">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">KEY EVENTS</p>
              <div className="space-y-1">
                {key_events.map((e, i) => (
                  <div key={i} className="flex gap-2 text-xs">
                    <span className="text-theater-accent-light font-mono flex-shrink-0">{String(i + 1).padStart(2, '0')}.</span>
                    <span className="text-theater-gray leading-relaxed">{e}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Next turn setup */}
          {next_turn_conditions && (
            <div className="px-5 py-3">
              <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">SITUATION AT NEXT TURN START</p>
              <p className="text-theater-gray text-xs leading-relaxed italic">{next_turn_conditions}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-5 py-3 border-t border-theater-border bg-theater-bg flex items-center justify-between gap-3">
          <button
            onClick={onViewMap}
            className="text-theater-muted text-xs font-mono hover:text-theater-text transition-colors"
          >
            VIEW ON MAP →
          </button>
          <button
            onClick={onClose}
            className="bg-theater-accent hover:bg-theater-accent-light text-white px-5 py-2 rounded font-mono font-semibold text-sm transition-colors"
          >
            CONTINUE
          </button>
        </div>
      </div>
    </div>
  )
}
