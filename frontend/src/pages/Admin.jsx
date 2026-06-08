import { useState, useEffect } from 'react'
import { adminApi, authApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge } from '../components/StatusBadge'
import { Shield, Users, Activity, Database, RefreshCw, AlertCircle, KeyRound, Check, X, DollarSign, Coins, Zap, Cpu } from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const CHART_COLORS = ['#171717', '#dc2626', '#a16207', '#16a34a', '#7c3aed', '#0891b2', '#db2777']
const usd = n => `$${(Number(n) || 0).toFixed(4)}`
const usd2 = n => `$${(Number(n) || 0).toFixed(2)}`
const num = n => (Number(n) || 0).toLocaleString()

const AXIS_TICK = { fill: '#737373', fontSize: 9, fontFamily: 'IBM Plex Mono' }
const TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #e5e5e5', borderRadius: 6, color: '#171717', fontFamily: 'IBM Plex Mono', fontSize: 11 }

function CostBarChart({ data, xKey }) {
  if (!data?.length) return <p className="text-theater-muted text-xs font-mono py-8 text-center">No data yet.</p>
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: -10, bottom: 30 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: '#e5e5e5' }}
          angle={-25} textAnchor="end" interval={0} height={50} />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: '#e5e5e5' }}
          tickFormatter={v => `$${v}`} />
        <Tooltip contentStyle={TOOLTIP_STYLE}
          formatter={(v, _n, p) => [`${usd(v)} · ${num(p.payload.total_tokens)} tok · ${num(p.payload.calls)} calls`, 'Cost']} />
        <Bar dataKey="cost_usd" radius={[3, 3, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function DailySpendChart({ data }) {
  if (!data?.length) return <p className="text-theater-muted text-xs font-mono py-8 text-center">No data yet.</p>
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ left: -10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey="date" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: '#e5e5e5' }} />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: '#e5e5e5' }}
          tickFormatter={v => `$${v}`} />
        <Tooltip contentStyle={TOOLTIP_STYLE}
          formatter={(v, _n, p) => [`${usd(v)} · ${num(p.payload.total_tokens)} tok`, 'Spend']} />
        <Line type="monotone" dataKey="cost_usd" stroke="#dc2626" strokeWidth={2} dot={{ r: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

function StatCard({ label, value, sub, icon: Icon, color = 'text-theater-accent-light' }) {
  return (
    <div className="bg-theater-card border border-theater-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-theater-muted text-xs font-mono tracking-wider">{label}</p>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <p className={`text-2xl font-bold font-mono ${color}`}>{value ?? '—'}</p>
      {sub && <p className="text-theater-muted text-xs mt-1">{sub}</p>}
    </div>
  )
}

function ResetPasswordCell({ userId }) {
  const [open, setOpen] = useState(false)
  const [pw, setPw] = useState('')
  const [status, setStatus] = useState(null) // null | 'ok' | 'err'
  const [msg, setMsg] = useState('')

  const submit = async () => {
    setStatus(null)
    try {
      await adminApi.resetPassword(userId, pw)
      setStatus('ok')
      setMsg('Password updated')
      setPw('')
      setTimeout(() => { setOpen(false); setStatus(null) }, 1500)
    } catch (e) {
      setStatus('err')
      setMsg(e.response?.data?.detail || 'Failed')
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 text-theater-muted hover:text-theater-accent-light transition-colors text-xs font-mono"
        title="Reset password"
      >
        <KeyRound className="w-3.5 h-3.5" /> Reset
      </button>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="password"
        value={pw}
        onChange={e => setPw(e.target.value)}
        placeholder="New password"
        minLength={8}
        className="bg-theater-bg border border-theater-border rounded px-2 py-1 text-xs text-theater-text w-32 focus:outline-none focus:border-theater-accent"
        onKeyDown={e => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') setOpen(false) }}
        autoFocus
      />
      <button onClick={submit} disabled={pw.length < 8} className="text-theater-green hover:text-green-400 disabled:opacity-30 transition-colors" title="Confirm">
        <Check className="w-3.5 h-3.5" />
      </button>
      <button onClick={() => { setOpen(false); setPw(''); setStatus(null) }} className="text-theater-muted hover:text-theater-red transition-colors" title="Cancel">
        <X className="w-3.5 h-3.5" />
      </button>
      {status && (
        <span className={`text-xs font-mono ${status === 'ok' ? 'text-theater-green' : 'text-theater-red'}`}>{msg}</span>
      )}
    </div>
  )
}

export default function Admin() {
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [sessions, setSessions] = useState([])
  const [tokenStats, setTokenStats] = useState(null)
  const [tokenByUser, setTokenByUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('overview')
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [statsRes, usersRes, sessionsRes] = await Promise.all([
        adminApi.stats(),
        adminApi.users(),
        adminApi.sessions()
      ])
      setStats(statsRes.data)
      setUsers(usersRes.data)
      setSessions(sessionsRes.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
    // Token stats are admin-only; fetch separately so a 403 never blanks the page
    try {
      const [tsRes, tuRes] = await Promise.all([
        adminApi.tokenStats(),
        adminApi.tokenStatsByUser(),
      ])
      setTokenStats(tsRes.data)
      setTokenByUser(tuRes.data)
    } catch {
      setTokenStats(null)
      setTokenByUser(null)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <LoadingSpinner />

  const TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'tokens', label: 'Tokens' },
    { key: 'users', label: `Users (${users.length})` },
    { key: 'sessions', label: `Sessions (${sessions.length})` },
  ]

  return (
    <div className="p-6 fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <Shield className="w-6 h-6 text-theater-red" />
            Admin Console
          </h1>
          <p className="text-theater-muted text-sm">System administration and monitoring</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text px-4 py-2 rounded text-xs font-mono transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-theater-red text-sm bg-red-50 border border-red-200 rounded p-3">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-theater-border">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-mono transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'text-theater-text border-theater-accent'
                : 'text-theater-muted border-transparent hover:text-theater-gray'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && stats && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Users" value={stats.total_users} icon={Users} />
            <StatCard label="Total Sessions" value={stats.total_sessions} icon={Activity} />
            <StatCard label="Total Scenarios" value={stats.total_scenarios} icon={Database} />
            <StatCard label="AAR Reports" value={stats.total_aars} icon={Shield} color="text-theater-green" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">Session Status Breakdown</h3>
              <div className="space-y-3">
                {Object.entries(stats.sessions_by_status || {}).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <StatusBadge status={status} />
                    <span className="font-mono text-theater-text text-sm">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">Recent Activity</h3>
              <div className="space-y-2">
                {(stats.recent_sessions || []).slice(0, 5).map(s => (
                  <div key={s.id} className="flex items-center justify-between text-xs border-b border-theater-border/40 pb-2">
                    <div>
                      <p className="text-theater-text font-semibold">{s.title}</p>
                      <p className="text-theater-muted">Turn {s.current_turn}/{s.max_turns}</p>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* System info */}
          <div className="bg-theater-card border border-theater-border rounded-lg p-4">
            <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">System Information</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <p className="text-theater-muted font-mono mb-1">AI Model</p>
                <p className="text-theater-text font-mono">{stats.ai_model || 'claude-sonnet-4-6'}</p>
              </div>
              <div>
                <p className="text-theater-muted font-mono mb-1">Database</p>
                <p className="text-theater-text font-mono">SQLite</p>
              </div>
              <div>
                <p className="text-theater-muted font-mono mb-1">Monte Carlo Runs</p>
                <p className="text-theater-text font-mono">{stats.total_monte_carlo || 0}</p>
              </div>
              <div>
                <p className="text-theater-muted font-mono mb-1">Classification</p>
                <p className="text-theater-text font-mono">UNCLASSIFIED</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tokens */}
      {tab === 'tokens' && (
        tokenStats ? (
          <div className="space-y-6">
            {/* Summary cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total Spend" value={usd2(tokenStats.totals.cost_usd)} icon={DollarSign} color="text-theater-red" />
              <StatCard label="Total Tokens" value={num(tokenStats.totals.total_tokens)} icon={Coins} sub={`${num(tokenStats.totals.calls)} API calls`} />
              <StatCard label="Cache Reads" value={num(tokenStats.totals.cache_read_tokens)} icon={Zap} color="text-theater-green" sub="billed at ~10% of input" />
              <StatCard label="Token Budget" value={num(tokenStats.totals.token_budget)} icon={Cpu} sub="informational" />
            </div>

            {/* Daily spend */}
            <div className="bg-theater-card border border-theater-border rounded-lg p-4">
              <h3 className="text-theater-text font-mono font-semibold text-sm mb-4 flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-theater-red" /> Daily Spend (USD)
              </h3>
              <DailySpendChart data={tokenStats.daily} />
            </div>

            {/* Cost per function + per scenario type */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">Cost per Function</h3>
                <CostBarChart data={tokenStats.per_function} xKey="function" />
              </div>
              <div className="bg-theater-card border border-theater-border rounded-lg p-4">
                <h3 className="text-theater-text font-mono font-semibold text-sm mb-4">Cost per Scenario Type</h3>
                <CostBarChart data={tokenStats.per_scenario_type} xKey="scenario_type" />
              </div>
            </div>

            {/* Per-user table */}
            <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
              <h3 className="text-theater-text font-mono font-semibold text-sm px-4 pt-4 pb-2">
                Spend by User <span className="text-theater-muted font-normal">· month to date as of {tokenByUser?.month_start ? new Date(tokenByUser.month_start).toLocaleDateString() : '—'}</span>
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-theater-border bg-theater-bg">
                    <th className="text-left py-3 px-4 text-theater-muted font-mono">User</th>
                    <th className="text-left py-3 px-4 text-theater-muted font-mono">Tier</th>
                    <th className="text-right py-3 px-4 text-theater-muted font-mono">Lifetime Cost</th>
                    <th className="text-right py-3 px-4 text-theater-muted font-mono">Lifetime Tokens</th>
                    <th className="text-right py-3 px-4 text-theater-muted font-mono">This Month</th>
                    <th className="text-right py-3 px-4 text-theater-muted font-mono">Calls</th>
                  </tr>
                </thead>
                <tbody>
                  {(tokenByUser?.users || []).map(u => (
                    <tr key={u.user_id} className="border-b border-theater-border/40 hover:bg-theater-card">
                      <td className="py-3 px-4 text-theater-text font-semibold">{u.username}</td>
                      <td className="py-3 px-4 font-mono text-theater-gray">{u.tier}</td>
                      <td className="py-3 px-4 font-mono text-theater-text text-right">{usd(u.cost_usd)}</td>
                      <td className="py-3 px-4 font-mono text-theater-gray text-right">{num(u.total_tokens)}</td>
                      <td className="py-3 px-4 font-mono text-theater-accent-light text-right">{usd(u.month_cost_usd)}</td>
                      <td className="py-3 px-4 font-mono text-theater-muted text-right">{num(u.calls)}</td>
                    </tr>
                  ))}
                  {!(tokenByUser?.users || []).length && (
                    <tr><td colSpan={6} className="py-6 text-center text-theater-muted font-mono">No attributed usage yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="bg-theater-card border border-theater-border rounded-lg p-12 text-center">
            <Coins className="w-12 h-12 text-theater-muted mx-auto mb-4" />
            <p className="text-theater-gray font-mono">No token usage data available yet, or insufficient permissions.</p>
            <p className="text-theater-muted text-xs mt-2">Usage is recorded as AI features (scenario generation, red team, adjudication, Monte Carlo, AAR) are run.</p>
          </div>
        )
      )}

      {/* Users */}
      {tab === 'users' && (
        <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-theater-border bg-theater-bg">
                <th className="text-left py-3 px-4 text-theater-muted font-mono">ID</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Username</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Email</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Role</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Clearance</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Status</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Password</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-theater-border/40 hover:bg-theater-card">
                  <td className="py-3 px-4 font-mono text-theater-muted">{u.id}</td>
                  <td className="py-3 px-4 text-theater-text font-semibold">{u.username}</td>
                  <td className="py-3 px-4 text-theater-gray">{u.email}</td>
                  <td className="py-3 px-4">
                    <span className={`badge ${u.role === 'admin' ? 'badge-red' : u.role === 'gamemaster' ? 'badge-paused' : 'badge-active'}`}>
                      {u.role?.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-theater-gray">{u.clearance_level || 'UNCLASSIFIED'}</td>
                  <td className="py-3 px-4">
                    <span className={`badge ${u.is_active ? 'badge-active' : 'badge-inactive'}`}>
                      {u.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </td>
                  <td className="py-3 px-4"><ResetPasswordCell userId={u.id} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sessions */}
      {tab === 'sessions' && (
        <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-theater-border bg-theater-bg">
                <th className="text-left py-3 px-4 text-theater-muted font-mono">ID</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Title</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Status</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Turn</th>
                <th className="text-left py-3 px-4 text-theater-muted font-mono">Created</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id} className="border-b border-theater-border/40 hover:bg-theater-card">
                  <td className="py-3 px-4 font-mono text-theater-muted">{s.id}</td>
                  <td className="py-3 px-4 text-theater-text font-semibold max-w-xs truncate">{s.title}</td>
                  <td className="py-3 px-4"><StatusBadge status={s.status} /></td>
                  <td className="py-3 px-4 font-mono text-theater-gray">{s.current_turn}/{s.max_turns}</td>
                  <td className="py-3 px-4 font-mono text-theater-muted">
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
