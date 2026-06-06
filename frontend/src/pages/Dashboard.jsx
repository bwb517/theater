import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sessionsApi, scenariosApi, adminApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge } from '../components/StatusBadge'
import { Plus, BookOpen, FileText, Activity, Users, Shield, Trash2, ChevronUp, Info } from 'lucide-react'

const WELCOME_KEY = 'theater_welcome_dismissed'

function WelcomeBanner() {
  const [dismissed, setDismissed] = useState(() => !!localStorage.getItem(WELCOME_KEY))

  if (dismissed) return null

  return (
    <div className="bg-theater-card border border-theater-accent/30 rounded-lg p-5 relative">
      <div className="flex items-start gap-3">
        <Info className="w-5 h-5 text-theater-accent-light flex-shrink-0 mt-0.5" />
        <div className="flex-1 space-y-3">
          <h2 className="text-theater-text font-semibold font-mono tracking-wider">Welcome to THEATER</h2>
          <p className="text-theater-gray text-sm leading-relaxed">
            THEATER is an AI-powered military wargaming platform. Here's how to get started:
          </p>
          <ol className="space-y-2 text-sm text-theater-gray list-none">
            <li className="flex gap-2"><span className="text-theater-accent-light font-mono font-bold">01</span><span><strong className="text-theater-text">Build a Scenario</strong> — click <em>New Scenario</em> or browse the Scenario Library. Use natural language to generate a full scenario with factions, units, and objectives via AI.</span></li>
            <li className="flex gap-2"><span className="text-theater-accent-light font-mono font-bold">02</span><span><strong className="text-theater-text">Start a Session</strong> — launch a game session from any scenario. Assign factions to players or AI, then begin turn-by-turn play on the Operational Map.</span></li>
            <li className="flex gap-2"><span className="text-theater-accent-light font-mono font-bold">03</span><span><strong className="text-theater-text">Submit Orders & Adjudicate</strong> — players submit moves across five warfighting functions. The AI Red Team generates adversary COAs and the adjudicator resolves each turn.</span></li>
            <li className="flex gap-2"><span className="text-theater-accent-light font-mono font-bold">04</span><span><strong className="text-theater-text">Analyze Outcomes</strong> — run Monte Carlo probability analysis, review the After Action Report, or export findings to PDF.</span></li>
          </ol>
          <p className="text-theater-muted text-xs font-mono">Demo credentials — admin: <strong>admin / theater123</strong> &nbsp;·&nbsp; player: <strong>player1 / theater123</strong></p>
        </div>
        <button
          onClick={() => { localStorage.setItem(WELCOME_KEY, '1'); setDismissed(true) }}
          className="text-theater-muted hover:text-theater-text transition-colors flex-shrink-0"
          title="Dismiss"
        >
          <ChevronUp className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color = 'theater-accent-light' }) {
  return (
    <div className="bg-theater-card border border-theater-border rounded-lg p-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded bg-theater-accent/10 border border-theater-accent/20 flex items-center justify-center flex-shrink-0`}>
        <Icon className={`w-5 h-5 text-${color}`} />
      </div>
      <div>
        <div className="text-2xl font-bold text-theater-text font-mono">{value ?? '—'}</div>
        <div className="text-theater-muted text-xs font-mono tracking-wider">{label}</div>
      </div>
    </div>
  )
}


export default function Dashboard() {
  const [sessions, setSessions] = useState([])
  const [scenarios, setScenarios] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  async function handleDelete(sessionId) {
    if (!window.confirm('Delete this session? All turn logs, AAR reports, and Monte Carlo results will be permanently removed.')) return
    await sessionsApi.delete(sessionId)
    setSessions(prev => prev.filter(s => s.id !== sessionId))
  }

  useEffect(() => {
    Promise.all([
      sessionsApi.list(),
      scenariosApi.list({ is_template: true }),
      adminApi.stats(),
    ]).then(([s, sc, st]) => {
      setSessions(s.data)
      setScenarios(sc.data)
      setStats(st.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner label="Loading THEATER..." />

  return (
    <div className="p-6 space-y-6 fade-in">
      <WelcomeBanner />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono">Operations Center</h1>
          <p className="text-theater-muted text-sm mt-1">AI-Powered Wargaming Platform</p>
        </div>
        <button
          onClick={() => navigate('/scenarios/new')}
          className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-4 py-2 rounded font-mono text-sm font-semibold tracking-wider transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Scenario
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Scenarios" value={stats?.total_scenarios} icon={BookOpen} />
        <StatCard label="Active Sessions" value={stats?.active_sessions} icon={Activity} color="theater-green" />
        <StatCard label="AARs Generated" value={stats?.total_aars} icon={FileText} />
        <StatCard label="Platform Users" value={stats?.total_users} icon={Users} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sessions */}
        <div className="lg:col-span-2 space-y-4">
          {sessions.length > 0 && (
            <>
              <h2 className="text-theater-text font-semibold font-mono tracking-wider flex items-center gap-2 pt-2">
                <FileText className="w-4 h-4 text-theater-gray" />
                All Sessions
              </h2>
              <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-theater-border">
                      <th className="text-left px-4 py-3 text-theater-muted font-mono text-xs tracking-wider">Exercise</th>
                      <th className="text-left px-4 py-3 text-theater-muted font-mono text-xs tracking-wider">Status</th>
                      <th className="text-left px-4 py-3 text-theater-muted font-mono text-xs tracking-wider">Turn</th>
                      <th className="text-left px-4 py-3 text-theater-muted font-mono text-xs tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.slice(0, 8).map(s => (
                      <tr key={s.id} className="border-b border-theater-border/50 hover:bg-theater-card transition-colors">
                        <td className="px-4 py-3">
                          <span className="text-theater-text font-medium">{s.title}</span>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                        <td className="px-4 py-3 font-mono text-theater-gray text-xs">{s.current_turn}/{s.max_turns}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-3 items-center">
                            <button onClick={() => navigate(`/sessions/${s.id}`)} className="text-theater-accent-light text-xs font-mono hover:text-theater-text transition-colors">Play</button>
                            <button onClick={() => navigate(`/sessions/${s.id}/aar`)} className="text-theater-gray text-xs font-mono hover:text-theater-text transition-colors">AAR</button>
                            <button onClick={() => navigate(`/sessions/${s.id}/monte-carlo`)} className="text-theater-gray text-xs font-mono hover:text-theater-text transition-colors">MC</button>
                            <button onClick={() => handleDelete(s.id)} className="text-theater-red hover:text-red-400 transition-colors" title="Delete session"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Scenario Templates */}
        <div className="space-y-4">
          <h2 className="text-theater-text font-semibold font-mono tracking-wider flex items-center gap-2">
            <Shield className="w-4 h-4 text-theater-accent-light" />
            Scenario Templates
          </h2>
          <div className="space-y-2">
            {scenarios.map(s => (
              <div
                key={s.id}
                onClick={() => navigate(`/scenarios/${s.id}/edit`)}
                className="bg-theater-card border border-theater-border rounded-lg p-3 hover:border-theater-accent/40 cursor-pointer transition-all group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-theater-text text-sm font-medium group-hover:text-theater-accent-light transition-colors">
                    {s.title?.split(':')[0]}
                  </span>
                  <StatusBadge status={s.scenario_type} />
                </div>
                <p className="text-theater-muted text-xs">{s.timeframe}</p>
                <p className="text-theater-muted text-xs font-mono mt-1">
                  {s.factions?.length || 0} factions · {s.win_conditions?.duration_turns || 0} turns
                </p>
              </div>
            ))}
          </div>
          <button
            onClick={() => navigate('/scenarios')}
            className="w-full text-center text-theater-muted text-xs font-mono hover:text-theater-accent-light transition-colors py-2"
          >
            → View full library
          </button>
        </div>
      </div>
    </div>
  )
}
