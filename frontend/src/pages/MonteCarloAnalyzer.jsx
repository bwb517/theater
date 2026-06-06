import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { monteCarloApi, sessionsApi } from '../api/client'
import { LoadingSpinner, AIThinking } from '../components/LoadingSpinner'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { ArrowLeft, BarChart3, AlertCircle, Zap, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'

const IMPACT_COLOR = { High: '#ef4444', Medium: '#fbbf24', Low: '#22c55e', Critical: '#ef4444', Important: '#fbbf24', Noteworthy: '#22c55e' }

function OutcomeChart({ data }) {
  const COLORS = ['#171717', '#dc2626', '#a16207', '#16a34a', '#7c3aed']
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey="scenario_outcome" tick={{ fill: '#737373', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
          tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
        <YAxis tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
        <Tooltip
          contentStyle={{ background: '#ffffff', border: '1px solid #e5e5e5', borderRadius: 6, color: '#171717', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
          formatter={v => [`${v}%`, 'Probability']}
        />
        <Bar dataKey="probability_pct" radius={[3, 3, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function ImpactBadge({ impact }) {
  const cls = impact === 'High' || impact === 'Critical'
    ? 'badge badge-red' : impact === 'Medium' || impact === 'Important'
    ? 'badge badge-paused' : 'badge badge-active'
  return <span className={cls}>{impact}</span>
}

function NarrativeCard({ title, icon: Icon, content, color }) {
  return (
    <div className={`bg-theater-card border rounded-lg p-4 border-l-4`} style={{ borderLeftColor: color }}>
      <h4 className="font-mono font-semibold text-sm text-theater-text flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4" style={{ color }} />
        {title}
      </h4>
      <p className="text-theater-gray text-xs leading-relaxed">{content}</p>
    </div>
  )
}

export default function MonteCarloAnalyzer() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [numRuns, setNumRuns] = useState(10)
  const [error, setError] = useState('')

  useEffect(() => {
    sessionsApi.get(id).then(r => setSession(r.data)).finally(() => setLoading(false))
    monteCarloApi.getForSession(id)
      .then(r => setResults(r.data.results))
      .catch(() => {})
  }, [id])

  const handleRun = async () => {
    setRunning(true)
    setError('')
    try {
      const res = await monteCarloApi.run({ session_id: id, num_runs: numRuns })
      setResults(res.data.results)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (running) return <AIThinking label={`Running ${numRuns} scenario simulations...`} />

  const agg = results?.aggregate

  return (
    <div className="p-6 fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(`/sessions/${id}`)} className="text-theater-muted hover:text-theater-text">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <BarChart3 className="w-6 h-6 text-theater-accent-light" />
            MONTE CARLO ANALYZER
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-theater-muted text-sm">{session?.title}</p>
            <span className="text-xs font-mono text-yellow-600 border border-yellow-200 bg-yellow-50 px-2 py-0.5 rounded">
              AI-NARRATED ANALYSIS
            </span>
          </div>
        </div>
      </div>

      {/* Run controls */}
      <div className="bg-theater-card border border-theater-border rounded-lg p-4 flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-theater-text font-mono font-semibold text-sm">Probability Analysis</p>
          <p className="text-theater-muted text-xs mt-0.5">Theater generates narrative simulations varying key assumptions to identify likely outcomes. Results reflect AI analysis, not stochastic modeling.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-theater-muted text-xs font-mono">SIMULATIONS:</label>
            <select
              value={numRuns}
              onChange={e => setNumRuns(Number(e.target.value))}
              className="bg-theater-bg border border-theater-border rounded px-2 py-1 text-theater-text text-xs font-mono focus:outline-none"
            >
              {[5, 10, 20, 30].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <button
            onClick={handleRun}
            className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-4 py-2 rounded font-mono text-sm font-semibold transition-colors"
          >
            <Zap className="w-4 h-4" />
            {results ? 'Re-run Analysis' : 'Run Analysis'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-theater-red text-sm bg-red-50 border border-red-200 rounded p-3">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {!results && !error && (
        <div className="bg-theater-card border border-theater-border rounded-lg p-12 text-center">
          <BarChart3 className="w-12 h-12 text-theater-muted mx-auto mb-4" />
          <p className="text-theater-gray font-mono">No analysis run yet. Click "Run Analysis" to generate probability estimates.</p>
        </div>
      )}

      {agg && (
        <>
          {/* Bottom line */}
          {agg.analytical_bottom_line && (
            <div className="bg-theater-accent/5 border border-theater-accent/30 rounded-lg p-4">
              <p className="text-theater-accent-light font-mono font-semibold text-xs tracking-wider mb-2 flex items-center gap-2">
                <Zap className="w-3.5 h-3.5" /> ANALYTICAL BOTTOM LINE
              </p>
              <p className="text-theater-text text-sm leading-relaxed">{agg.analytical_bottom_line}</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Outcome probabilities */}
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-theater-accent-light" />
                OUTCOME PROBABILITY DISTRIBUTION
              </h3>
              {agg.outcome_probabilities?.length > 0 && (
                <>
                  <OutcomeChart data={agg.outcome_probabilities} />
                  <div className="mt-3 space-y-2">
                    {agg.outcome_probabilities.map((o, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-theater-gray flex-1 pr-2">{o.scenario_outcome}</span>
                        <span className="font-mono text-theater-text font-bold">{o.probability_pct}%</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Risk factors */}
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-700" />
                RISK FACTORS
              </h3>
              <div className="space-y-3">
                {(agg.risk_factors || []).map((rf, i) => (
                  <div key={i} className="border border-theater-border/50 rounded p-3">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <span className="text-theater-text text-xs font-semibold flex-1">{rf.factor}</span>
                      <ImpactBadge impact={rf.impact} />
                    </div>
                    <p className="text-theater-muted text-xs">{rf.frequency} occurrence</p>
                    <p className="text-theater-gray text-xs mt-1 italic">→ {rf.mitigation}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Key decision points */}
          {agg.key_decision_points?.length > 0 && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">KEY DECISION POINTS</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-theater-border">
                      <th className="text-left py-2 px-3 text-theater-muted font-mono">Turn</th>
                      <th className="text-left py-2 px-3 text-theater-muted font-mono">DECISION</th>
                      <th className="text-left py-2 px-3 text-theater-muted font-mono">IMPACT</th>
                      <th className="text-left py-2 px-3 text-theater-muted font-mono">RUNS</th>
                      <th className="text-left py-2 px-3 text-theater-muted font-mono">WHY IT MATTERS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agg.key_decision_points.map((dp, i) => (
                      <tr key={i} className="border-b border-theater-border/40 hover:bg-theater-card">
                        <td className="py-2 px-3 font-mono text-theater-accent-light">{dp.turn}</td>
                        <td className="py-2 px-3 text-theater-text font-semibold max-w-xs">{dp.decision}</td>
                        <td className="py-2 px-3"><ImpactBadge impact={dp.impact_rating} /></td>
                        <td className="py-2 px-3 font-mono text-theater-gray">{dp.appears_in_runs}/{numRuns}</td>
                        <td className="py-2 px-3 text-theater-gray leading-relaxed max-w-sm">{dp.rationale}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sensitivity */}
          {agg.sensitivity_findings && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-2">SENSITIVITY ANALYSIS</h3>
              <p className="text-theater-gray text-sm leading-relaxed">{agg.sensitivity_findings}</p>
            </div>
          )}

          {/* Narratives */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <NarrativeCard title="Most Likely Outcome" icon={TrendingUp} content={agg.most_likely_narrative} color="#171717" />
            <NarrativeCard title="Best Case" icon={CheckCircle} content={agg.best_case_narrative} color="#16a34a" />
            <NarrativeCard title="Worst Case" icon={AlertTriangle} content={agg.worst_case_narrative} color="#dc2626" />
          </div>

          {/* Simulation runs table */}
          {results.simulation_runs?.length > 0 && (
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">
                SIMULATION RUNS ({results.simulation_runs.length})
              </h3>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {results.simulation_runs.map(run => (
                  <div key={run.run_id} className="border border-theater-border/50 rounded p-3 text-xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-theater-accent-light">RUN {run.run_id}</span>
                      <div className="flex gap-2">
                        {run.outcome?.blue_achieves_primary && <span className="badge badge-blue">BLUE WIN</span>}
                        {run.outcome?.red_achieves_primary && <span className="badge badge-red">RED WIN</span>}
                      </div>
                    </div>
                    <div className="flex gap-3 flex-wrap mb-2">
                      {Object.entries(run.assumptions || {}).map(([k, v]) => (
                        <span key={k} className="text-theater-muted">{k}: <span className="text-theater-gray">{v}</span></span>
                      ))}
                    </div>
                    <p className="text-theater-gray leading-relaxed">{run.narrative}</p>
                    {run.outcome?.dominant_factor && (
                      <p className="text-yellow-700 mt-1">⚡ {run.outcome.dominant_factor}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
