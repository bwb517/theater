import { useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'

const VERBOSITY_OPTIONS = [
  { value: 1, label: 'Terse', description: 'Shortest responses — fastest, cheapest. Best for beta testing.' },
  { value: 2, label: 'Normal', description: 'Balanced detail. Default for most use cases.' },
  { value: 3, label: 'Verbose', description: 'Rich narratives and full analysis. Best for demos and exports.' },
]

export default function Settings() {
  const [verbosity, setVerbosity] = useState(() =>
    parseInt(localStorage.getItem('theater_verbosity') || '2', 10)
  )
  const [forecastingDefault, setForecastingDefault] = useState(() =>
    localStorage.getItem('theater_forecasting_default') === 'true'
  )

  const handleVerbosity = (v) => {
    setVerbosity(v)
    localStorage.setItem('theater_verbosity', String(v))
  }

  const handleForecastingDefault = (v) => {
    setForecastingDefault(v)
    localStorage.setItem('theater_forecasting_default', String(v))
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <SlidersHorizontal className="w-5 h-5 text-theater-accent" />
        <h1 className="text-theater-text text-xl font-bold">Settings</h1>
      </div>

      <div className="bg-theater-card border border-theater-border rounded p-5">
        <h2 className="text-theater-text text-sm font-semibold mb-1">AI Verbosity</h2>
        <p className="text-theater-muted text-xs mb-4">
          Controls how much prose we write in scenarios, adjudications, red team moves, Monte Carlo runs, and AARs.
          Lower verbosity reduces token usage and response time.
        </p>

        <div className="space-y-2">
          {VERBOSITY_OPTIONS.map(({ value, label, description }) => (
            <button
              key={value}
              onClick={() => handleVerbosity(value)}
              className={`w-full flex items-start gap-3 px-4 py-3 rounded border text-left transition-all ${
                verbosity === value
                  ? 'border-theater-accent bg-theater-accent/10'
                  : 'border-theater-border hover:border-theater-gray'
              }`}
            >
              <div className={`w-4 h-4 mt-0.5 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
                verbosity === value ? 'border-theater-accent' : 'border-theater-muted'
              }`}>
                {verbosity === value && (
                  <div className="w-2 h-2 rounded-full bg-theater-accent" />
                )}
              </div>
              <div>
                <div className={`text-sm font-medium ${verbosity === value ? 'text-theater-accent' : 'text-theater-text'}`}>
                  {label}
                </div>
                <div className="text-theater-muted text-xs mt-0.5">{description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="bg-theater-card border border-theater-border rounded p-5 mt-4">
        <h2 className="text-theater-text text-sm font-semibold mb-1">Session defaults</h2>
        <p className="text-theater-muted text-xs mb-4">
          These preferences apply automatically when launching a new session from the Scenario Library.
        </p>

        <button
          onClick={() => handleForecastingDefault(!forecastingDefault)}
          className={`w-full flex items-start gap-3 px-4 py-3 rounded border text-left transition-all ${
            forecastingDefault
              ? 'border-theater-accent bg-theater-accent/10'
              : 'border-theater-border hover:border-theater-gray'
          }`}
        >
          <div className={`w-4 h-4 mt-0.5 rounded border-2 flex-shrink-0 flex items-center justify-center ${
            forecastingDefault ? 'border-theater-accent bg-theater-accent' : 'border-theater-muted'
          }`}>
            {forecastingDefault && (
              <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 10 10">
                <path d="M1.5 5l2.5 2.5 4.5-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <div>
            <div className={`text-sm font-medium ${forecastingDefault ? 'text-theater-accent' : 'text-theater-text'}`}>
              Enable forecasting overlay
            </div>
            <div className="text-theater-muted text-xs mt-0.5">
              Track your prediction accuracy turn by turn. Adds a pre-turn probability form and Brier score tracking to sessions.
            </div>
          </div>
        </button>
      </div>
    </div>
  )
}
