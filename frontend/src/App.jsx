import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { createContext, useContext, useState, useEffect, Component } from 'react'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ScenarioLibrary from './pages/ScenarioLibrary'
import ScenarioBuilder from './pages/ScenarioBuilder'
import GameSession from './pages/GameSession'
import RedTeamConsole from './pages/RedTeamConsole'
import MonteCarloAnalyzer from './pages/MonteCarloAnalyzer'
import AARGenerator from './pages/AARGenerator'
import Admin from './pages/Admin'
import Settings from './pages/Settings'
import Login from './pages/Login'

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) return (
      <div style={{ padding: '2rem', fontFamily: 'monospace', color: '#f87171' }}>
        <h2>Something went wrong</h2>
        <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>{this.state.error.message}</p>
        <button onClick={() => this.setState({ error: null })} style={{ marginTop: '1rem', padding: '0.5rem 1rem', cursor: 'pointer' }}>
          Try again
        </button>
      </div>
    )
    return this.props.children
  }
}

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('theater_user')) } catch { return null }
  })

  const login = (userData, token) => {
    localStorage.setItem('theater_token', token)
    localStorage.setItem('theater_user', JSON.stringify(userData))
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem('theater_token')
    localStorage.removeItem('theater_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <ErrorBoundary>{children}</ErrorBoundary>
    </AuthContext.Provider>
  )
}

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="scenarios" element={<ScenarioLibrary />} />
            <Route path="scenarios/new" element={<ScenarioBuilder />} />
            <Route path="scenarios/:id/edit" element={<ScenarioBuilder />} />
            <Route path="sessions/:id" element={<GameSession />} />
            <Route path="sessions/:id/red-team" element={<RedTeamConsole />} />
            <Route path="sessions/:id/monte-carlo" element={<MonteCarloAnalyzer />} />
            <Route path="sessions/:id/aar" element={<AARGenerator />} />
            <Route path="admin" element={<Admin />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
