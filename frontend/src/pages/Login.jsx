import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { authApi } from '../api/client'
import { Shield, Lock, User, Mail, AlertCircle } from 'lucide-react'

export default function Login() {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [creds, setCreds] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      if (mode === 'login') {
        const res = await authApi.login(creds.username, creds.password)
        login(res.data.user, res.data.access_token)
        navigate('/')
      } else {
        const res = await authApi.register({
          username: creds.username,
          email: creds.email,
          password: creds.password,
        })
        login(res.data.user, res.data.access_token)
        navigate('/')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode(m => m === 'login' ? 'register' : 'login')
    setError('')
    setCreds({ username: '', email: '', password: '' })
  }

  return (
    <div className="min-h-screen bg-theater-bg tac-grid flex items-center justify-center p-4">
      <div className="w-full max-w-md fade-in">
        {/* Classification */}
        <div className="classification-banner mb-6">
          UNCLASSIFIED — FOR AUTHORIZED USE ONLY
        </div>

        <div className="bg-white border border-theater-border rounded-lg p-8 shadow-sm">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-theater-card rounded-lg border border-theater-border mb-4">
              <Shield className="w-8 h-8 text-theater-accent" />
            </div>
            <h1 className="text-3xl font-bold text-theater-text">Theater</h1>
            <p className="text-theater-gray text-sm mt-1">AI Wargaming Platform</p>
            <div className="flex items-center justify-center gap-2 mt-3">
              <div className="h-px w-12 bg-theater-border" />
              <span className="text-theater-muted text-xs">
                {mode === 'login' ? 'Secure Access' : 'Create Account'}
              </span>
              <div className="h-px w-12 bg-theater-border" />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-theater-gray font-medium mb-1.5">
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theater-muted" />
                <input
                  type="text"
                  value={creds.username}
                  onChange={e => setCreds(p => ({ ...p, username: e.target.value }))}
                  className="w-full bg-theater-bg border border-theater-border rounded px-10 py-2.5 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors"
                  placeholder="Enter username"
                  required
                />
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs text-theater-gray font-medium mb-1.5">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theater-muted" />
                  <input
                    type="email"
                    value={creds.email}
                    onChange={e => setCreds(p => ({ ...p, email: e.target.value }))}
                    className="w-full bg-theater-bg border border-theater-border rounded px-10 py-2.5 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors"
                    placeholder="Enter email"
                    required
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs text-theater-gray font-medium mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theater-muted" />
                <input
                  type="password"
                  value={creds.password}
                  onChange={e => setCreds(p => ({ ...p, password: e.target.value }))}
                  className="w-full bg-theater-bg border border-theater-border rounded px-10 py-2.5 text-theater-text text-sm focus:outline-none focus:border-theater-accent transition-colors"
                  placeholder={mode === 'register' ? 'Min 8 characters' : 'Enter password'}
                  required
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-theater-red text-sm bg-red-50 border border-red-200 rounded p-3">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-theater-accent hover:bg-theater-accent-light disabled:opacity-50 text-white font-semibold py-2.5 rounded transition-colors mt-2"
            >
              {loading
                ? (mode === 'login' ? 'Signing in...' : 'Creating account...')
                : (mode === 'login' ? 'Sign In' : 'Create Account')}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-theater-border text-center">
            {mode === 'login' ? (
              <p className="text-theater-muted text-xs">
                Don't have an account?{' '}
                <button
                  onClick={switchMode}
                  className="text-theater-accent font-medium hover:underline"
                >
                  Sign Up
                </button>
              </p>
            ) : (
              <p className="text-theater-muted text-xs">
                Already have an account?{' '}
                <button
                  onClick={switchMode}
                  className="text-theater-accent font-medium hover:underline"
                >
                  Sign In
                </button>
              </p>
            )}
          </div>
        </div>

        <p className="text-center text-theater-muted text-xs mt-4">
          Theater v1.0 · Powered by Claude AI · UNCLASSIFIED
        </p>
      </div>
    </div>
  )
}
