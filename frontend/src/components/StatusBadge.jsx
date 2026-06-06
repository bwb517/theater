export function StatusBadge({ status }) {
  const map = {
    Active: 'badge badge-active',
    Paused: 'badge badge-paused',
    Complete: 'badge badge-complete',
    Setup: 'badge badge-setup',
    Blue: 'badge badge-blue',
    Red: 'badge badge-red',
    'AI-controlled': 'badge badge-red',
    Player: 'badge badge-blue',
    Neutral: 'badge badge-setup',
    Full: 'badge badge-active',
    Degraded: 'badge badge-paused',
    Critical: 'badge badge-red',
    Robust: 'badge badge-active',
    Adequate: 'badge badge-active',
    Strained: 'badge badge-paused',
    Tactical: 'badge badge-blue',
    Operational: 'badge badge-active',
    Strategic: 'badge badge-complete',
    'Gray-Zone': 'badge badge-paused',
  }
  const cls = map[status] || 'badge badge-setup'
  return <span className={cls}>{status?.toUpperCase()}</span>
}

export function StrengthBar({ strength }) {
  const pct = strength === 'Full' ? 100 : strength === 'Degraded' ? 55 : 20
  const color = strength === 'Full' ? 'bg-theater-green' : strength === 'Degraded' ? 'bg-yellow-500' : 'bg-theater-red'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-theater-border rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs ${pct > 70 ? 'strength-full' : pct > 40 ? 'strength-degraded' : 'strength-critical'}`}>
        {strength}
      </span>
    </div>
  )
}

export function SideChip({ side }) {
  const colors = {
    Blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    Red: 'bg-red-500/20 text-red-400 border-red-500/30',
    Green: 'bg-green-500/20 text-green-400 border-green-500/30',
    White: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold border ${colors[side] || colors.White}`}>
      {side}
    </span>
  )
}
