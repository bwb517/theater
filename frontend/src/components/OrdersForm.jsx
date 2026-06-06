import { useState } from 'react'
import { Plus, Trash2, Send, ChevronDown, ChevronRight, Navigation, Target, Radio, Package, Megaphone, AlertTriangle, MapPin } from 'lucide-react'
import { sessionsApi } from '../api/client'
import { haversineKm, MOVEMENT_RATES } from '../utils/geo'

// ─── Constants ───────────────────────────────────────────────────────────────

const MANEUVER_ACTIONS = [
  'Move To', 'Hold', 'Attack', 'Defend', 'Withdraw', 'Screen',
  'Establish Battle Position', 'Delay', 'Exploit', 'Pursue', 'Interdict',
]
const FIRE_EFFECTS    = ['Suppress', 'Destroy', 'Neutralize', 'Obscure', 'Interdict', 'Shape']
const FIRE_PRIORITIES = ['High', 'Medium', 'Low']
const INTEL_TASKS = [
  'ISR Sortie', 'HUMINT Collection', 'SIGINT Collection', 'Ground Recon',
  'Combat Patrol', 'OSINT', 'EW Collection', 'Cyber Recon', 'Observation Post',
]
const LOGISTICS_RESOURCES = [
  'Ammunition', 'Fuel', 'Medical Supplies', 'Maintenance/Repair',
  'Equipment', 'Personnel', 'Water/Rations', 'General Supply',
]
const LOGISTICS_PRIORITIES = ['Emergency', 'High', 'Routine']
const INFO_OPS_TYPES = [
  'Influence Operation', 'Military Deception (MILDEC)', 'PSYOP',
  'Counter-Disinformation', 'IO Campaign', 'EW Jamming',
  'Cyber Operation', 'Media Engagement', 'Diplomatic Signal',
]

const WFF_META = {
  maneuver:        { label: 'Maneuver',       Icon: Navigation, color: '#2563eb', ring: 'border-theater-blue/40',   bg: 'bg-blue-50',    text: 'text-theater-blue'  },
  fires:           { label: 'Fires',           Icon: Target,     color: '#dc2626', ring: 'border-theater-red/40',    bg: 'bg-red-50',     text: 'text-theater-red'   },
  intelligence:    { label: 'Intelligence',    Icon: Radio,      color: '#a16207', ring: 'border-yellow-600/40',     bg: 'bg-yellow-50',  text: 'text-yellow-700'    },
  logistics:       { label: 'Logistics',       Icon: Package,    color: '#16a34a', ring: 'border-theater-green/40',  bg: 'bg-green-50',   text: 'text-theater-green' },
  information_ops: { label: 'Information Ops', Icon: Megaphone,  color: '#7c3aed', ring: 'border-purple-400/40',    bg: 'bg-purple-50',  text: 'text-purple-700'    },
}

// ─── Supply display helpers ───────────────────────────────────────────────────

function SupplyBar({ label, value, max = 100 }) {
  const pct = max === 0 ? 0 : Math.max(0, Math.min(100, (value / max) * 100))
  const color = pct > 50 ? '#22c55e' : pct > 20 ? '#fbbf24' : '#ef4444'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 9, fontFamily: 'monospace' }}>
      <span style={{ color: '#9ca3af' }}>{label}</span>
      <span style={{ display: 'inline-block', width: 28, height: 4, background: '#1f2937', borderRadius: 2, overflow: 'hidden' }}>
        <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: color, borderRadius: 2 }} />
      </span>
      <span style={{ color }}>{max === 100 ? value : `${value}/${max}`}</span>
    </span>
  )
}

function UnitSupplyBars({ unit }) {
  if (!unit?.supply) return null
  const { ammo, fuel, munitions } = unit.supply
  const manning = unit.manning
  return (
    <span style={{ display: 'inline-flex', gap: 6, marginLeft: 6 }}>
      {munitions != null
        ? <SupplyBar label="MUN" value={munitions.count} max={munitions.max} />
        : <SupplyBar label="AMO" value={ammo} />}
      <SupplyBar label="FUEL" value={fuel} />
      {manning != null && <SupplyBar label="MAN" value={manning} />}
    </span>
  )
}

// ─── Order helpers ────────────────────────────────────────────────────────────

let _seq = 0
const uid = () => `ord-${++_seq}`

export function blankOrder(wff, unit = null) {
  return {
    id: uid(), wff,
    unit_id: unit?.unit_id || '', unit_name: unit?.name || '',
    action: '', to_location: '', to_lat: null, to_lng: null,
    target: '', effect: '',
    task_type: '', asset: '',
    resource: '', logistics_unit_id: '',
    op_type: '', target_audience: '',
    priority: '',
    details: '',
  }
}

export function serializeOrders(orders) {
  const out = { maneuver: [], fires: [], intelligence: [], logistics: [], information_ops: [] }
  for (const o of orders) {
    const d = { details: o.details }
    if (o.wff === 'maneuver')
      out.maneuver.push({ unit_id: o.unit_id, unit_name: o.unit_name, action: o.action, to_location: o.to_location, to_lat: o.to_lat, to_lng: o.to_lng, ...d })
    else if (o.wff === 'fires')
      out.fires.push({ unit_id: o.unit_id, unit_name: o.unit_name, system: o.system, target: o.target, effect: o.effect, priority: o.priority, ...d })
    else if (o.wff === 'intelligence')
      out.intelligence.push({ task_type: o.task_type, asset: o.asset, ...d })
    else if (o.wff === 'logistics')
      out.logistics.push({ unit_id: o.logistics_unit_id || undefined, resource: o.resource, priority: o.priority, ...d })
    else if (o.wff === 'information_ops')
      out.information_ops.push({ op_type: o.op_type, target_audience: o.target_audience, ...d })
  }
  return out
}

// ─── Shared field components ─────────────────────────────────────────────────

const sel = 'bg-theater-bg border border-theater-border rounded px-2 py-1.5 text-theater-text text-xs font-mono focus:outline-none focus:border-theater-accent transition-colors'
const inp = 'bg-theater-bg border border-theater-border rounded px-2 py-1.5 text-theater-text text-xs font-mono placeholder:text-theater-muted focus:outline-none focus:border-theater-accent transition-colors'
const txa = `${inp} resize-none leading-relaxed`

function Sel({ value, onChange, options, placeholder }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} className={sel}>
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

// ─── Per-WFF entry row ────────────────────────────────────────────────────────

function ManeuverRow({ order, units, session, onChange, onRemove }) {
  const selectedUnit = units.find(u => u.unit_id === order.unit_id)
  const supply = selectedUnit?.supply || {}
  const lowFuel = supply.fuel != null && supply.fuel < 20
  const wtfBroken = selectedUnit?.will_to_fight === 'Broken'
  const offensiveAction = ['Attack', 'Assault', 'Exploit', 'Pursue'].includes(order.action)

  // Movement range warning
  let rangeWarning = null
  if (order.to_lat && order.to_lng && selectedUnit?.location?.lat) {
    const dist = haversineKm(selectedUnit.location.lat, selectedUnit.location.lng, order.to_lat, order.to_lng)
    const rate = MOVEMENT_RATES[selectedUnit.type] || 20
    const maxKm = rate * (session?.time_per_turn_hours || 9)
    const pct = maxKm > 0 ? (dist / maxKm) * 100 : 999
    if (pct > 100) rangeWarning = { color: 'text-theater-red', msg: `⚠ ${dist.toFixed(1)} km exceeds max range ${maxKm.toFixed(0)} km — server will reject` }
    else if (pct > 80) rangeWarning = { color: 'text-yellow-600', msg: `⚡ ${dist.toFixed(1)} km of ${maxKm.toFixed(0)} km max (${Math.round(pct)}%)` }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap items-center">
        <select value={order.unit_id} onChange={e => {
          const u = units.find(u => u.unit_id === e.target.value)
          onChange({ unit_id: e.target.value, unit_name: u?.name || '' })
        }} className={`${sel} flex-1 min-w-32`}>
          <option value="">Select unit…</option>
          {units.filter(u => u.strength !== 'Destroyed').map(u => (
            <option key={u.unit_id} value={u.unit_id}>
              {u.unit_id} — {u.name}
            </option>
          ))}
        </select>
        {selectedUnit && <UnitSupplyBars unit={selectedUnit} />}
        <Sel value={order.action} onChange={v => onChange({ action: v })} options={MANEUVER_ACTIONS} placeholder="Action…" />
        <input
          value={order.to_location} onChange={e => onChange({ to_location: e.target.value })}
          placeholder="Destination / grid reference"
          className={`${inp} flex-1 min-w-40`}
        />
        <button onClick={onRemove} className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      {lowFuel && (
        <p className="text-theater-red text-xs font-mono flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> Fuel critical ({supply.fuel}/100) — maneuver blocked server-side
        </p>
      )}
      {wtfBroken && offensiveAction && (
        <p className="text-orange-500 text-xs font-mono flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> Unit Will-to-Fight is Broken — offensive orders will be ignored by adjudicator
        </p>
      )}
      {rangeWarning && (
        <p className={`text-xs font-mono flex items-center gap-1 ${rangeWarning.color}`}>
          <AlertTriangle className="w-3 h-3" /> {rangeWarning.msg}
        </p>
      )}
      <textarea
        value={order.details} onChange={e => onChange({ details: e.target.value })}
        placeholder="Additional details, timing, contingencies… (optional)"
        rows={2} className={`${txa} w-full`}
      />
    </div>
  )
}

function FiresRow({ order, units, onChange, onRemove, onPickTarget }) {
  const selectedUnit = units.find(u => u.unit_id === order.unit_id)
  const supply = selectedUnit?.supply || {}
  const munitions = supply.munitions
  const noAmmo = munitions != null ? munitions.count <= 0 : (supply.ammo != null && supply.ammo < 20)
  const ammoWarning = munitions != null
    ? munitions.count <= 0
      ? `No ${munitions.type || 'munitions'} remaining — fires blocked`
      : null
    : supply.ammo != null && supply.ammo < 20
      ? `Ammo critical (${supply.ammo}/100) — fires blocked server-side`
      : null

  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap items-center">
        <select value={order.unit_id} onChange={e => {
          const u = units.find(u => u.unit_id === e.target.value)
          onChange({ unit_id: e.target.value, unit_name: u?.name || '' })
        }} className={`${sel} flex-1 min-w-32`}>
          <option value="">Firing unit…</option>
          {units.filter(u => u.strength !== 'Destroyed').map(u => <option key={u.unit_id} value={u.unit_id}>{u.unit_id} — {u.name}</option>)}
        </select>
        {selectedUnit && <UnitSupplyBars unit={selectedUnit} />}
        <input
          value={order.target} onChange={e => onChange({ target: e.target.value })}
          placeholder="Target location or unit"
          className={`${inp} flex-1 min-w-40`}
        />
        {onPickTarget && (
          <button
            onClick={() => onPickTarget(order.id)}
            title="Pick target on map"
            className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0"
          >
            <MapPin className="w-3.5 h-3.5" />
          </button>
        )}
        <Sel value={order.effect} onChange={v => onChange({ effect: v })} options={FIRE_EFFECTS} placeholder="Effect…" />
        <Sel value={order.priority} onChange={v => onChange({ priority: v })} options={FIRE_PRIORITIES} placeholder="Priority…" />
        <button onClick={onRemove} className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      {ammoWarning && (
        <p className="text-theater-red text-xs font-mono flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {ammoWarning}
        </p>
      )}
      <textarea
        value={order.details} onChange={e => onChange({ details: e.target.value })}
        placeholder="Timing, ammunition type, restrictions, desired effects in detail… (optional)"
        rows={2} className={`${txa} w-full`}
      />
    </div>
  )
}

function IntelRow({ order, onChange, onRemove }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap items-center">
        <Sel value={order.task_type} onChange={v => onChange({ task_type: v })} options={INTEL_TASKS} placeholder="Collection type…" />
        <input
          value={order.asset} onChange={e => onChange({ asset: e.target.value })}
          placeholder="Asset / platform (e.g. RQ-7 Shadow, SOF team)"
          className={`${inp} flex-1 min-w-48`}
        />
        <button onClick={onRemove} className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <textarea
        value={order.details} onChange={e => onChange({ details: e.target.value })}
        placeholder="Collection task: what to find, where to look, priority intelligence requirements, reporting timeline, specific indicators to watch for…"
        rows={3} className={`${txa} w-full`}
      />
    </div>
  )
}

function LogisticsRow({ order, units, onChange, onRemove }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap items-center">
        <Sel value={order.resource} onChange={v => onChange({ resource: v })} options={LOGISTICS_RESOURCES} placeholder="Resource…" />
        <select value={order.logistics_unit_id} onChange={e => onChange({ logistics_unit_id: e.target.value })} className={`${sel} flex-1 min-w-32`}>
          <option value="">Target unit (optional)…</option>
          {units.map(u => <option key={u.unit_id} value={u.unit_id}>{u.unit_id} — {u.name}</option>)}
        </select>
        <Sel value={order.priority} onChange={v => onChange({ priority: v })} options={LOGISTICS_PRIORITIES} placeholder="Priority…" />
        <button onClick={onRemove} className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <textarea
        value={order.details} onChange={e => onChange({ details: e.target.value })}
        placeholder="Quantity, method of delivery, timing window…"
        rows={2} className={`${txa} w-full`}
      />
    </div>
  )
}

function InfoOpsRow({ order, onChange, onRemove }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap items-center">
        <Sel value={order.op_type} onChange={v => onChange({ op_type: v })} options={INFO_OPS_TYPES} placeholder="Operation type…" />
        <input
          value={order.target_audience} onChange={e => onChange({ target_audience: e.target.value })}
          placeholder="Target audience / system"
          className={`${inp} flex-1 min-w-40`}
        />
        <button onClick={onRemove} className="text-theater-muted hover:text-theater-red transition-colors flex-shrink-0">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <textarea
        value={order.details} onChange={e => onChange({ details: e.target.value })}
        placeholder="Full description — messaging themes, channels, timing, desired effects, narrative lines, coordination requirements, technical approach…"
        rows={3} className={`${txa} w-full`}
      />
    </div>
  )
}

// ─── WFF section ─────────────────────────────────────────────────────────────

function WFFSection({ wff, orders, units, session, onAdd, onChange, onRemove, onPickFiresTarget }) {
  const [open, setOpen] = useState(wff === 'maneuver' || orders.length > 0)
  const { label, Icon, color, ring, bg, text } = WFF_META[wff]
  const count = orders.length

  return (
    <div className={`border rounded-lg overflow-hidden ${ring}`}>
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between px-4 py-3 bg-theater-card hover:bg-theater-card transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-4 h-4" style={{ color }} />
          <span className={`font-mono font-semibold text-sm ${text}`}>{label}</span>
          {count > 0 && (
            <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: color + '22', color }}>
              {count} order{count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-theater-muted" /> : <ChevronRight className="w-4 h-4 text-theater-muted" />}
      </button>

      {open && (
        <div className={`border-t ${ring} p-4 ${bg} space-y-3`}>
          {orders.map((order, idx) => (
            <div key={order.id} className="bg-theater-card border border-theater-border rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className={`font-mono text-xs ${text}`}>{label.split(' ')[0]} #{idx + 1}</span>
              </div>
              {wff === 'maneuver'        && <ManeuverRow order={order} units={units} session={session} onChange={p => onChange(order.id, p)} onRemove={() => onRemove(order.id)} />}
              {wff === 'fires'           && <FiresRow    order={order} units={units} onChange={p => onChange(order.id, p)} onRemove={() => onRemove(order.id)} onPickTarget={onPickFiresTarget} />}
              {wff === 'intelligence'    && <IntelRow    order={order}               onChange={p => onChange(order.id, p)} onRemove={() => onRemove(order.id)} />}
              {wff === 'logistics'       && <LogisticsRow order={order} units={units} onChange={p => onChange(order.id, p)} onRemove={() => onRemove(order.id)} />}
              {wff === 'information_ops' && <InfoOpsRow  order={order}               onChange={p => onChange(order.id, p)} onRemove={() => onRemove(order.id)} />}
            </div>
          ))}

          <button
            onClick={() => onAdd(wff)}
            className={`flex items-center gap-2 text-xs font-mono px-3 py-2 rounded border transition-colors ${ring} ${text} hover:bg-white/5`}
          >
            <Plus className="w-3.5 h-3.5" /> ADD {label.split(' ')[0]} ORDER
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function OrdersForm({ session, orders, setOrders, playerUnits, playerFactions, onPickFiresTarget, onSubmitted }) {
  const [faction, setFaction] = useState(playerFactions?.[0]?.faction_id || '')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const activeFactionId = faction || playerFactions?.[0]?.faction_id || 'BLUE-01'
  const totalOrders = orders.length

  const handleAdd = (wff) => {
    setOrders(prev => [...prev, blankOrder(wff)])
  }

  const handleChange = (id, patch) => {
    setOrders(prev => prev.map(o => o.id === id ? { ...o, ...patch } : o))
  }

  const handleRemove = (id) => {
    setOrders(prev => prev.filter(o => o.id !== id))
  }

  const handleSubmit = async () => {
    if (totalOrders === 0) return
    setSubmitting(true)
    try {
      await sessionsApi.submitMoves(session.id, {
        faction_id: activeFactionId,
        moves: serializeOrders(orders),
      })
      setSubmitted(true)
      onSubmitted?.()
    } catch (e) {
      alert('Submit failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) return (
    <div className="p-6 text-center">
      <div className="w-12 h-12 bg-theater-green/20 rounded-full flex items-center justify-center mx-auto mb-3 border border-theater-green/30">
        <Send className="w-5 h-5 text-theater-green" />
      </div>
      <p className="text-theater-text font-mono font-semibold">ORDERS SUBMITTED</p>
      <p className="text-theater-muted text-sm mt-1">
        {totalOrders} order{totalOrders !== 1 ? 's' : ''} submitted for Turn {session.current_turn}.
      </p>
      <button
        onClick={() => { setSubmitted(false); setOrders([]) }}
        className="mt-4 text-theater-muted text-xs font-mono border border-theater-border hover:border-theater-accent/40 hover:text-theater-text px-4 py-1.5 rounded transition-colors"
      >
        CLEAR & RE-ENTER ORDERS
      </button>
    </div>
  )

  return (
    <div className="p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-theater-text font-mono font-semibold">SUBMIT ORDERS — TURN {session.current_turn}</h3>
          <p className="text-theater-muted text-xs mt-0.5">Add orders by warfighting function. Orders from the map are included automatically.</p>
        </div>
        {playerFactions?.length > 1 && (
          <select value={faction} onChange={e => setFaction(e.target.value)} className={`${sel} text-xs`}>
            {playerFactions.map(f => <option key={f.faction_id} value={f.faction_id}>{f.faction_id}</option>)}
          </select>
        )}
      </div>

      {/* WFF sections */}
      {Object.keys(WFF_META).map(wff => (
        <WFFSection
          key={wff}
          wff={wff}
          orders={orders.filter(o => o.wff === wff)}
          units={playerUnits}
          session={session}
          onAdd={handleAdd}
          onChange={handleChange}
          onRemove={handleRemove}
          onPickFiresTarget={onPickFiresTarget}
        />
      ))}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={submitting || totalOrders === 0}
        className="w-full flex items-center justify-center gap-2 bg-theater-accent hover:bg-theater-accent-light disabled:opacity-40 text-white py-2.5 rounded font-mono font-semibold transition-colors"
      >
        <Send className="w-4 h-4" />
        {submitting ? 'Submitting...' : `Submit ${totalOrders > 0 ? `${totalOrders} Order${totalOrders !== 1 ? 's' : ''}` : 'Orders'}`}
      </button>
    </div>
  )
}
