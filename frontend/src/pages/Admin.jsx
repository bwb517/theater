import { useState, useEffect } from 'react'
import { adminApi, authApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge } from '../components/StatusBadge'
import { Shield, Users, Activity, Database, RefreshCw, AlertCircle, KeyRound, Check, X } from 'lucide-react'

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
  }

  useEffect(() => { load() }, [])

  if (loading) return <LoadingSpinner />

  const TABS = [
    { key: 'overview', label: 'Overview' },
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
