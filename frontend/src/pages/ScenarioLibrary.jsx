import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { scenariosApi, sessionsApi } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge, SideChip } from '../components/StatusBadge'
import { Search, Plus, Copy, Play, Filter, Download, Upload, BookOpen } from 'lucide-react'

function ScenarioCard({ scenario, onLaunch, onClone, onEdit }) {
  const factions = scenario.factions || []
  const blue = factions.filter(f => f.side === 'Blue')
  const red = factions.filter(f => f.side === 'Red')

  return (
    <div className="bg-theater-card border border-theater-border rounded-lg overflow-hidden hover:border-theater-accent/30 transition-all group">
      {/* Header strip */}
      <div className={`h-1 ${scenario.is_template ? 'bg-theater-accent' : 'bg-theater-border'}`} />
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {scenario.is_template && (
                <span className="badge badge-blue text-xs">TEMPLATE</span>
              )}
              <StatusBadge status={scenario.scenario_type} />
            </div>
            <h3 className="text-theater-text font-semibold text-sm leading-tight group-hover:text-theater-accent-light transition-colors line-clamp-2">
              {scenario.title}
            </h3>
          </div>
        </div>

        <p className="text-theater-muted text-xs mb-3 font-mono">{scenario.timeframe}</p>

        {/* Geography */}
        {scenario.geography?.region && (
          <p className="text-theater-gray text-xs mb-3 line-clamp-1">{scenario.geography.region}</p>
        )}

        {/* Factions */}
        <div className="flex flex-wrap gap-1 mb-3">
          {factions.slice(0, 4).map(f => (
            <SideChip key={f.faction_id} side={f.side} />
          ))}
        </div>

        {/* Stats */}
        <div className="flex gap-4 text-xs font-mono text-theater-muted mb-4">
          <span>{factions.length} factions</span>
          <span>{scenario.win_conditions?.duration_turns || '?'} turns</span>
          <span>{scenario.injects?.length || 0} injects</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-3 border-t border-theater-border">
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
        </div>
      </div>
    </div>
  )
}

export default function ScenarioLibrary() {
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
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
    const title = scenario.title
    const wc = scenario.win_conditions || {}
    try {
      const faction_assignments = (scenario.factions || []).map(f => ({
        faction_id: f.faction_id,
        type: f.role === 'AI-controlled' ? 'AI' : 'Player',
      }))
      const res = await sessionsApi.create({
        scenario_id: scenario.id,
        title,
        max_turns: wc.duration_turns || 8,
        time_per_turn_hours: 9,
        faction_assignments,
      })
      navigate(`/sessions/${res.data.id}`)
    } catch (e) {
      alert('Failed to create session: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleClone = async (scenario) => {
    const { id, created_at, updated_at, is_template, template_name, created_by, ...data } = scenario
    try {
      const res = await scenariosApi.create({ ...data, title: `${scenario.title} (Copy)`, is_template: false })
      navigate(`/scenarios/${res.data.id}/edit`)
    } catch (e) {
      alert('Clone failed: ' + e.message)
    }
  }

  const handleImport = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = async ev => {
      try {
        const data = JSON.parse(ev.target.result)
        const res = await scenariosApi.create(data)
        navigate(`/scenarios/${res.data.id}/edit`)
      } catch (err) {
        alert('Import failed: ' + err.message)
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  if (loading) return <LoadingSpinner label="Loading scenario library..." />

  return (
    <div className="p-6 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <BookOpen className="w-6 h-6 text-theater-accent-light" />
            Scenario Library
          </h1>
          <p className="text-theater-muted text-sm mt-1">{scenarios.length} scenarios available</p>
        </div>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text rounded px-3 py-2 text-xs font-mono cursor-pointer transition-all">
            <Upload className="w-3.5 h-3.5" /> Import JSON
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
          </label>
          <button
            onClick={() => navigate('/scenarios/new')}
            className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-4 py-2 rounded font-mono text-sm font-semibold tracking-wider transition-colors"
          >
            <Plus className="w-4 h-4" /> New Scenario
          </button>
        </div>
      </div>

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
        <div className="flex gap-2">
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

      {/* Templates section */}
      {typeFilter === 'All' && (
        <div className="mb-6">
          <h2 className="text-theater-gray text-xs font-mono tracking-widest mb-3 flex items-center gap-2">
            <span className="h-px flex-1 bg-theater-border" />
            Official Templates ({filtered.filter(s => s.is_template).length})
            <span className="h-px flex-1 bg-theater-border" />
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.filter(s => s.is_template).map(s => (
              <ScenarioCard
                key={s.id} scenario={s}
                onLaunch={handleLaunch}
                onClone={handleClone}
                onEdit={sc => navigate(`/scenarios/${sc.id}/edit`)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Custom scenarios */}
      {filtered.filter(s => !s.is_template).length > 0 && (
        <div>
          <h2 className="text-theater-gray text-xs font-mono tracking-widest mb-3 flex items-center gap-2">
            <span className="h-px flex-1 bg-theater-border" />
            Custom Scenarios ({filtered.filter(s => !s.is_template).length})
            <span className="h-px flex-1 bg-theater-border" />
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.filter(s => !s.is_template).map(s => (
              <ScenarioCard
                key={s.id} scenario={s}
                onLaunch={handleLaunch}
                onClone={handleClone}
                onEdit={sc => navigate(`/scenarios/${sc.id}/edit`)}
              />
            ))}
          </div>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-16">
          <BookOpen className="w-12 h-12 text-theater-muted mx-auto mb-4" />
          <p className="text-theater-gray font-mono">No scenarios match your search</p>
          <button onClick={() => { setSearch(''); setTypeFilter('All') }} className="text-theater-accent-light text-sm font-mono mt-2 hover:text-theater-text transition-colors">
            Clear filters
          </button>
        </div>
      )}
    </div>
  )
}
