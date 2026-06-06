import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import {
  LayoutDashboard, BookOpen, Plus, SlidersHorizontal, LogOut,
  Shield, ChevronRight, Activity, Users, Cpu
} from 'lucide-react'
import { adminApi } from '../api/client'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/scenarios', label: 'Scenario Library', icon: BookOpen, end: true },
  { to: '/scenarios/new', label: 'New Scenario', icon: Plus },
  { to: '/settings', label: 'Settings', icon: SlidersHorizontal },
  { to: '/admin', label: 'Admin', icon: Shield },
]

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [tokenUsage, setTokenUsage] = useState(null)

  useEffect(() => {
    if (user?.role !== 'admin') return
    adminApi.tokenUsage().then(r => setTokenUsage(r.data)).catch(() => {})
    const interval = setInterval(() => {
      adminApi.tokenUsage().then(r => setTokenUsage(r.data)).catch(() => {})
    }, 30_000)
    return () => clearInterval(interval)
  }, [user])

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen bg-theater-bg overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-theater-card border-r border-theater-border flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-theater-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-theater-accent/10 rounded border border-theater-border flex items-center justify-center">
              <Shield className="w-4 h-4 text-theater-accent" />
            </div>
            <div>
              <div className="font-sans font-bold text-theater-text text-lg">Theater</div>
              <div className="text-theater-muted text-xs">AI Wargaming</div>
            </div>
          </div>
        </div>

        {/* Classification */}
        <div className="bg-theater-card border-b border-theater-border px-3 py-1">
          <p className="text-theater-muted text-xs text-center tracking-wide">UNCLASSIFIED</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <p className="text-theater-muted text-xs px-2 py-1 font-medium">Navigation</p>
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-all ${
                  isActive
                    ? 'bg-theater-accent text-white border-l-2 border-theater-accent'
                    : 'text-theater-gray hover:text-theater-text hover:bg-theater-border'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-xs">{label}</span>
            </NavLink>
          ))}

          <div className="pt-3">
            <p className="text-theater-muted text-xs px-2 py-1 font-medium">Quick Actions</p>
            <button
              onClick={() => navigate('/scenarios/new')}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded text-sm text-theater-accent-light hover:bg-theater-border transition-all"
            >
              <Plus className="w-4 h-4" />
              <span className="text-xs">Build Scenario</span>
            </button>
          </div>

        </nav>

        {/* Token Usage */}
        {tokenUsage && (
          <div className="px-3 pb-2 border-t border-theater-border pt-2">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Cpu className="w-3 h-3 text-theater-muted" />
              <span className="text-theater-muted text-xs font-mono tracking-wider">TOKEN USAGE</span>
            </div>
            {(() => {
              const pct = Math.min(100, Math.round((tokenUsage.total_tokens / tokenUsage.token_budget) * 100))
              const barColor = pct >= 80 ? 'bg-theater-red' : pct >= 50 ? 'bg-yellow-500' : 'bg-theater-green'
              return (
                <>
                  <div className="h-1 bg-theater-border rounded-full overflow-hidden mb-1">
                    <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex justify-between text-xs font-mono text-theater-muted">
                    <span>{fmt(tokenUsage.total_tokens)} used</span>
                    <span>{fmt(tokenUsage.tokens_remaining)} left</span>
                  </div>
                </>
              )
            })()}
          </div>
        )}

        {/* User */}
        <div className="p-3 border-t border-theater-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 bg-theater-border rounded-full flex items-center justify-center flex-shrink-0">
                <Users className="w-3.5 h-3.5 text-theater-gray" />
              </div>
              <div className="min-w-0">
                <div className="text-theater-text text-xs font-semibold truncate">{user?.username}</div>
                <div className="text-theater-muted text-xs">{user?.role}</div>
              </div>
            </div>
            <button onClick={handleLogout} className="text-theater-muted hover:text-theater-red transition-colors p-1 flex-shrink-0" title="Logout">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="h-10 flex-shrink-0 bg-theater-card border-b border-theater-border flex items-center justify-between px-4">
          <div className="flex items-center gap-2 text-theater-muted text-xs">
            <Activity className="w-3 h-3 text-theater-green" />
            <span>Theater Wargaming Platform</span>
            <ChevronRight className="w-3 h-3" />
            <span className="text-theater-gray">Operational</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-theater-muted">
            <span className="text-theater-gray">UNCLASSIFIED</span>
            <span>{new Date().toUTCString().replace(' GMT', 'Z')}</span>
          </div>
        </div>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
