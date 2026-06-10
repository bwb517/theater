import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { scenariosApi, sessionsApi } from '../api/client'
import { useAuth } from '../App'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge, SideChip } from '../components/StatusBadge'
import {
  Search, Plus, Copy, Play, Download, BookOpen,
  Globe, Star, ChevronDown, ChevronUp, Users,
} from 'lucide-react'

// ─── Shared helpers ────────────────────────────────────────────────────────────

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ─── My Scenarios tab ─────────────────────────────────────────────────────────

function ScenarioCard({ scenario, onLaunch, onClone, onEdit, onPublish, onExport, userRole }) {
  const factions = scenario.factions || []

  return (
    <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden hover:border-theater-accent/30 transition-all group">
      <div className={`h-1 ${scenario.is_template ? 'bg-theater-accent' : 'bg-theater-border'}`} />
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {scenario.is_template && <span className="badge badge-blue text-xs">TEMPLATE</span>}
              {scenario.is_published && (
                <span className="flex items-center gap-1 text-xs font-mono text-emerald-400 border border-emerald-400/30 rounded px-1.5 py-0.5">
                  <Globe className="w-2.5 h-2.5" /> PUBLIC
                </span>
              )}
              <StatusBadge status={scenario.scenario_type} />
            </div>
            <h3 className="text-theater-text font-semibold text-sm leading-tight group-hover:text-theater-accent-light transition-colors line-clamp-2">
              {scenario.title}
            </h3>
          </div>
        </div>

        <p className="text-theater-muted text-xs mb-3 font-mono">{scenario.timeframe}</p>
        {scenario.geography?.region && (
          <p className="text-theater-gray text-xs mb-3 line-clamp-1">{scenario.geography.region}</p>
        )}

        <div className="flex flex-wrap gap-1 mb-3">
          {factions.slice(0, 4).map(f => <SideChip key={f.faction_id} side={f.side} />)}
        </div>

        <div className="flex gap-4 text-xs font-mono text-theater-muted mb-4">
          <span>{factions.length} factions</span>
          <span>{scenario.win_conditions?.duration_turns || '?'} turns</span>
          <span>{scenario.injects?.length || 0} injects</span>
        </div>

        <div className="flex gap-2 pt-3 border-t border-theater-border flex-wrap">
          <button
            onClick={() => onLaunch(scenario)}
            className="flex-1 flex items-center justify-center gap-1.5 bg-theater-accent/10 hover:bg-theater-accent/20 text-theater-accent-light border border-theater-accent/30 rounded py-1.5 text-xs font-mono font-semibold transition-all"
          >
            <Play className="w-3 h-3" /> Launch
          </button>
          <button
            onClick={() => onEdit(scenario)}
            className="flex items-center justify-center gap-1.5 px-3 border border-theater-border hover:border-theater-accent/30 rounded py-1.5 text-xs font-mono text-theater-gray hover:text-theater-text transition-all"
          >
            EDIT
          </button>
          <button
            onClick={() => onClone(scenario)}
            className="flex items-center justify-center p-1.5 border border-theater-border hover:border-theater-accent/30 rounded text-theater-gray hover:text-theater-text transition-all"
            title="Clone scenario"
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onExport(scenario)}
            className="flex items-center justify-center p-1.5 border border-theater-border hover:border-theater-accent/30 rounded text-theater-gray hover:text-theater-text transition-all"
            title="Export as JSON template"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
          {(userRole === 'admin' || userRole === 'game_master') && !scenario.is_published && (
            <button
              onClick={() => onPublish(scenario)}
              className="flex items-center justify-center p-1.5 border border-theater-border hover:border-emerald-400/40 rounded text-theater-gray hover:text-emerald-400 transition-all"
              title="Publish to public library"
            >
              <Globe className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function MyScenarios({ userRole }) {
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [forecastingEnabled, setForecastingEnabled] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    scenariosApi.list().then(r => setScenarios(r.data)).finally(() => setLoading(false))
  }, [])

  const types = ['All', 'Tactical', 'Operational', 'Strategic', 'Gray-Zone']
  const filtered = scenarios.filter(s => {
    const matchSearch = !search || s.title?.toLowerCase().includes(search.toLowerCase()) ||
      s.geography?.region?.toLowerCase().includes(search.toLowerCase())
    const matchType = typeFilter === 'All' || s.scenario_type === typeFilter
    return matchSearch && matchType
  })

  const handleLaunch = async (scenario) => {
    try {
      const wc = scenario.win_conditions || {}
      const faction_assignments = (scenario.factions || []).map(f => ({
        faction_id: f.faction_id,
        type: f.role === 'AI-controlled' ? 'AI' : 'Player',
      }))
      const res = await sessionsApi.create({
        scenario_id: scenario.id,
        title: scenario.title,
        max_turns: wc.duration_turns || 8,
        time_per_turn_hours: 9,
        faction_assignments,
        forecasting_enabled: forecastingEnabled,
      })
      navigate(`/sessions/${res.data.id}`)
    } catch (e) {
      alert('Failed to create session: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleClone = async (scenario) => {
    try {
      const res = await scenariosApi.clone(scenario.id)
      navigate(`/scenarios/${res.data.id}/edit`)
    } catch (e) {
      alert('Clone failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handlePublish = async (scenario) => {
    if (!confirm(`Publish "${scenario.title}" to the public library? This makes it visible to all users.`)) return
    try {
      await scenariosApi.publish(scenario.id)
      setScenarios(prev => prev.map(s => s.id === scenario.id ? { ...s, is_published: true } : s))
    } catch (e) {
      alert('Publish failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleExport = async (scenario) => {
    try {
      const res = await scenariosApi.exportTemplate(scenario.id)
      const slug = scenario.title.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 30)
      downloadBlob(res.data, `theater_scenario_${slug}.json`)
    } catch (e) {
      alert('Export failed: ' + e.message)
    }
  }

  if (loading) return <LoadingSpinner label="Loading scenarios..." />

  return (
    <>
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theater-muted" />
          <input
            type="text"
            placeholder="Search scenarios..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-theater-card border border-theater-border rounded px-10 py-2.5 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors font-mono"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {types.map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-2 rounded text-xs font-mono border transition-all ${
                typeFilter === t
                  ? 'bg-theater-accent/20 text-theater-accent-light border-theater-accent/40'
                  : 'text-theater-gray border-theater-border hover:border-theater-accent/30 hover:text-theater-text'
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Optional analytic overlay applied to sessions launched from here */}
      <label className="flex items-center gap-2 mb-6 text-xs font-mono text-theater-gray cursor-pointer select-none">
        <input
          type="checkbox"
          checked={forecastingEnabled}
          onChange={e => setForecastingEnabled(e.target.checked)}
          className="accent-theater-accent"
        />
        Enable forecasting (track your prediction accuracy) for new sessions
      </label>

      {typeFilter === 'All' && (
        <div className="mb-6">
          <h2 className="text-theater-gray text-xs font-mono tracking-widest mb-3 flex items-center gap-2">
            <span className="h-px flex-1 bg-theater-border" />
            Official Templates ({filtered.filter(s => s.is_template).length})
            <span className="h-px flex-1 bg-theater-border" />
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.filter(s => s.is_template).map(s => (
              <ScenarioCard key={s.id} scenario={s} userRole={userRole}
                onLaunch={handleLaunch} onClone={handleClone}
                onEdit={sc => navigate(`/scenarios/${sc.id}/edit`)}
                onPublish={handlePublish} onExport={handleExport}
              />
            ))}
          </div>
        </div>
      )}

      {filtered.filter(s => !s.is_template).length > 0 && (
        <div>
          <h2 className="text-theater-gray text-xs font-mono tracking-widest mb-3 flex items-center gap-2">
            <span className="h-px flex-1 bg-theater-border" />
            Custom Scenarios ({filtered.filter(s => !s.is_template).length})
            <span className="h-px flex-1 bg-theater-border" />
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.filter(s => !s.is_template).map(s => (
              <ScenarioCard key={s.id} scenario={s} userRole={userRole}
                onLaunch={handleLaunch} onClone={handleClone}
                onEdit={sc => navigate(`/scenarios/${sc.id}/edit`)}
                onPublish={handlePublish} onExport={handleExport}
              />
            ))}
          </div>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-16">
          <BookOpen className="w-12 h-12 text-theater-muted mx-auto mb-4" />
          <p className="text-theater-gray font-mono">No scenarios match your search</p>
          <button onClick={() => { setSearch(''); setTypeFilter('All') }}
            className="text-theater-accent-light text-sm font-mono mt-2 hover:text-theater-text transition-colors">
            Clear filters
          </button>
        </div>
      )}
    </>
  )
}

// ─── Public Library tab ───────────────────────────────────────────────────────

function LibraryCard({ scenario, onCloneAndPlay, cloning }) {
  const [expanded, setExpanded] = useState(false)
  const factions = scenario.factions || []
  const situation = scenario.situation || {}

  return (
    <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden hover:border-theater-accent/30 transition-all">
      {/* Official badge strip */}
      <div className={`h-1 ${scenario.is_official ? 'bg-amber-500' : 'bg-theater-accent/40'}`} />
      <div className="p-4">
        {/* Title row */}
        <div className="flex items-start gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {scenario.is_official && (
                <span className="flex items-center gap-1 text-xs font-mono text-amber-400 border border-amber-400/30 rounded px-1.5 py-0.5">
                  <Star className="w-2.5 h-2.5" /> OFFICIAL
                </span>
              )}
              <StatusBadge status={scenario.scenario_type} />
            </div>
            <h3 className="text-theater-text font-semibold text-sm leading-tight line-clamp-2">
              {scenario.title}
            </h3>
          </div>
        </div>

        <p className="text-theater-muted text-xs mb-3 font-mono">{scenario.timeframe}</p>
        {scenario.geography?.region && (
          <p className="text-theater-gray text-xs mb-3 line-clamp-1">{scenario.geography.region}</p>
        )}

        {/* Faction chips */}
        <div className="flex flex-wrap gap-1 mb-3">
          {factions.slice(0, 4).map(f => <SideChip key={f.faction_id} side={f.side} />)}
        </div>

        {/* Stats row */}
        <div className="flex gap-4 text-xs font-mono text-theater-muted mb-2">
          <span>{factions.length} factions</span>
          <span>{scenario.win_conditions?.duration_turns || '?'} turns</span>
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3" /> {scenario.usage_count} uses
          </span>
        </div>

        {scenario.published_by_username && (
          <p className="text-theater-muted text-xs font-mono mb-3">
            by {scenario.published_by_username}
          </p>
        )}

        {/* Expandable detail */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-theater-border space-y-2 text-xs text-theater-gray">
            {(situation.summary || situation.background || situation.description) && (
              <p className="leading-relaxed">
                {situation.summary || situation.background || situation.description}
              </p>
            )}
            {scenario.win_conditions?.blue_wins?.length > 0 && (
              <div>
                <p className="text-theater-muted font-mono mb-1">Win Conditions (Blue):</p>
                {scenario.win_conditions.blue_wins.slice(0, 2).map((c, i) => (
                  <p key={i} className="ml-2">• {typeof c === 'string' ? c : c.condition}</p>
                ))}
              </div>
            )}
            {scenario.published_at && (
              <p className="text-theater-muted font-mono">
                Published {new Date(scenario.published_at).toLocaleDateString()}
              </p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-3 border-t border-theater-border mt-3">
          <button
            onClick={() => onCloneAndPlay(scenario)}
            disabled={cloning === scenario.id}
            className="flex-1 flex items-center justify-center gap-1.5 bg-theater-accent/10 hover:bg-theater-accent/20 text-theater-accent-light border border-theater-accent/30 rounded py-1.5 text-xs font-mono font-semibold transition-all disabled:opacity-50"
          >
            {cloning === scenario.id
              ? 'Cloning...'
              : <><Copy className="w-3 h-3" /> Clone &amp; Play</>
            }
          </button>
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center justify-center gap-1 px-3 border border-theater-border hover:border-theater-accent/30 rounded py-1.5 text-xs font-mono text-theater-gray hover:text-theater-text transition-all"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? 'Less' : 'Details'}
          </button>
        </div>
      </div>
    </div>
  )
}

function PublicLibrary() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('usage_count')
  const [page, setPage] = useState(1)
  const [cloning, setCloning] = useState(null)
  const [forecastingEnabled, setForecastingEnabled] = useState(false)
  const navigate = useNavigate()
  const LIMIT = 18

  useEffect(() => {
    setLoading(true)
    scenariosApi.library({ page, limit: LIMIT, sort, q: search || undefined })
      .then(r => { setItems(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }, [page, sort, search])

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [search, sort])

  const handleCloneAndPlay = async (scenario) => {
    setCloning(scenario.id)
    try {
      const cloneRes = await scenariosApi.clone(scenario.id)
      const cloned = cloneRes.data
      const wc = cloned.win_conditions || {}
      const faction_assignments = (cloned.factions || []).map(f => ({
        faction_id: f.faction_id,
        type: f.role === 'AI-controlled' ? 'AI' : 'Player',
      }))
      const sessionRes = await sessionsApi.create({
        scenario_id: cloned.id,
        title: cloned.title,
        max_turns: wc.duration_turns || 8,
        time_per_turn_hours: 9,
        faction_assignments,
        forecasting_enabled: forecastingEnabled,
      })
      navigate(`/sessions/${sessionRes.data.id}`)
    } catch (e) {
      alert('Clone failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setCloning(null)
    }
  }

  const totalPages = Math.ceil(total / LIMIT)

  return (
    <>
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theater-muted" />
          <input
            type="text"
            placeholder="Search public library..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-theater-card border border-theater-border rounded px-10 py-2.5 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors font-mono"
          />
        </div>
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          className="bg-theater-card border border-theater-border rounded px-3 py-2.5 text-theater-text text-xs font-mono focus:outline-none focus:border-theater-accent transition-colors"
        >
          <option value="usage_count">Most Used</option>
          <option value="created_at">Newest</option>
          <option value="title">Alphabetical</option>
        </select>
      </div>

      {/* Optional analytic overlay applied to sessions launched via Clone & Play */}
      <label className="flex items-center gap-2 mb-6 text-xs font-mono text-theater-gray cursor-pointer select-none">
        <input
          type="checkbox"
          checked={forecastingEnabled}
          onChange={e => setForecastingEnabled(e.target.checked)}
          className="accent-theater-accent"
        />
        Enable forecasting (track your prediction accuracy) for new sessions
      </label>

      {loading ? (
        <LoadingSpinner label="Loading library..." />
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <Globe className="w-12 h-12 text-theater-muted mx-auto mb-4" />
          <p className="text-theater-gray font-mono">
            {search ? 'No published scenarios match your search' : 'No scenarios published yet'}
          </p>
          {search && (
            <button onClick={() => setSearch('')}
              className="text-theater-accent-light text-sm font-mono mt-2 hover:text-theater-text transition-colors">
              Clear search
            </button>
          )}
        </div>
      ) : (
        <>
          <p className="text-theater-muted text-xs font-mono mb-4">{total} published scenario{total !== 1 ? 's' : ''}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
            {items.map(s => (
              <LibraryCard key={s.id} scenario={s} onCloneAndPlay={handleCloneAndPlay} cloning={cloning} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 border border-theater-border rounded text-xs font-mono text-theater-gray hover:text-theater-text disabled:opacity-40 transition-all"
              >
                ← Prev
              </button>
              <span className="text-theater-muted text-xs font-mono">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 border border-theater-border rounded text-xs font-mono text-theater-gray hover:text-theater-text disabled:opacity-40 transition-all"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}

// ─── Page shell ───────────────────────────────────────────────────────────────

export default function ScenarioLibrary() {
  const [activeTab, setActiveTab] = useState('mine')
  const { user } = useAuth()
  const navigate = useNavigate()

  const tabs = [
    { id: 'mine', label: 'My Scenarios', icon: BookOpen },
    { id: 'library', label: 'Public Library', icon: Globe },
  ]

  return (
    <div className="p-6 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <BookOpen className="w-6 h-6 text-theater-accent-light" />
            Scenario Library
          </h1>
        </div>
        {activeTab === 'mine' && (
          <button
            onClick={() => navigate('/scenarios/new')}
            className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-4 py-2 rounded font-mono text-sm font-semibold tracking-wider transition-colors"
          >
            <Plus className="w-4 h-4" /> New Scenario
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-theater-border">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-mono border-b-2 transition-all -mb-px ${
              activeTab === id
                ? 'border-theater-accent text-theater-accent-light'
                : 'border-transparent text-theater-gray hover:text-theater-text'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'mine'
        ? <MyScenarios userRole={user?.role} />
        : <PublicLibrary />
      }
    </div>
  )
}
