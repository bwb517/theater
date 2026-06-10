import { useState } from 'react'
import { forecastingApi } from '../api/client'
import { ChevronDown, Target, Check } from 'lucide-react'

const QUESTIONS = [
  { key: 'p_blue_wins', label: 'Blue achieves its objectives this turn', color: 'accent-blue-600' },
  { key: 'p_red_wins', label: 'Red achieves its objectives this turn', color: 'accent-red-600' },
  { key: 'p_escalation', label: 'An escalatory action occurs (casualties, units break/lose C2)', color: 'accent-orange-500' },
  { key: 'p_key_objective_captured', label: 'Key terrain / objective changes hands', color: 'accent-yellow-600' },
]

/**
 * Optional pre-turn probabilistic forecast. The player assigns probabilities to four
 * binary outcomes BEFORE adjudication; after the turn resolves they're scored with the
 * Brier score. Strictly optional — collapsed by default, skipping it changes nothing.
 */
export default function PreTurnForecastPanel({ session, turnNum, alreadyForecast, onSubmitted }) {
  const [open, setOpen] = useState(false)
  const [vals, setVals] = useState({ p_blue_wins: 50, p_red_wins: 50, p_escalation: 50, p_key_objective_captured: 50 })
  const [rationale, setRationale] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const submitted = alreadyForecast || done

  const submit = async () => {
    setSubmitting(true)
    setError('')
    try {
      await forecastingApi.submit(session.id, turnNum, {
        p_blue_wins: vals.p_blue_wins / 100,
        p_red_wins: vals.p_red_wins / 100,
        p_escalation: vals.p_escalation / 100,
        p_key_objective_captured: vals.p_key_objective_captured / 100,
        rationale: rationale.trim() || null,
      })
      setDone(true)
      onSubmitted?.()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-4 mt-3 border border-theater-accent/30 rounded-lg overflow-hidden bg-theater-card">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-3 hover:bg-theater-bg transition-colors"
      >
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-theater-accent-light" />
          <span className="font-mono text-sm text-theater-text">Pre-Turn Forecast</span>
          <span className="text-theater-muted text-xs font-mono">(optional)</span>
          {submitted && (
            <span className="flex items-center gap-1 text-theater-green text-xs font-mono">
              <Check className="w-3 h-3" /> submitted
            </span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-theater-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-theater-border p-4 space-y-4">
          {submitted ? (
            <p className="text-theater-gray text-xs font-mono">
              Forecast recorded for Turn {turnNum}. Your estimates will be scored against the
              outcome after this turn is adjudicated. (Brier score, Brier 1950 — lower is better.)
            </p>
          ) : (
            <>
              <p className="text-theater-muted text-xs leading-relaxed">
                Estimate the probability of each outcome this turn. After adjudication you'll get a
                Brier score (0 = perfect, 2 = worst) measuring how well-calibrated your forecasts were.
              </p>
              {QUESTIONS.map(q => (
                <div key={q.key}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-theater-gray text-xs">{q.label}</span>
                    <span className="font-mono text-theater-text text-sm font-bold w-12 text-right">{vals[q.key]}%</span>
                  </div>
                  <input
                    type="range" min="0" max="100" step="1"
                    value={vals[q.key]}
                    onChange={e => setVals(v => ({ ...v, [q.key]: parseInt(e.target.value, 10) }))}
                    className={`w-full ${q.color}`}
                  />
                </div>
              ))}
              <div>
                <label className="text-theater-muted text-xs font-mono block mb-1">RATIONALE (optional)</label>
                <textarea
                  value={rationale}
                  onChange={e => setRationale(e.target.value)}
                  rows={2}
                  placeholder="Why do you expect these outcomes?"
                  className="w-full bg-theater-bg border border-theater-border rounded p-2 text-xs text-theater-text font-mono resize-none focus:outline-none focus:border-theater-accent/50"
                />
              </div>
              {error && <p className="text-theater-red text-xs font-mono">{error}</p>}
              <button
                onClick={submit}
                disabled={submitting}
                className="w-full bg-theater-accent/20 border border-theater-accent/40 text-theater-accent-light font-mono text-sm py-2 rounded hover:bg-theater-accent/30 transition-colors disabled:opacity-50"
              >
                {submitting ? 'Submitting…' : 'Submit Forecast'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
