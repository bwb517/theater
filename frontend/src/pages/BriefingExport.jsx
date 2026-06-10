import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { briefingApi, sessionsApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { ArrowLeft, ClipboardList, Download, TrendingUp, AlertCircle, Target } from 'lucide-react'

// Trigger a browser download from an axios blob response (Bearer header is sent
// because the request goes through the axios client, unlike a raw anchor href).
function downloadBlob(res, filename) {
  const blob = new Blob([res.data], { type: res.headers['content-type'] })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function outcomeColor(outcome) {
  if (outcome === 'Blue won') return '#3b82f6'
  if (outcome === 'Red won') return '#ef4444'
  return '#a16207'
}

function StateEvolutionChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -10, right: 10, top: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey="turn" tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          tickLine={false} axisLine={{ stroke: '#e5e5e5' }}
          label={{ value: 'TURN', position: 'insideBottom', offset: -2, fill: '#737373', fontSize: 9 }} />
        <YAxis domain={[0, 100]} tick={{ fill: '#737373', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
        <Tooltip
          contentStyle={{ background: '#ffffff', border: '1px solid #e5e5e5', borderRadius: 6, color: '#171717', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
          formatter={(v, name) => [v == null ? 'n/a' : v, name]}
        />
        <Legend wrapperStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 11 }} />
        <Line type="monotone" dataKey="blue_strength" name="Blue" stroke="#3b82f6" strokeWidth={2}
          dot={{ r: 3 }} connectNulls />
        <Line type="monotone" dataKey="red_strength" name="Red" stroke="#ef4444" strokeWidth={2}
          dot={{ r: 3 }} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  )
}

function TurningPointCard({ tp }) {
  return (
    <div className="bg-theater-card border border-theater-border rounded-lg p-4 border-l-4" style={{ borderLeftColor: '#fbbf24' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono text-theater-accent-light font-bold text-sm">TURN {tp.turn_number}</span>
        <span className="badge badge-paused">{tp.impact_on_outcome}</span>
        <span className="ml-auto text-xs font-mono text-theater-muted">impact {tp.impact_score}</span>
      </div>
      <p className="text-theater-gray text-xs leading-relaxed mb-2">{tp.description}</p>
      <p className="text-theater-muted text-xs italic">{tp.why_significant}</p>
    </div>
  )
}

function TimelineTurn({ t }) {
  const sc = t.state_changes || {}
  const fmt = (v) => (v == null ? '—' : v > 0 ? `+${v}` : `${v}`)
  return (
    <div className="border border-theater-border rounded-lg p-4">
      <div className="flex items-center gap-3 mb-2">
        <span className="font-mono text-theater-accent-light font-bold text-sm">TURN {t.turn_number}</span>
        <span className="text-xs font-mono text-theater-muted">
          Δ Blue {fmt(sc.blue_strength_delta)} · Red {fmt(sc.red_strength_delta)}
        </span>
      </div>
      {t.adjudication_summary && (
        <p className="text-theater-gray text-xs leading-relaxed mb-2">{t.adjudication_summary}</p>
      )}
      {t.key_decisions?.length > 0 && (
        <div className="mb-2">
          <p className="text-theater-muted font-mono tracking-wider text-[10px] mb-1">KEY DECISIONS</p>
          <ul className="list-disc list-inside text-theater-gray text-xs space-y-0.5">
            {t.key_decisions.map((k, i) => <li key={i}>{k}</li>)}
          </ul>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 mt-2">
        {t.blue_moves?.length > 0 && (
          <div>
            <p className="text-[10px] font-mono tracking-wider mb-1" style={{ color: '#3b82f6' }}>BLUE MOVES</p>
            <ul className="text-theater-gray text-xs space-y-0.5">
              {t.blue_moves.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        )}
        {t.red_response?.length > 0 && (
          <div>
            <p className="text-[10px] font-mono tracking-wider mb-1" style={{ color: '#ef4444' }}>RED RESPONSE</p>
            <ul className="text-theater-gray text-xs space-y-0.5">
              {t.red_response.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default function BriefingExport() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [briefing, setBriefing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    sessionsApi.get(id).then(r => setSession(r.data)).catch(() => {})
    briefingApi.get(id)
      .then(r => setBriefing(r.data))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [id])

  const slug = (briefing?.metadata?.scenario_title || session?.title || 'briefing')
    .replace(/[^a-z0-9]+/gi, '_').slice(0, 30)

  const handleMarkdown = () =>
    briefingApi.exportMarkdown(id).then(r => downloadBlob(r, `THEATER_briefing_${slug}.md`))
  const handlePdf = () =>
    briefingApi.exportPdf(id).then(r => downloadBlob(r, `THEATER_briefing_${slug}.pdf`))

  if (loading) return <LoadingSpinner />

  if (error) return (
    <div className="p-6 fade-in">
      <button onClick={() => navigate(`/sessions/${id}`)} className="text-theater-muted hover:text-theater-text mb-4 flex items-center gap-2">
        <ArrowLeft className="w-5 h-5" /> Back to session
      </button>
      <div className="bg-theater-card border border-theater-border rounded-lg p-6 flex items-center gap-3 text-theater-gray">
        <AlertCircle className="w-5 h-5 text-red-400" />
        <span className="text-sm">{error}</span>
      </div>
    </div>
  )

  const md = briefing?.metadata || {}

  return (
    <div className="p-6 fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(`/sessions/${id}`)} className="text-theater-muted hover:text-theater-text">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <ClipboardList className="w-6 h-6 text-theater-accent-light" />
            BRIEFING EXPORT
          </h1>
          <p className="text-theater-muted text-sm">{md.scenario_title || session?.title}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleMarkdown} className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text px-3 py-2 rounded text-xs font-mono transition-all">
            <Download className="w-3.5 h-3.5" /> MARKDOWN
          </button>
          <button onClick={handlePdf} className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-3 py-2 rounded text-xs font-mono font-semibold transition-colors">
            <Download className="w-3.5 h-3.5" /> EXPORT PDF
          </button>
        </div>
      </div>

      {/* Outcome banner */}
      <div className="bg-theater-card border border-theater-border rounded-lg p-4 border-l-4" style={{ borderLeftColor: outcomeColor(briefing.outcome) }}>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-lg font-mono font-bold" style={{ color: outcomeColor(briefing.outcome) }}>
            {briefing.outcome}
          </span>
          <span className="text-xs font-mono text-theater-muted">
            {md.turns_played} turn(s) · {md.scenario_type} · {md.status}
          </span>
        </div>
        <p className="text-theater-gray text-sm leading-relaxed">{briefing.outcome_narrative}</p>
      </div>

      {/* Executive summary */}
      <div className="bg-theater-card border border-theater-border rounded-lg p-5">
        <h3 className="text-theater-text font-mono font-semibold text-sm mb-2 flex items-center gap-2">
          <Target className="w-4 h-4 text-theater-accent-light" /> EXECUTIVE SUMMARY
        </h3>
        <p className="text-theater-gray text-sm leading-relaxed">{briefing.executive_summary}</p>
      </div>

      {/* State evolution chart */}
      <div className="bg-theater-card border border-theater-border rounded-lg p-5">
        <h3 className="text-theater-text font-mono font-semibold text-sm mb-1 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-theater-accent-light" /> STATE EVOLUTION — MEAN FORCE STRENGTH
        </h3>
        {md.strength_metric_note && (
          <p className="text-theater-muted text-xs leading-relaxed mb-3">{md.strength_metric_note}</p>
        )}
        {briefing.state_evolution?.length > 1
          ? <StateEvolutionChart data={briefing.state_evolution} />
          : <p className="text-theater-muted text-xs">Not enough adjudicated turns to chart strength over time.</p>}
      </div>

      {/* Turning points */}
      <div>
        <h3 className="text-theater-text font-mono font-semibold text-sm mb-3 tracking-wider">TURNING POINTS</h3>
        {briefing.turning_points?.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {briefing.turning_points.map((tp, i) => <TurningPointCard key={i} tp={tp} />)}
          </div>
        ) : (
          <p className="text-theater-muted text-xs">No turning points detected from the adjudication record.</p>
        )}
      </div>

      {/* Decision timeline */}
      <div>
        <h3 className="text-theater-text font-mono font-semibold text-sm mb-3 tracking-wider">DECISION TIMELINE</h3>
        {briefing.timeline?.length > 0 ? (
          <div className="space-y-3">
            {briefing.timeline.map((t, i) => <TimelineTurn key={i} t={t} />)}
          </div>
        ) : (
          <p className="text-theater-muted text-xs">No adjudicated turns recorded for this session.</p>
        )}
      </div>
    </div>
  )
}
