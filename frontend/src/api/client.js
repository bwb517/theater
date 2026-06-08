import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('theater_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('theater_token')
      localStorage.removeItem('theater_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

export const getVerbosity = () => parseInt(localStorage.getItem('theater_verbosity') || '2', 10)

// Auth
export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

// Scenarios
export const scenariosApi = {
  list: (params) => api.get('/scenarios', { params }),
  get: (id) => api.get(`/scenarios/${id}`),
  generate: (prompt) => api.post('/scenarios/generate', { prompt, verbosity: getVerbosity() }),
  create: (data) => api.post('/scenarios', data),
  update: (id, data) => api.put(`/scenarios/${id}`, data),
  delete: (id) => api.delete(`/scenarios/${id}`),
  unitLibrary: (params) => api.get('/scenarios/units/library', { params }),
  addUnitToLibrary: (data) => api.post('/scenarios/units/library', data),
}

// Sessions
export const sessionsApi = {
  list: () => api.get('/sessions'),
  get: (id) => api.get(`/sessions/${id}`),
  getFiltered: (id, factionId) => api.get(`/sessions/${id}`, { params: { faction_id: factionId } }),
  create: (data) => api.post('/sessions', data),
  submitMoves: (id, data) => api.post(`/sessions/${id}/moves`, data),
  advanceTurn: (id) => api.post(`/sessions/${id}/advance-turn`),
  updateStatus: (id, status) => api.put(`/sessions/${id}/status`, null, { params: { status } }),
  saveGMNotes: (id, turn, notes) => api.post(`/sessions/${id}/turns/${turn}/gm-notes`, { notes }),
  updateGameState: (id, state) => api.put(`/sessions/${id}/game-state`, state),
  capitulate: (id, factionId) => api.post(`/sessions/${id}/capitulate`, { faction_id: factionId }),
  delete: (id) => api.delete(`/sessions/${id}`),
}

// Red Team
export const redTeamApi = {
  generateMoves: (sessionId, data) => api.post(`/sessions/${sessionId}/red-team`, { ...data, verbosity: getVerbosity() }),
  adjudicate: (sessionId, data) => api.post(`/sessions/${sessionId}/adjudicate`, { ...data, verbosity: getVerbosity() }),
  updatePersonality: (sessionId, data) => api.put(`/sessions/${sessionId}/personality`, data),
}

// Monte Carlo
export const monteCarloApi = {
  run: (data) => api.post('/monte-carlo/run', { ...data, verbosity: getVerbosity() }),
  get: (id) => api.get(`/monte-carlo/${id}`),
  getForSession: (sessionId) => api.get(`/monte-carlo/session/${sessionId}/latest`),
  getForScenario: (scenarioId) => api.get(`/monte-carlo/scenario/${scenarioId}/latest`),
}

// AAR
export const aarApi = {
  generate: (sessionId, data) => api.post(`/sessions/${sessionId}/aar`, { ...data, verbosity: getVerbosity() }),
  get: (sessionId) => api.get(`/sessions/${sessionId}/aar`),
  pdfUrl: (sessionId) => `/api/sessions/${sessionId}/aar/pdf`,
  getShared: (token) => api.get(`/sessions/aar/share/${token}`),
}

// Admin
export const adminApi = {
  stats: () => api.get('/admin/stats'),
  users: () => api.get('/admin/users'),
  sessions: () => api.get('/admin/sessions'),
  tokenUsage: () => api.get('/admin/token-usage'),
  tokenStats: () => api.get('/admin/token-stats'),
  tokenStatsByUser: () => api.get('/admin/token-stats/by-user'),
  resetPassword: (userId, newPassword) => api.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword }),
}
