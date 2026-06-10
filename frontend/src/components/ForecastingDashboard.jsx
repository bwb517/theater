import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import { Target } from 'lucide-react'

const RATING_COLOR = {
  'Well-calibrated': 'text-theater-green',
  'Overconfident': 'text-theater-red',
  'Underconfident': 'text-yellow-600',
}

const QUESTION_KEYS = [
  ['p_blue_wins', 'blue_achieved'],
  ['p_red_wins', 'red_achieved'],
  ['p_escalation', 'escalation_occurred'],
  ['p_key_objective_captured', 'key_objective_captured'],
]

// Bucket every (forecast, outcome) pair into deciles and compute the realised hit-rate
// per bucket. A well-calibrated forecaster's bars sit on the diagonal: 70% estimates
// come true ~70% of the time.
function calibrationBuckets(turnByTurn) {
  const buckets = Array.from({ length: 5 }, (_, i) => ({
    label: `${i * 20}–${i * 20 + 20}%`,
    mid: i * 20 + 10,
    hits: 0,
    total: 0,
  }))
  for (const t of turnByTurn) {
    if (t.brier_score == null) continue // unresolved
    for (const [pKey, oKey] of QUESTION_KEYS) {
      const p = t[pKey]
      if (typeof p !== 'number') continue
      const idx = Math.min(4, Math.floor(p * 5))
      buckets[idx].total += 1
      if (t[oKey]) buckets[idx].hits += 1
    }
  }
  return buckets
    .filter(b => b.total > 0)
    .map(b => ({ label: b.label, mid: b.mid, hit_rate: Math.round((b.hits / b.total) * 100), n: b.total }))
}

/**
 * Forecasting accuracy dashboard: Brier-score trend, calibration histogram, and an
 * overall calibration summary card. Driven entirely by the deterministic
 * /forecasting-summary payload (passed in as `summary`).
 */
export default function ForecastingDashboard({ summary }) {
  if (!summary || !summary.forecasts_submitted) {
    return (
      <div className="bg-theater-card border border-theater-border rounded-lg p-6 text-center">
        <Target className="w-6 h-6 text-theater-muted mx-auto mb-2" />
        <p className="text-theater-muted text-sm font-mono">No forecasts submitted yet.</p>
        <p className="text-theater-muted text-xs mt-1">Submit a Pre-Turn Forecast before adjudicating a turn to start tracking calibration.</p>
      </div>
    )
  }

  const trend = (summary.turn_by_turn || [])
    .filter(t => t.brier_score != null)
    .map(t => ({ turn: t.turn_num, brier: t.brier_score }))
  const buckets = calibrationBuckets(summary.turn_by_turn || [])
  const avg = summary.average_brier_score
  const ratingColor = RATING_COLOR[summary.calibration_rating] || 'text-theater-text'

  return (
    <div className="space-y-4">
      {/* Summary card */}
      <div className="bg-theater-card border border-theater-accent/30 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-theater-accent-light" />
            <h4 className="text-theater-text font-mono text-sm font-semibold">FORECASTING ACCURACY</h4>
          </div>
          <span className={`font-mono text-sm font-bold ${ratingColor}`}>{summary.calibration_rating}</span>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-3">
          <Stat label="AVG BRIER" value={avg != null ? avg.toFixed(3) : '—'} hint="0 = perfect" />
          <Stat label="RESOLVED" value={`${summary.forecasts_resolved}/${summary.forecasts_submitted}`} hint="turns scored" />
          <Stat label="CALIBRATION" value={summary.calibration_rating?.split('-')[0] || '—'} hint="overall" />
        </div>
        <p className="text-theater-muted text-[10px] leading-relaxed mt-3">{summary.brier_note}</p>
      </div>

      {/* Brier trend */}
      {trend.length > 0 && (
        <div className="bg-theater-card border border-theater-border rounded-lg p-4">
          <h4 className="text-theater-text font-mono text-xs font-semibold mb-3">BRIER SCORE BY TURN — lower is better</h4>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trend} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="turn" tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
              <YAxis domain={[0, 2]} tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e5e5e5', borderRadius: 6, color: '#171717', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
                formatter={v => [v.toFixed(3), 'Brier']}
                labelFormatter={l => `Turn ${l}`}
              />
              <ReferenceLine y={0.5} stroke="#a16207" strokeDasharray="4 4" label={{ value: 'coin flip', fontSize: 9, fill: '#a16207' }} />
              <Line dataKey="brier" stroke="#2563eb" strokeWidth={2} dot={{ fill: '#2563eb', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Calibration histogram */}
      {buckets.length > 0 && (
        <div className="bg-theater-card border border-theater-border rounded-lg p-4">
          <h4 className="text-theater-text font-mono text-xs font-semibold mb-1">CALIBRATION — did N% estimates come true ~N% of the time?</h4>
          <p className="text-theater-muted text-[10px] mb-3">Each bar is the realised hit-rate for forecasts in that probability band. Closer to the band = better calibrated.</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={buckets} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="label" tick={{ fill: '#737373', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e5e5e5', borderRadius: 6, color: '#171717', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
                formatter={(v, _n, p) => [`${v}% (n=${p.payload.n})`, 'Hit rate']}
              />
              <Bar dataKey="hit_rate" radius={[3, 3, 0, 0]}>
                {buckets.map((b, i) => {
                  // Green when the realised rate is within 15pts of the band midpoint.
                  const ok = Math.abs(b.hit_rate - b.mid) <= 15
                  return <Cell key={i} fill={ok ? '#16a34a' : '#dc2626'} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="bg-theater-bg border border-theater-border rounded p-2 text-center">
      <p className="text-theater-muted text-[10px] font-mono">{label}</p>
      <p className="text-theater-text text-lg font-bold font-mono">{value}</p>
      <p className="text-theater-muted text-[9px]">{hint}</p>
    </div>
  )
}
