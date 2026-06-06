import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { aarApi, sessionsApi } from '../api/client'
import { LoadingSpinner, AIThinking } from '../components/LoadingSpinner'
import { ArrowLeft, FileText, Download, Share2, Zap, ChevronRight, AlertCircle, ExternalLink } from 'lucide-react'

function Section({ number, title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-theater-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between p-4 bg-theater-card hover:bg-theater-card transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-theater-accent-light font-bold text-sm">SEC {number}</span>
          <span className="text-theater-text font-semibold text-sm">{title}</span>
        </div>
        <ChevronRight className={`w-4 h-4 text-theater-muted transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && <div className="border-t border-theater-border p-4 bg-theater-bg">{children}</div>}
    </div>
  )
}

function FindingCard({ finding }) {
  const sigColor = { Critical: '#ef4444', Important: '#fbbf24', Noteworthy: '#22c55e' }
  return (
    <div className="border border-theater-border rounded p-3 mb-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono text-theater-accent-light text-xs">FINDING {finding.finding_number}</span>
        <span className="badge badge-active">{finding.confidence} Confidence</span>
        <span className="text-xs font-mono" style={{ color: sigColor[finding.significance] }}>
          [{finding.significance}]
        </span>
      </div>
      <p className="text-theater-gray text-xs leading-relaxed">{finding.finding}</p>
    </div>
  )
}

function LessonCard({ lesson }) {
  return (
    <div className="border border-theater-border rounded-lg p-4 mb-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="font-mono text-theater-accent-light font-bold text-sm">LL-{lesson.lesson_number}</span>
        <span className="badge badge-blue">{lesson.warfighting_function}</span>
      </div>
      <div className="space-y-2 text-xs">
        <div>
          <p className="text-theater-muted font-mono tracking-wider mb-1">Observation</p>
          <p className="text-theater-gray leading-relaxed">{lesson.observation}</p>
        </div>
        <div>
          <p className="text-theater-muted font-mono tracking-wider mb-1">Discussion</p>
          <p className="text-theater-gray leading-relaxed">{lesson.discussion}</p>
        </div>
        <div className="bg-theater-accent/5 border border-theater-accent/20 rounded p-2">
          <p className="text-theater-muted font-mono tracking-wider mb-1">Lesson Learned</p>
          <p className="text-theater-accent-light leading-relaxed font-medium">{lesson.lesson_learned}</p>
        </div>
        <div>
          <p className="text-theater-muted font-mono tracking-wider mb-1">Recommendation</p>
          <p className="text-theater-gray leading-relaxed">→ {lesson.recommendation}</p>
        </div>
      </div>
    </div>
  )
}

function DecisionRow({ decision }) {
  const gradeColor = { Good: '#22c55e', Excellent: '#22c55e', Acceptable: '#fbbf24', Poor: '#ef4444' }
  return (
    <div className="border border-theater-border/50 rounded p-3 mb-2 text-xs">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-theater-muted">Turn {decision.turn}</span>
          <span className="font-semibold text-theater-text">{decision.decision}</span>
        </div>
        <span className="font-mono font-bold" style={{ color: gradeColor[decision.assessment] || '#9ca3af' }}>
          {decision.assessment}
        </span>
      </div>
      <p className="text-theater-gray">{decision.rationale}</p>
      {decision.alternative && <p className="text-theater-muted mt-1">Alt: {decision.alternative}</p>}
    </div>
  )
}

export default function AARGenerator() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [aar, setAar] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [gmNotes, setGmNotes] = useState('')
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [activeSection, setActiveSection] = useState(null)

  useEffect(() => {
    sessionsApi.get(id).then(r => setSession(r.data)).finally(() => setLoading(false))
    aarApi.get(id).then(r => setAar(r.data)).catch(() => {})
  }, [id])

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    try {
      const res = await aarApi.generate(id, { gm_notes: gmNotes })
      setAar(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleCopyShareLink = () => {
    if (aar?.share_token) {
      navigator.clipboard.writeText(`${window.location.origin}/api/sessions/aar/share/${aar.share_token}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleExportMarkdown = () => {
    if (!aar?.content) return
    const c = aar.content
    const s1 = c.section_1_executive_summary || {}
    const s5 = c.section_5_lessons_learned || []
    const md = `# ${c.metadata?.exercise_title || 'After Action Review'}
**Classification:** ${c.metadata?.classification || 'UNCLASSIFIED'}
**Date:** ${c.metadata?.date_generated || ''}

## BLUF
${s1.bottom_line_up_front || ''}

## Executive Summary
${s1.scenario_overview || ''}

**Outcome:** ${s1.outcome || ''}

## Key Findings
${(s1.key_findings || []).map(f => `${f.finding_number}. [${f.confidence}/${f.significance}] ${f.finding}`).join('\n')}

## Lessons Learned
${s5.map(l => `**LL-${l.lesson_number} [${l.warfighting_function}]**\n- Observation: ${l.observation}\n- Lesson: ${l.lesson_learned}\n- Recommendation: ${l.recommendation}`).join('\n\n')}
`
    const blob = new Blob([md], { type: 'text/markdown' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `AAR_${session?.title || 'exercise'}.md`; a.click()
  }

  if (loading) return <LoadingSpinner />
  if (generating) return <AIThinking label="Writing your After Action Review..." />

  const content = aar?.content
  const s1 = content?.section_1_executive_summary || {}
  const s2 = content?.section_2_chronological_narrative || {}
  const s3 = content?.section_3_blue_force_analysis || {}
  const s4 = content?.section_4_red_force_analysis || {}
  const s5 = content?.section_5_lessons_learned || []
  const s6 = content?.section_6_implications || {}
  const s7 = content?.section_7_appendices || {}

  return (
    <div className="p-6 fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(`/sessions/${id}`)} className="text-theater-muted hover:text-theater-text">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-theater-text tracking-wider font-mono flex items-center gap-3">
            <FileText className="w-6 h-6 text-theater-accent-light" />
            AFTER ACTION REVIEW
          </h1>
          <p className="text-theater-muted text-sm">{session?.title}</p>
        </div>
        {content && (
          <div className="flex items-center gap-2">
            <button onClick={handleCopyShareLink} className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text px-3 py-2 rounded text-xs font-mono transition-all">
              <Share2 className="w-3.5 h-3.5" />
              {copied ? 'COPIED!' : 'SHARE LINK'}
            </button>
            <button onClick={handleExportMarkdown} className="flex items-center gap-2 border border-theater-border hover:border-theater-accent/40 text-theater-gray hover:text-theater-text px-3 py-2 rounded text-xs font-mono transition-all">
              <Download className="w-3.5 h-3.5" />
              MARKDOWN
            </button>
            <a
              href={aarApi.pdfUrl(id)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-3 py-2 rounded text-xs font-mono font-semibold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              EXPORT PDF
            </a>
          </div>
        )}
      </div>

      {/* Generate */}
      {!content && (
        <div className="bg-theater-card border border-theater-border rounded-lg p-6 space-y-4">
          <h3 className="text-theater-text font-mono font-semibold">Generate After Action Review</h3>
          <p className="text-theater-muted text-sm">We will analyze the complete game log and produce a structured professional AAR.</p>
          <div>
            <label className="block text-xs font-mono text-theater-muted mb-2">GAME MASTER NOTES (optional)</label>
            <textarea
              value={gmNotes}
              onChange={e => setGmNotes(e.target.value)}
              rows={3}
              placeholder="Add any notes about the game session, key observations, or themes to highlight in the AAR..."
              className="w-full bg-theater-bg border border-theater-border rounded p-3 text-theater-text text-sm font-mono resize-none focus:outline-none focus:border-theater-accent transition-colors"
            />
          </div>
          {error && (
            <div className="flex items-center gap-2 text-theater-red text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          <button
            onClick={handleGenerate}
            className="flex items-center gap-2 bg-theater-accent hover:bg-theater-accent-light text-white px-6 py-3 rounded font-mono font-semibold tracking-wider transition-colors"
          >
            <Zap className="w-4 h-4" />
            GENERATE AAR
          </button>
        </div>
      )}

      {content && (
        <>
          {/* Classification banner */}
          <div className="classification-banner rounded">
            ⬛ UNCLASSIFIED // FOR EXERCISE PURPOSES ONLY ⬛
          </div>

          {/* Metadata */}
          <div className="bg-theater-card border border-theater-border rounded-lg p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              {[
                ['Exercise', content.metadata?.exercise_title],
                ['Type', content.metadata?.scenario_type],
                ['Duration', `${content.metadata?.duration_turns} turns`],
                ['Generated', content.metadata?.date_generated],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-theater-muted font-mono tracking-wider mb-1">{k}</p>
                  <p className="text-theater-text font-semibold">{v || '—'}</p>
                </div>
              ))}
            </div>
          </div>

          {/* BLUF */}
          {s1.bottom_line_up_front && (
            <div className="bg-theater-accent/5 border-l-4 border-theater-accent-light rounded-r-lg p-4">
              <p className="text-theater-accent-light font-mono font-bold text-xs tracking-wider mb-2">Bottom Line Up Front</p>
              <p className="text-theater-text text-sm leading-relaxed font-semibold">{s1.bottom_line_up_front}</p>
            </div>
          )}

          <div className="space-y-3">
            {/* Section 1 */}
            <Section number="1" title="EXECUTIVE SUMMARY" defaultOpen>
              <p className="text-theater-gray text-xs leading-relaxed mb-4">{s1.scenario_overview}</p>
              <p className="text-theater-muted text-xs font-mono mb-1">Outcome</p>
              <p className="text-theater-text text-sm mb-4">{s1.outcome}</p>
              {s1.key_findings?.length > 0 && (
                <>
                  <p className="text-theater-muted text-xs font-mono tracking-wider mb-3">Key Findings</p>
                  {s1.key_findings.map((f, i) => <FindingCard key={i} finding={f} />)}
                </>
              )}
            </Section>

            {/* Section 2 */}
            <Section number="2" title="CHRONOLOGICAL NARRATIVE">
              {s2.overall_flow && <p className="text-theater-gray text-xs leading-relaxed mb-4 italic">{s2.overall_flow}</p>}
              {(s2.phase_narratives || []).map((phase, i) => (
                <div key={i} className="mb-4 border-l-2 border-theater-accent/30 pl-4">
                  <p className="text-theater-accent-light font-mono font-semibold text-xs mb-2">{phase.phase}</p>
                  <p className="text-theater-gray text-xs leading-relaxed">{phase.narrative}</p>
                  {phase.turning_point && (
                    <p className="text-yellow-700 text-xs mt-2 font-mono">⚡ TURNING POINT: {phase.turning_point}</p>
                  )}
                  {phase.decisive_moments?.length > 0 && (
                    <div className="mt-2">
                      {phase.decisive_moments.map((dm, j) => (
                        <p key={j} className="text-theater-gray text-xs">• {dm}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </Section>

            {/* Section 3 */}
            <Section number="3" title="BLUE FORCE ANALYSIS">
              <div className="flex items-center justify-between mb-4">
                <p className="text-theater-muted text-xs font-mono">Overall Grade</p>
                <span className="font-mono font-bold text-theater-green text-sm">{s3.overall_grade}</span>
              </div>
              <div className="space-y-3 text-xs mb-4">
                <div>
                  <p className="text-theater-muted font-mono tracking-wider mb-1">COA Assessment</p>
                  <p className="text-theater-gray leading-relaxed">{s3.coa_assessment}</p>
                </div>
                <div>
                  <p className="text-theater-muted font-mono tracking-wider mb-1">Execution Quality</p>
                  <p className="text-theater-gray leading-relaxed">{s3.execution_quality}</p>
                </div>
                <div>
                  <p className="text-theater-muted font-mono tracking-wider mb-1">Logistics & Sustainment</p>
                  <p className="text-theater-gray leading-relaxed">{s3.logistics_sustainment}</p>
                </div>
              </div>
              {s3.key_decisions?.length > 0 && (
                <>
                  <p className="text-theater-muted text-xs font-mono tracking-wider mb-3">Key Decisions</p>
                  {s3.key_decisions.map((d, i) => <DecisionRow key={i} decision={d} />)}
                </>
              )}
            </Section>

            {/* Section 4 */}
            <Section number="4" title="RED FORCE ANALYSIS">
              <p className="text-theater-gray text-xs leading-relaxed mb-4">{s4.strategy_assessment}</p>
              {s4.most_effective_ttps?.length > 0 && (
                <div className="mb-3">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Most Effective TTPs</p>
                  {s4.most_effective_ttps.map((t, i) => <p key={i} className="text-theater-gray text-xs">• {t}</p>)}
                </div>
              )}
              {s4.vulnerabilities_exploited?.length > 0 && (
                <div className="mb-3">
                  <p className="text-theater-red font-mono text-xs tracking-wider mb-2">Vulnerabilities Exploited</p>
                  {s4.vulnerabilities_exploited.map((v, i) => <p key={i} className="text-theater-gray text-xs">• {v}</p>)}
                </div>
              )}
              {s4.implications_for_real_world && (
                <div className="bg-theater-accent/5 border border-theater-accent/20 rounded p-3 mt-3">
                  <p className="text-theater-accent-light font-mono text-xs tracking-wider mb-1">Real-World Implications</p>
                  <p className="text-theater-gray text-xs leading-relaxed">{s4.implications_for_real_world}</p>
                </div>
              )}
            </Section>

            {/* Section 5 */}
            <Section number="5" title={`LESSONS LEARNED (${s5.length})`}>
              {s5.map((l, i) => <LessonCard key={i} lesson={l} />)}
            </Section>

            {/* Section 6 */}
            <Section number="6" title="IMPLICATIONS & RECOMMENDATIONS">
              {s6.doctrine_implications && (
                <div className="mb-3">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Doctrine Implications</p>
                  <p className="text-theater-gray text-xs leading-relaxed">{s6.doctrine_implications}</p>
                </div>
              )}
              {s6.capability_gaps_identified?.length > 0 && (
                <div className="mb-3">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Capability Gaps</p>
                  {s6.capability_gaps_identified.map((g, i) => <p key={i} className="text-theater-gray text-xs">• {g}</p>)}
                </div>
              )}
              {s6.planning_recommendations?.length > 0 && (
                <div className="mb-3">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Planning Recommendations</p>
                  {s6.planning_recommendations.map((r, i) => <p key={i} className="text-theater-gray text-xs">→ {r}</p>)}
                </div>
              )}
              {s6.questions_for_further_study?.length > 0 && (
                <div>
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Questions for Further Study</p>
                  {s6.questions_for_further_study.map((q, i) => <p key={i} className="text-theater-gray text-xs">? {q}</p>)}
                </div>
              )}
            </Section>

            {/* Section 7 */}
            <Section number="7" title="APPENDICES">
              {s7.score_summary?.length > 0 && (
                <div className="mb-4">
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Final Scores</p>
                  {s7.score_summary.map((s, i) => (
                    <div key={i} className="flex justify-between text-xs py-1 border-b border-theater-border/40">
                      <span className="text-theater-text">{s.faction}</span>
                      <span className="font-mono text-theater-accent-light">{s.final_score} pts</span>
                    </div>
                  ))}
                </div>
              )}
              {s7.scenario_parameters && (
                <div>
                  <p className="text-theater-muted font-mono text-xs tracking-wider mb-2">Scenario Parameters</p>
                  <div className="text-xs text-theater-gray space-y-1">
                    <p>Turns Played: {s7.scenario_parameters.turns_played}</p>
                    <p>Time per Turn: {s7.scenario_parameters.time_per_turn}</p>
                    <p>Total Game Time: {s7.scenario_parameters.total_game_time}</p>
                  </div>
                </div>
              )}
            </Section>
          </div>

          <div className="text-center py-4">
            <p className="text-theater-muted text-xs font-mono">
              THEATER Wargaming Platform — AI-Generated AAR — UNCLASSIFIED
            </p>
            <button onClick={handleGenerate} className="text-theater-accent-light text-xs font-mono mt-2 hover:text-theater-text transition-colors">
              → Regenerate AAR
            </button>
          </div>
        </>
      )}
    </div>
  )
}
